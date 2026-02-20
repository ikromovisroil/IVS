import base64
import json
from reportlab.lib.units import mm
import qrcode
import os
import time
import shutil
import logging
from io import BytesIO
from contextlib import contextmanager
from django.urls import reverse
from django.utils import timezone
from reportlab.pdfgen import canvas
from reportlab.lib.colors import red
from reportlab.lib.utils import ImageReader
from PyPDF2 import PdfReader, PdfWriter
from qrcode.constants import ERROR_CORRECT_M
from .models import *
from django.shortcuts import get_object_or_404

logger = logging.getLogger(__name__)


# ==========================================================
# 1) Lock (PDF band bo‘lib qolmasin)
# ==========================================================
@contextmanager
def file_lock(lock_path: str, timeout: int = 10):
    """
    PDF faylni band qilish uchun lock mexanizmi
    """
    start = time.time()
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            if time.time() - start > timeout:
                raise TimeoutError(f"PDF band (lock timeout) - {lock_path}")
            time.sleep(0.1)

    try:
        yield
    finally:
        try:
            os.remove(lock_path)
        except Exception as e:
            logger.warning(f"Lock faylni o'chirishda xatolik: {e}")


# ==========================================================
# 2) Overlay PDF (RAM’da) yaratish
# ==========================================================
def build_overlay_pdf_bytes(page_w: float, page_h: float, text: str, qr_link: str) -> bytes:
    # --- QR kod ---
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=6,
        border=1,
    )
    qr.add_data(qr_link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    qr_buf = BytesIO()
    img.save(qr_buf, format="PNG")
    qr_buf.seek(0)
    qr_reader = ImageReader(qr_buf)

    # --- Overlay PDF ---
    pdf_buf = BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=(page_w, page_h))

    # ✅ matn parametrlari
    c.setFillColor(red)
    font_name = "Helvetica-Bold"
    font_size = 10
    c.setFont(font_name, font_size)

    # ✅ matnni line qilib yozamiz (newline ishlaydi)
    lines = (text or "").splitlines()  # \n bo'lsa bo'lib beradi
    x = 10
    y = page_h - 15
    line_gap = 12  # qator oralig'i

    for line in lines:
        c.drawString(x, y, line)
        y -= line_gap

    # ✅ QR (pastki markaz)
    qr_size = 65
    x_center = (page_w - qr_size) / 2
    y_bottom = 5
    c.drawImage(qr_reader, x_center, y_bottom, width=qr_size, height=qr_size, mask="auto")

    c.showPage()
    c.save()
    return pdf_buf.getvalue()



# ==========================================================
# 3) PDF ga QK urish (HAR BIR SAHIFAGA, o‘lchamga mos)
# ==========================================================
def sign_pdf_inplace(pdf_path: str, request, approver_name: str, deed_id: int) -> bool:

    if not pdf_path or not os.path.exists(pdf_path):
        logger.error(f"PDF topilmadi: {pdf_path}")
        raise FileNotFoundError(f"PDF topilmadi: {pdf_path}")

    if not pdf_path.lower().endswith(".pdf"):
        logger.error(f"PDF noto‘g‘ri format: {pdf_path}")
        raise ValueError("PDF noto‘g‘ri format")

    abs_pdf = os.path.abspath(pdf_path)
    logger.info(f"PDF QK urilmoqda: {abs_pdf}")

    # QR link: deed status sahifasi
    qr_link = request.build_absolute_uri(reverse("deed_status", args=[int(deed_id)]))

    deed = get_object_or_404(Deed, id=deed_id)
    dt = timezone.localtime(timezone.now()).strftime("%d.%m.%Y %H:%M")
    if deed.receiver:
        text = (
            f"{deed.sender.full_name} tomonidan {dt} da tasdiqlandi\n"
            f"{deed.receiver.full_name} tomonidan {dt} da tasdiqlandi"
        )
    else:
        text = f"{deed.sender.full_name} tomonidan {dt} da tasdiqlandi"

    lock_path = abs_pdf + ".lock"
    tmp_out = abs_pdf.replace(".pdf", "_signed_tmp.pdf")

    try:
        with file_lock(lock_path, timeout=10):
            reader = PdfReader(abs_pdf)
            if not reader.pages:
                raise ValueError("PDF bo‘sh")

            writer = PdfWriter()

            for i, page in enumerate(reader.pages):
                # ✅ HAR SAHIFA O‘LCHAMI
                w = float(page.mediabox.width)
                h = float(page.mediabox.height)

                # ✅ Shu sahifa uchun overlay bytes
                overlay_bytes = build_overlay_pdf_bytes(w, h, text, qr_link)

                overlay_reader = PdfReader(BytesIO(overlay_bytes))
                overlay_page = overlay_reader.pages[0]

                # ✅ QK urish
                page.merge_page(overlay_page)
                writer.add_page(page)

                logger.debug(f"Sahifa {i + 1} QK urildi")

            # ✅ avval tmp ga yozamiz, keyin almashtiramiz (xavfsiz)
            with open(tmp_out, "wb") as f:
                writer.write(f)

            shutil.move(tmp_out, abs_pdf)
            logger.info(f"PDF muvaffaqiyatli QK urildi: {abs_pdf}")
            return True

    except Exception as e:
        logger.error(f"PDF QK urishda xatolik: {e}")
        raise
    finally:
        # tmp qolib ketgan bo‘lsa tozalab ketamiz
        try:
            if os.path.exists(tmp_out):
                os.remove(tmp_out)
        except Exception as e:
            logger.warning(f"tmp faylni o'chirishda xatolik: {e}")

# ==========================================================
# 4) JWT decode
# ==========================================================
def decode_jwt(token: str) -> dict:

    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception as e:
        logger.error(f"JWT dekodlashda xatolik: {e}")
        raise


def get_sso_redirect_uri(request) -> str:

    host = request.get_host()
    if "localhost" in host or "127.0.0.1" in host:
        return "http://localhost:8000/sso/callback/"
    return "https://report.imv.uz/sso/callback/"