import os
import shutil
import base64
import json
import time
import logging
from contextlib import contextmanager
from typing import Optional
from django.conf import settings  # <-- MUHIM!
from django.urls import reverse
from django.utils import timezone
from reportlab.pdfgen import canvas
from reportlab.lib.colors import red
from reportlab.lib.units import mm
from PyPDF2 import PdfReader, PdfWriter
import qrcode
from qrcode.constants import ERROR_CORRECT_M

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
# 2) Overlay PDF yaratish
# ==========================================================
def create_overlay_pdf(page_w: float, page_h: float, text: str, qr_link: str, overlay_path: str):

    qr_png = overlay_path.replace(".pdf", "_qr.png")

    # QR kod yaratish
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=6,
        border=1,
    )
    qr.add_data(qr_link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(qr_png)

    # PDF yaratish
    c = canvas.Canvas(overlay_path, pagesize=(page_w, page_h))
    c.setFillColor(red)

    # Yozuv (yuqori chap)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(10, page_h - 15, text)

    # QR kod (pastki markaz) - 15mm
    qr_size = 65
    x_center = (page_w - qr_size) / 2
    y_bottom = 5

    c.drawImage(qr_png, x_center, y_bottom, width=qr_size, height=qr_size, mask="auto")
    c.save()

    # QR kod faylini o'chirish
    try:
        os.remove(qr_png)
    except Exception as e:
        logger.warning(f"QR kod faylini o'chirishda xatolik: {e}")


# ==========================================================
# 3) PDF ga imzo (HAR BIR SAHIFAGA)
# ==========================================================
def sign_pdf_inplace(pdf_path: str, request, approver_name: str, deed_id: int) -> bool:

    if not pdf_path or not os.path.exists(pdf_path):
        logger.error(f"PDF topilmadi: {pdf_path}")
        raise FileNotFoundError(f"PDF topilmadi: {pdf_path}")

    if not pdf_path.lower().endswith(".pdf"):
        logger.error(f"PDF noto‘g‘ri format: {pdf_path}")
        raise ValueError("PDF noto‘g‘ri format")

    abs_pdf = os.path.abspath(pdf_path)
    logger.info(f"PDF imzolanmoqda: {abs_pdf}")

    # QR link: deed status sahifasi
    qr_link = request.build_absolute_uri(
        reverse("deed_status", args=[int(deed_id)])
    )

    text = (
        f"{approver_name} tomonidan "
        f"{timezone.now().strftime('%d.%m.%Y %H:%M')} da tasdiqlandi"
    )

    lock_path = abs_pdf + ".lock"

    try:
        with file_lock(lock_path, timeout=10):
            # PDF ni o'qish
            reader = PdfReader(abs_pdf)
            if not reader.pages:
                logger.error("PDF bo‘sh")
                raise ValueError("PDF bo‘sh")

            # Birinchi sahifa o'lchamini olish
            first = reader.pages[0]
            w = float(first.mediabox.width)
            h = float(first.mediabox.height)

            # Vaqtinchalik fayllar
            overlay_path = abs_pdf.replace(".pdf", "_overlay.pdf")
            tmp_out = abs_pdf.replace(".pdf", "_signed_tmp.pdf")

            try:
                # Overlay yaratish
                create_overlay_pdf(w, h, text, qr_link, overlay_path)

                overlay_reader = PdfReader(overlay_path)
                overlay_page = overlay_reader.pages[0]

                # Har bir sahifaga overlay qo'shish
                writer = PdfWriter()
                for i, page in enumerate(reader.pages):
                    page.merge_page(overlay_page)
                    writer.add_page(page)
                    logger.debug(f"Sahifa {i + 1} imzolandi")

                # Vaqtinchalik faylga yozish
                with open(tmp_out, "wb") as f:
                    writer.write(f)

                # Asl faylni imzolangan versiya bilan almashtirish
                shutil.move(tmp_out, abs_pdf)
                logger.info(f"PDF muvaffaqiyatli imzolandi: {abs_pdf}")

                return True

            finally:
                # Vaqtinchalik fayllarni tozalash
                for f in [overlay_path, tmp_out]:
                    try:
                        if os.path.exists(f):
                            os.remove(f)
                    except Exception as e:
                        logger.warning(f"Faylni o'chirishda xatolik: {f} - {e}")

    except Exception as e:
        logger.error(f"PDF imzolashda xatolik: {e}")
        raise


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