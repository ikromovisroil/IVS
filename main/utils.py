import os
import shutil
import subprocess
import base64
import json
from datetime import datetime

from contextlib import contextmanager
from django.conf import settings
from django.utils import timezone
from django.urls import reverse

from reportlab.pdfgen import canvas
from reportlab.lib.colors import red

from PyPDF2 import PdfReader, PdfWriter

import qrcode
from qrcode.constants import ERROR_CORRECT_M


# ==========================================================
# 1) DOCX → PDF (LIBREOFFICE)  → (pdf_path, debug)
# ==========================================================
def convert_docx_to_pdf_libre(docx_path: str) -> tuple[str | None, str]:
    if not os.path.exists(docx_path):
        return None, f"DOCX topilmadi: {docx_path}"

    output_dir = os.path.dirname(docx_path)
    expected_pdf = os.path.splitext(docx_path)[0] + ".pdf"

    # soffice aniqlash
    if os.name == "nt":
        candidates = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]
        soffice = next((c for c in candidates if os.path.exists(c)), None)
    else:
        soffice = shutil.which("soffice") or shutil.which("libreoffice")

    if not soffice:
        return None, "LibreOffice (soffice) topilmadi. (sudo apt install libreoffice)"

    env = os.environ.copy()
    env.setdefault("HOME", output_dir)

    cmd = [
        soffice,
        "--headless",
        "--invisible",
        "--nodefault",
        "--nologo",
        "--nofirststartwizard",
        "--norestore",
        "--convert-to", "pdf",
        "--outdir", output_dir,
        docx_path
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            timeout=30
        )
    except Exception as e:
        return None, str(e)

    if proc.returncode != 0:
        return None, f"LibreOffice returncode={proc.returncode}"

    if os.path.exists(expected_pdf):
        return expected_pdf, "OK"

    # fallback
    pdfs = [f for f in os.listdir(output_dir) if f.lower().endswith(".pdf")]
    if pdfs:
        return os.path.join(output_dir, pdfs[0]), "OK (fallback)"

    return None, "PDF yaratilmadi"


# ==========================================================
# 2) Lock (PDF band bo‘lib qolmasin)
# ==========================================================
@contextmanager
def file_lock(lock_path: str, timeout: int = 10):
    start = timezone.now()
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            if (timezone.now() - start).total_seconds() > timeout:
                raise TimeoutError("PDF band (lock timeout)")
    try:
        yield
    finally:
        try:
            os.remove(lock_path)
        except Exception:
            pass


# ==========================================================
# 3) Overlay PDF yaratish (page_w/page_h bo‘yicha)
# ==========================================================
def create_overlay_pdf(page_w: float, page_h: float, text: str, qr_link: str, overlay_path: str):
    qr_png = overlay_path.replace(".pdf", "_qr.png")

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

    c = canvas.Canvas(overlay_path, pagesize=(page_w, page_h))
    c.setFillColor(red)

    # Yozuv (yuqori chap)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(10, page_h - 15, text)

    # QR (pastki markaz)
    qr_size = 65
    x_center = (page_w - qr_size) / 2
    c.drawImage(qr_png, x_center, 2, width=qr_size, height=qr_size, mask="auto")

    c.save()

    try:
        os.remove(qr_png)
    except Exception:
        pass


# ==========================================================
# 4) PDF ga imzo (HAR BIR SAHIFAGA) — inplace
# ==========================================================
def sign_pdf_inplace(pdf_path: str, request, approver_name: str, deed_id: int) -> None:
    """
    PDF ning o'zini o'ziga imzolaydi: HAR BIR SAHIFAGA QR + yozuv qo'yadi.
    QR skaner bo‘lsa: deed_status sahifaga olib boradi.
    """

    if not pdf_path or not os.path.exists(pdf_path):
        raise FileNotFoundError("PDF topilmadi")

    if not pdf_path.lower().endswith(".pdf"):
        raise ValueError("PDF noto‘g‘ri")

    abs_pdf = os.path.abspath(pdf_path)

    # QR link: status sahifa
    qr_link = request.build_absolute_uri(
        reverse("deed_status", args=[int(deed_id)])
    )

    text = (
        f"Ushbu hujjat {approver_name} tomonidan "
        f"{timezone.now().strftime('%Y-%m-%d %H:%M')} da tasdiqlandi."
    )

    lock_path = abs_pdf + ".lock"
    with file_lock(lock_path, timeout=10):
        reader = PdfReader(abs_pdf)
        if not reader.pages:
            raise ValueError("PDF bo‘sh")

        first = reader.pages[0]
        w = float(first.mediabox.width)
        h = float(first.mediabox.height)

        overlay_path = abs_pdf.replace(".pdf", "_overlay.pdf")
        tmp_out = abs_pdf.replace(".pdf", "_signed_tmp.pdf")

        # overlay 1 ta sahifa qilib yaratiladi (o‘lchami PDF bilan bir xil)
        create_overlay_pdf(w, h, text, qr_link, overlay_path)

        overlay_reader = PdfReader(overlay_path)
        overlay_page = overlay_reader.pages[0]

        writer = PdfWriter()
        for page in reader.pages:
            page.merge_page(overlay_page)   # har bir sahifaga
            writer.add_page(page)

        with open(tmp_out, "wb") as f:
            writer.write(f)

        # eski pdf o‘rniga yozish
        shutil.move(tmp_out, abs_pdf)

        try:
            os.remove(overlay_path)
        except Exception:
            pass


# ==========================================================
# JWT decode (o‘zingizniki)
# ==========================================================
def decode_jwt(token):
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def get_sso_redirect_uri(request):
    host = request.get_host()
    if "localhost" in host or "127.0.0.1" in host:
        return "http://localhost:8000/sso/callback/"
    return "https://report.imv.uz/sso/callback/"
