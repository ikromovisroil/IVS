from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.colors import red
import qrcode
import base64
import json
from django.conf import settings
from django.utils import timezone
from contextlib import contextmanager
from qrcode.constants import ERROR_CORRECT_M
import os
import subprocess
from typing import Optional, Tuple
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import Color
from io import BytesIO

# =========================
# 1) PDF watermark chizish (overlay PDF yaratamiz)
# =========================
def _make_watermark_overlay(page_width: float, page_height: float, text: str) -> BytesIO:
    """
    Bitta sahifalik watermark overlay PDF (memoryda).
    """
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_width, page_height))

    # Yengil kulrang + shaffofroq (reportlab: alpha ishlashi muhitga bog'liq, lekin ko'p holatda OK)
    # Agar alpha ishlamasa ham, rangni juda och qilamiz.
    light_gray = Color(0.6, 0.6, 0.6, alpha=0.20)
    c.setFillColor(light_gray)

    # Markazga diagonal yozuv
    c.saveState()
    c.translate(page_width / 2, page_height / 2)
    c.rotate(35)

    # Font
    c.setFont("Helvetica-Bold", 52)
    c.drawCentredString(0, 0, text)

    c.restoreState()
    c.showPage()
    c.save()

    packet.seek(0)
    return packet


# =========================
# 2) PDF ga watermark bosish
# =========================
def apply_watermark_pdf(
    pdf_path: str,
    watermark_text: str = "TASDIQLANMAGAN",
    keep_original_backup: bool = True,
) -> Tuple[Optional[str], str]:
    """
    pdf_path faylni watermark qilib, natijani shu pdf_path'ning o'ziga yozadi.
    keep_original_backup=True bo'lsa: pdf_path.orig backup saqlaydi.
    """
    if not os.path.exists(pdf_path):
        return None, f"PDF topilmadi: {pdf_path}"

    backup_path = pdf_path + ".orig"

    try:
        # Backup faqat bir marta
        if keep_original_backup and not os.path.exists(backup_path):
            shutil.copy2(pdf_path, backup_path)

        reader = PdfReader(pdf_path)
        writer = PdfWriter()

        for page in reader.pages:
            # Sahifa o'lchami
            w = float(page.mediabox.width)
            h = float(page.mediabox.height)

            overlay_stream = _make_watermark_overlay(w, h, watermark_text)
            overlay_pdf = PdfReader(overlay_stream)
            overlay_page = overlay_pdf.pages[0]

            # Watermark merge
            page.merge_page(overlay_page)
            writer.add_page(page)

        # Vaqtinchalik yozib, keyin almashtirish (xavfsiz)
        tmp_path = pdf_path + ".tmp"
        with open(tmp_path, "wb") as f:
            writer.write(f)

        os.replace(tmp_path, pdf_path)
        return pdf_path, "OK (watermark applied)"
    except Exception as e:
        return None, f"Watermark error: {e}"


# =========================
# 3) Watermarkni olib tashlash (backupdan tiklash)
# =========================
def remove_watermark_pdf(pdf_path: str) -> Tuple[Optional[str], str]:
    """
    pdf_path.orig bo'lsa, shuni qaytarib pdf_path qiladi (watermark yo'qoladi).
    """
    backup_path = pdf_path + ".orig"
    if not os.path.exists(backup_path):
        return None, f"Backup topilmadi (remove qilib bo'lmaydi): {backup_path}"

    try:
        # watermarkli pdfni backupdan tiklaymiz
        os.replace(backup_path, pdf_path)
        return pdf_path, "OK (watermark removed)"
    except Exception as e:
        return None, f"Remove watermark error: {e}"


# =========================
# 4) DOCX → PDF (LibreOffice) + (kerak bo'lsa watermark)
# =========================
def convert_docx_to_pdf_libre(
    docx_path: str,
    add_watermark: bool = True,
    watermark_text: str = "TASDIQLANMAGAN",
) -> Tuple[Optional[str], str]:
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

    pdf_path = None
    if os.path.exists(expected_pdf):
        pdf_path = expected_pdf
    else:
        # fallback
        pdfs = [f for f in os.listdir(output_dir) if f.lower().endswith(".pdf")]
        if pdfs:
            pdf_path = os.path.join(output_dir, pdfs[0])

    if not pdf_path or not os.path.exists(pdf_path):
        return None, "PDF yaratilmadi"

    # Watermark qo'yish
    if add_watermark:
        wm_path, wm_msg = apply_watermark_pdf(pdf_path, watermark_text=watermark_text, keep_original_backup=True)
        if not wm_path:
            return pdf_path, f"PDF OK, lekin watermark qo'yilmadi: {wm_msg}"
        return wm_path, "OK (pdf+watermark)"

    return pdf_path, "OK (pdf only)"



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


def create_overlay_pdf(page_w: float, page_h: float, text: str, qr_link: str, overlay_path: str):
    qr_png = overlay_path.replace(".pdf", "_qr.png")

    # 🔥 QR ni qo‘lda yaratamiz
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
    qr_size = 60
    x_center = (page_w - qr_size) / 2
    c.drawImage(qr_png, x_center, 2, width=qr_size, height=qr_size, mask="auto")

    c.save()

    try:
        os.remove(qr_png)
    except Exception:
        pass


from django.urls import reverse
def sign_pdf_inplace(pdf_path: str, request, approver_name: str, deed_id: int) -> None:
    """
    PDF ning o'zini o'ziga imzolaydi: HAR BIR SAHIFAGA QR + yozuv qo'yadi.
    QR skaner bo‘lsa: /deed/status/<deed_id>/ ga olib boradi.
    """

    if not pdf_path or not os.path.exists(pdf_path):
        raise FileNotFoundError("PDF topilmadi")

    if not pdf_path.lower().endswith(".pdf"):
        raise ValueError("PDF noto‘g‘ri")

    abs_pdf = os.path.abspath(pdf_path)

    # ✅ QR endi STATUS sahifaga olib boradi
    qr_link = request.build_absolute_uri(
        reverse("deed_status", args=[int(deed_id)])
    )

    # Matn
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

        create_overlay_pdf(w, h, text, qr_link, overlay_path)

        overlay_reader = PdfReader(overlay_path)
        overlay_page = overlay_reader.pages[0]

        writer = PdfWriter()
        for page in reader.pages:
            page.merge_page(overlay_page)  # ✅ har bir sahifaga
            writer.add_page(page)

        with open(tmp_out, "wb") as f:
            writer.write(f)

        shutil.move(tmp_out, abs_pdf)

        try:
            os.remove(overlay_path)
        except Exception:
            pass


# ==========================================================
# 3) Original + Overlay PDF birlashtirish
# ==========================================================
def merge_pdf(original: str, overlay: str, output: str) -> None:
    reader = PdfReader(original)
    overlay_reader = PdfReader(overlay)
    writer = PdfWriter()

    overlay_page = overlay_reader.pages[0]

    for page in reader.pages:
        page.merge_page(overlay_page)
        writer.add_page(page)

    with open(output, "wb") as f:
        writer.write(f)


# =========================================================
# 4) Asosiy FUNKSIYA: DOCX → PDF → Overlay → Signed PDF
# ==========================================================
import shutil

def sign_pdf(pdf_path: str, request, approver_name: str) -> bool:

    if not os.path.exists(pdf_path):
        print("❌ PDF topilmadi:", pdf_path)
        return False

    pdf_path = os.path.abspath(pdf_path)

    text = (
        f"Ushbu hujjat {approver_name} tomonidan "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')} da tasdiqlandi."
    )

    media_root = os.path.abspath(settings.MEDIA_ROOT)
    rel_pdf = os.path.relpath(pdf_path, media_root).replace(os.sep, "/")

    # QR doim shu faylni ochadi (fayl nomi o‘zgarmaydi)
    qr_link = request.build_absolute_uri(settings.MEDIA_URL + rel_pdf)

    overlay_path = pdf_path.replace(".pdf", "_overlay.pdf")
    merged_tmp = pdf_path.replace(".pdf", "_merged_tmp.pdf")

    create_overlay_pdf(
        original_pdf_path=pdf_path,
        text=text,
        qr_link=qr_link,
        overlay_path=overlay_path
    )

    merge_pdf(
        original=pdf_path,
        overlay=overlay_path,
        output=merged_tmp
    )

    # 🔥 ASOSIY NUQTA
    # Imzolangan hujjat — eski faylning o‘ziga yoziladi
    shutil.move(merged_tmp, pdf_path)

    if os.path.exists(overlay_path):
        os.remove(overlay_path)

    return True



def decode_jwt(token):
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def get_sso_redirect_uri(request):
    host = request.get_host()
    if "localhost" in host or "127.0.0.1" in host:
        return "http://localhost:8000/sso/callback/"
    return "https://report.imv.uz/sso/callback/"

