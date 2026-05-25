import os
import qrcode
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
from .models import Deed


logger = logging.getLogger(__name__)


# ==========================================================
# 1) Lock
# ==========================================================
@contextmanager
def file_lock(lock_path: str, timeout: int = 10):
    start = time.time()
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            if time.time() - start > timeout:
                raise TimeoutError("PDF band (lock timeout) - %s" % lock_path)
            time.sleep(0.1)
    try:
        yield
    finally:
        try:
            os.remove(lock_path)
        except Exception as e:
            logger.warning("Lock faylni o'chirishda xatolik: %s", e)


# ==========================================================
# 2) Overlay PDF yaratish
# ==========================================================
def build_overlay_pdf_bytes(page_w: float, page_h: float, text: str, qr_link: str) -> bytes:
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
    try:
        img.save(qr_buf, format="PNG")
        qr_buf.seek(0)
        qr_reader = ImageReader(qr_buf)

        pdf_buf = BytesIO()
        c = canvas.Canvas(pdf_buf, pagesize=(page_w, page_h))

        c.setFillColor(red)
        c.setFont("Helvetica-Bold", 10)

        lines   = (text or "").splitlines()
        x       = 10
        y       = page_h - 15
        line_gap = 12

        for line in lines:
            c.drawString(x, y, line)
            y -= line_gap

        qr_size  = 65
        x_center = (page_w - qr_size) / 2
        c.drawImage(qr_reader, x_center, 5, width=qr_size, height=qr_size, mask="auto")

        c.showPage()
        c.save()
        return pdf_buf.getvalue()
    finally:
        qr_buf.close()


# ==========================================================
# 3) PDF ga imzo urish
# ==========================================================
def sign_pdf_inplace(pdf_path: str, request, approver_name: str, deed_id: int) -> bool:
    try:
        deed = Deed.objects.select_related("sender", "receiver").get(id=deed_id)
    except Deed.DoesNotExist:
        raise ValueError("Deed topilmadi: %s" % deed_id)

    if not pdf_path or not os.path.exists(pdf_path):
        logger.error("PDF topilmadi: %s", pdf_path)
        raise FileNotFoundError("PDF topilmadi: %s" % pdf_path)

    if not pdf_path.lower().endswith(".pdf"):
        logger.error("PDF noto'g'ri format: %s", pdf_path)
        raise ValueError("PDF noto'g'ri format")

    abs_pdf = os.path.abspath(pdf_path)
    logger.info("PDF imzo urilmoqda: %s", abs_pdf)

    qr_link = request.build_absolute_uri(
        reverse("deed_status", args=[deed.code, deed.id])
    )

    dt = timezone.localtime(timezone.now()).strftime("%d.%m.%Y %H:%M")
    if deed.receiver_id:
        text = (
            f"REPORT.YATM.UZ tizimi orqali ERI bilan {deed.sender.full_name} tomonidan {dt} da tasdiqlandi\n"
            f"REPORT.YATM.UZ tizimi orqali ERI bilan {deed.receiver.full_name} tomonidan {dt} da tasdiqlandi"
        )
    else:
        text = f"REPORT.YATM.UZ tizimi orqali ERI bilan {deed.sender.full_name} tomonidan {dt} da tasdiqlandi"

    lock_path = abs_pdf + ".lock"
    tmp_out   = abs_pdf.replace(".pdf", "_signed_tmp.pdf")

    try:
        with file_lock(lock_path, timeout=10):
            reader = PdfReader(abs_pdf)
            if not reader.pages:
                raise ValueError("PDF bo'sh")

            writer = PdfWriter()

            for i, page in enumerate(reader.pages):
                w = float(page.mediabox.width)
                h = float(page.mediabox.height)

                overlay_bytes  = build_overlay_pdf_bytes(w, h, text, qr_link)
                overlay_reader = PdfReader(BytesIO(overlay_bytes))
                overlay_page   = overlay_reader.pages[0]

                page.merge_page(overlay_page)
                writer.add_page(page)
                logger.debug("Sahifa %d imzo urildi", i + 1)

            with open(tmp_out, "wb") as f:
                writer.write(f)

            shutil.move(tmp_out, abs_pdf)
            logger.info("PDF muvaffaqiyatli imzo urildi: %s", abs_pdf)
            return True

    except Exception as e:
        logger.error("PDF imzo urishda xatolik: %s", e)
        raise
    finally:
        try:
            if os.path.exists(tmp_out):
                os.remove(tmp_out)
        except Exception as e:
            logger.warning("tmp faylni o'chirishda xatolik: %s", e)