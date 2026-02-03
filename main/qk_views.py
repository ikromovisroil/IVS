# qkviews.py
import base64
import io
import json
import os
import tempfile

import fitz  # PyMuPDF
import qrcode
from PIL import Image

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
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
    approved_text=None,   # py<3.10 bo'lsa ham ishlaydi
) -> None:
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

    # ✅ QR faqat tanlangan betga
    rect = fitz.Rect(x, y, x + s, y + s)
    page.insert_image(rect, stream=qr_png, overlay=True)

    # ✅ Matn har bir betga (agar approved_text bo'lsa)
    if approved_text:
        for p in doc:
            # chap tepa (point koordinata)
            p.insert_text(
                fitz.Point(10, 15),  # x=10, y=15 (xohlasangiz o'zgartirasiz)
                approved_text,
                fontsize=10,
                fontname="helv",
                color=(1, 0, 0),  # qizil
                overlay=True,
            )

    # xavfsiz overwrite
    dir_name = os.path.dirname(pdf_path)
    fd, tmp_path = tempfile.mkstemp(prefix="tmp_qr_", suffix=".pdf", dir=dir_name)
    os.close(fd)

    try:
        doc.save(tmp_path)
        doc.close()
        os.replace(tmp_path, pdf_path)
    except Exception:
        try:
            doc.close()
        except Exception:
            pass
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


@never_cache
@login_required
def deed_pdf_view(request, pk):
    deed = get_object_or_404(Deed, pk=pk)
    emp = request.user.employee

    # faqat sender yoki receiver
    if deed.sender != emp and deed.receiver != emp:
        return render(request, "main/deed_pdf_view.html", {"error": "Sizga ruxsat yo‘q"})

    if not deed.file:
        return render(request, "main/deed_pdf_view.html", {"error": "PDF yo‘q"})

    role = "sender" if deed.sender == emp else "receiver"

    # rad etilgan bo'lsa
    is_rejected = (deed.status_sender == "rejected") or (deed.status_receiver == "rejected")
    if is_rejected:
        return render(request, "main/deed_pdf_view.html", {"error": "Hujjat rad etilgan"})

    # receiver QR qo‘yishi uchun SSO_OK bo‘lishi shart
    if role == "receiver":
        ok = request.session.get("SSO_OK") or {}
        if ok.get("kind") != "deed" or ok.get("deed_id") != deed.id or ok.get("role") != "receiver":
            return render(request, "main/deed_pdf_view.html", {"error": "Avval SSO orqali tasdiqlang"})

    # QR lock (status orqali)
    sender_qr_done = (deed.status_sender == "approved")
    receiver_qr_done = (deed.status_receiver == "approved")
    qr_locked = (role == "sender" and sender_qr_done) or (role == "receiver" and receiver_qr_done)

    next_url = (request.GET.get("next") or "").strip() or request.META.get("HTTP_REFERER") or "/"

    pdf_file_url = request.build_absolute_uri(deed.file.url)  # PDF faylning linki
    status_url = request.build_absolute_uri(f"/deed/status/{deed.id}/")

    return render(request, "main/deed_pdf_view.html", {
        "deed_id": deed.id,
        "pdf_url": pdf_file_url,
        "status_url": status_url,
        "role": role,
        "qr_locked": qr_locked,
        "next_url": next_url,
    })


from datetime import datetime

FINAL_MARK = "[FINAL_TEXT_DONE]"

@csrf_exempt
@require_http_methods(["POST"])
@never_cache
@login_required
def deed_stamp_qr(request, pk):
    emp = request.user.employee

    # 1) JSON parse
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

        # 2) Permission: faqat sender/receiver
        if deed.sender != emp and deed.receiver != emp:
            return JsonResponse({"ok": False, "error": "Sizga ruxsat yo‘q"}, status=403)

        if not deed.file:
            return JsonResponse({"ok": False, "error": "PDF yo‘q"}, status=400)

        role = "sender" if deed.sender == emp else "receiver"

        # 3) Rad etilgan bo'lsa
        if deed.status_sender == "rejected" or deed.status_receiver == "rejected":
            return JsonResponse({"ok": False, "error": "Hujjat rad etilgan"}, status=400)

        ok_sso = request.session.get("SSO_OK") or {}

        # 4) Receiver uchun SSO OK shart
        if role == "receiver":
            if (
                ok_sso.get("kind") != "deed"
                or ok_sso.get("deed_id") != deed.id
                or ok_sso.get("role") != "receiver"
            ):
                return JsonResponse({"ok": False, "error": "SSO tasdiq topilmadi"}, status=403)

        # 5) Qayta qo‘yishni blok
        if role == "sender" and deed.status_sender == "approved":
            return JsonResponse({"ok": False, "error": "Sender QR allaqachon qo‘yilgan"}, status=400)
        if role == "receiver" and deed.status_receiver == "approved":
            return JsonResponse({"ok": False, "error": "Receiver QR allaqachon qo‘yilgan"}, status=400)

        # 6) QR ichidagi link
        status_url = request.build_absolute_uri(f"/deed/status/{deed.id}/")
        qr_png = _make_qr_png_bytes(status_url, size_px=size)

        # 7) Preview bo'lsa - faqat QR rasm qaytariladi
        if preview:
            b64 = base64.b64encode(qr_png).decode("utf-8")
            return JsonResponse({"ok": True, "qr_data_url": f"data:image/png;base64,{b64}"})

        # 8) Koordinatalar
        try:
            page = int(body.get("page") or 1)
            x = float(body.get("x") or 0)
            y = float(body.get("y") or 0)
            scale = float(body.get("scale") or 1.5)
        except Exception:
            return JsonResponse({"ok": False, "error": "Koordinata/scale xato"}, status=400)

        # 9) Status update + message (AVVAL statusni yozamiz)
        sso_message = (ok_sso.get("message") or "").strip()
        now = timezone.now()

        if role == "sender":
            deed.status_sender = "approved"
            deed.date_sender = now  # sizda bor
            if sso_message:
                deed.message_sender = sso_message
            deed.date_receiver = now
            deed.save(update_fields=["status_sender", "date_sender", "message_sender", "date_edit"])
        else:
            deed.status_receiver = "approved"
            deed.date_receiver = now  # sizda bor
            if sso_message:
                deed.message_receiver = sso_message
            deed.date_edit = now
            deed.save(update_fields=["status_receiver", "date_receiver", "message_receiver", "date_edit"])

        # 10) IKKALASI TASDIQLANGANMI? bo‘lsa — text tayyorlaymiz
        approved_text = None
        already_marked = (deed.message_user or "").find(FINAL_MARK) != -1

        if deed.receiver:
            if deed.status_sender == "approved" and deed.status_receiver == "approved" and not already_marked:
                approved_text = (
                    f"Ushbu hujjat {deed.sender} tomonidan "
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M')} da va "
                    f"{deed.receiver} tomonidan "
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M')} da tasdiqlandi."
                )

        else:
            if deed.status_sender == "approved" and not already_marked:
                approved_text = (
                    f"Ushbu hujjat {deed.sender} tomonidan "
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M')} da tasdiqlandi."
                )

        # 11) PDFga QR (har doim), text esa faqat final bo‘lsa
        try:
            _stamp_qr_pdf_overwrite_same_name(
                pdf_path=deed.file.path,
                page_1based=page,
                x_px=x,
                y_px=y,
                size_px=size,
                render_scale=scale,
                qr_png=qr_png,
                approved_text=approved_text,  # faqat ikkalasi bo‘lsa matn yoziladi
            )
        except Exception as e:
            return JsonResponse({"ok": False, "error": f"PDFga QR urishda xato: {e}"}, status=400)

        # 12) receiver yakunlaganda SSO_OK tozalansin
        if role == "receiver":
            request.session.pop("SSO_OK", None)

        messages.success(request, "✅ QR qo‘yildi")
        return JsonResponse({"ok": True, "redirect_url": redirect_url})

