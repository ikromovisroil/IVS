import base64
import io
import json
import os
import tempfile

import fitz  # PyMuPDF
import qrcode
from PIL import Image

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Deed


def _make_qr_png_bytes(text: str, size_px: int) -> bytes:
    qr = qrcode.QRCode(box_size=10, border=1)
    qr.add_data(text)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    img = img.resize((size_px, size_px), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _stamp_qr_pdf_overwrite_same_name(
    pdf_path: str,
    page_1based: int,
    x_px: float,
    y_px: float,
    size_px: int,
    render_scale: float,
    qr_png: bytes,
) -> None:
    """
    PDF nomi o‘zgarmaydi. Shu faylning o‘ziga yoziladi.
    (Xavfsiz qilish uchun temp faylga saqlab, keyin o‘sha nomga replace qilinadi)
    """
    doc = fitz.open(pdf_path)
    page_index = max(0, int(page_1based) - 1)

    if page_index >= doc.page_count:
        doc.close()
        raise ValueError("Bunday bet (page) yo‘q")

    page = doc[page_index]

    # canvas(px) -> pdf(point)
    x = float(x_px) / float(render_scale)
    y = float(y_px) / float(render_scale)
    s = float(size_px) / float(render_scale)

    rect = fitz.Rect(x, y, x + s, y + s)
    page.insert_image(rect, stream=qr_png, overlay=True)

    dir_name = os.path.dirname(pdf_path)
    fd, tmp_path = tempfile.mkstemp(prefix="tmp_qr_", suffix=".pdf", dir=dir_name)
    os.close(fd)

    try:
        doc.save(tmp_path)
        doc.close()
        os.replace(tmp_path, pdf_path)  # ✅ shu nomning o‘zi saqlanadi
    except Exception:
        try:
            doc.close()
        except Exception:
            pass
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


@login_required
def deed_pdf_view(request, pk):
    deed = get_object_or_404(Deed, pk=pk)
    emp = request.user.employee

    # ✅ faqat sender yoki receiver kira oladi
    if deed.sender != emp and deed.receiver != emp:
        return render(request, "main/deed_pdf_view.html", {"error": "Sizga ruxsat yo‘q"})

    if not deed.file:
        return render(request, "main/deed_pdf_view.html", {"error": "PDF yo‘q"})

    if deed.status == "rejected":
        return render(request, "main/deed_pdf_view.html", {"error": "Hujjat rad etilgan"})

    role = "sender" if deed.sender == emp else "receiver"

    # ✅ receiver approved bo‘lsa endi QR qo‘ya olmaydi (tasdiqlash tugaydi)
    # sender esa o‘zi qo‘ymagan bo‘lsa, approved bo‘lsa ham qo‘yishi mumkin
    # (agar sender ham approveddan keyin qo‘ymasın desangiz, pastdagi qatorni yoqing)
    # if deed.status == "approved": return render(...)

    qr_locked = False
    if role == "sender" and deed.sender_qr_done:
        qr_locked = True
    if role == "receiver" and (deed.receiver_qr_done or deed.status == "approved"):
        qr_locked = True

    # ✅ cache-buster: date_edit o‘zgarsa URL ham o‘zgaradi
    v = int(deed.date_edit.timestamp()) if deed.date_edit else int(timezone.now().timestamp())
    pdf_url = f"{deed.file.url}?v={v}"

    return render(request, "main/deed_pdf_view.html", {
        "deed_id": deed.id,
        "pdf_url": pdf_url,
        "role": role,
        "qr_locked": qr_locked,
    })


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def deed_stamp_qr(request, pk):
    emp = request.user.employee

    try:
        body = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "JSON xato"}, status=400)

    preview = bool(body.get("preview"))
    size = int(body.get("size") or 120)
    size = max(60, min(size, 400))

    redirect_url = (body.get("redirect_url") or "").strip() or request.META.get("HTTP_REFERER") or "/"

    with transaction.atomic():
        deed = Deed.objects.select_for_update().get(pk=pk)

        if deed.sender != emp and deed.receiver != emp:
            return JsonResponse({"ok": False, "error": "Sizga ruxsat yo‘q"}, status=403)

        if deed.status == "rejected":
            return JsonResponse({"ok": False, "error": "Hujjat rad etilgan"}, status=400)

        if not deed.file:
            return JsonResponse({"ok": False, "error": "PDF yo‘q"}, status=400)

        role = "sender" if deed.sender == emp else "receiver"

        # ✅ role bo‘yicha qayta QR qo‘yishni blok
        if role == "sender" and deed.sender_qr_done:
            return JsonResponse({"ok": False, "error": "Sender QR allaqachon qo‘yilgan"}, status=400)

        if role == "receiver" and (deed.receiver_qr_done or deed.status == "approved"):
            return JsonResponse({"ok": False, "error": "Receiver allaqachon tasdiqlagan"}, status=400)

        # QR ichidagi matn (skaner qilinsa shu viewer ochilsin)
        verify_url = request.build_absolute_uri(f"/deed/{deed.id}/viewer/?by={role}")
        qr_png = _make_qr_png_bytes(verify_url, size_px=size)

        if preview:
            b64 = base64.b64encode(qr_png).decode("utf-8")
            return JsonResponse({"ok": True, "qr_data_url": f"data:image/png;base64,{b64}"})


        # save coords
        try:
            page = int(body.get("page") or 1)
            x = float(body.get("x") or 0)
            y = float(body.get("y") or 0)
            scale = float(body.get("scale") or 1.5)
        except Exception:
            return JsonResponse({"ok": False, "error": "Koordinata/scale xato"}, status=400)

        # ✅ PDFga urish (nom o‘zgarmaydi)
        try:
            _stamp_qr_pdf_overwrite_same_name(
                pdf_path=deed.file.path,
                page_1based=page,
                x_px=x,
                y_px=y,
                size_px=size,
                render_scale=scale,
                qr_png=qr_png,
            )
        except Exception as e:
            return JsonResponse({"ok": False, "error": f"PDFga QR urishda xato: {e}"}, status=400)

        # ✅ DB yangilash + date_edit (cache bust)
        now = timezone.now()
        if role == "sender":
            deed.sender_qr_done = True
            deed.date_edit = now
            deed.save(update_fields=["sender_qr_done", "date_edit"])
        else:
            deed.receiver_qr_done = True
            deed.status = "approved"
            deed.date_edit = now
            deed.save(update_fields=["receiver_qr_done", "status", "date_edit"])

    return JsonResponse({"ok": True, "redirect_url": redirect_url})
