import os
import subprocess
from datetime import datetime

from reportlab.pdfgen import canvas
from reportlab.lib.colors import red
from PyPDF2 import PdfReader, PdfWriter
import qrcode

from django.conf import settings


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
    else:
        candidates = ["soffice", "libreoffice"]

    soffice = candidates[0]

    env = os.environ.copy()
    env.setdefault("HOME", output_dir)

    cmd = [
        soffice,
        "--headless",
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
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
    except Exception as e:
        return None, str(e)

    debug = (
        f"CMD: {' '.join(cmd)}\n"
        f"RC: {proc.returncode}\n"
        f"STDOUT:\n{proc.stdout}\n"
        f"STDERR:\n{proc.stderr}\n"
        f"EXPECTED: {expected_pdf}\n"
        f"EXISTS: {os.path.exists(expected_pdf)}"
    )

    if proc.returncode != 0:
        return None, debug

    if os.path.exists(expected_pdf):
        return expected_pdf, debug

    return None, debug


def create_overlay_pdf(original_pdf_path: str,text: str,qr_link: str,overlay_path: str):
    reader = PdfReader(original_pdf_path)
    first_page = reader.pages[0]

    width = float(first_page.mediabox.width)
    height = float(first_page.mediabox.height)

    # QR yaratamiz
    qr_png = overlay_path.replace(".pdf", "_qr.png")
    qrcode.make(qr_link).save(qr_png)

    c = canvas.Canvas(overlay_path, pagesize=(width, height))
    c.setFillColor(red)

    # Imzo matni (yuqori chap)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20, height - 30, text)

    # QR (pastki markaz)
    qr_size = 80
    x_center = (width - qr_size) / 2
    c.drawImage(
        qr_png,
        x_center,
        20,
        width=qr_size,
        height=qr_size,
        mask="auto"
    )

    c.save()

    if os.path.exists(qr_png):
        os.remove(qr_png)


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
def sign_pdf(pdf_path: str, request,approver_name: str) -> str | None:

    if not os.path.exists(pdf_path):
        print("❌ PDF topilmadi:", pdf_path)
        return None

    pdf_path = os.path.abspath(pdf_path)

    # =============================
    # Imzo matni
    # =============================
    text = (
        f"Ushbu hujjat {approver_name} tomonidan "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')} da tasdiqlandi."
    )

    # =============================
    # QR link
    # =============================
    media_root = os.path.abspath(settings.MEDIA_ROOT)
    rel_pdf = os.path.relpath(pdf_path, media_root).replace(os.sep, "/")
    qr_link = request.build_absolute_uri(settings.MEDIA_URL + rel_pdf)

    # =============================
    # Fayl yo‘llari
    # =============================
    overlay_path = pdf_path.replace(".pdf", "_overlay.pdf")
    final_path = pdf_path.replace(".pdf", "_signed.pdf")

    create_overlay_pdf(
        original_pdf_path=pdf_path,
        text=text,
        qr_link=qr_link,
        overlay_path=overlay_path
    )

    merge_pdf(
        original=pdf_path,
        overlay=overlay_path,
        output=final_path
    )

    if os.path.exists(overlay_path):
        os.remove(overlay_path)

    return os.path.relpath(final_path, media_root).replace(os.sep, "/")



import base64
import json


def decode_jwt(token):
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def get_sso_redirect_uri(request):
    host = request.get_host()
    if "localhost" in host or "127.0.0.1" in host:
        return "http://localhost:8000/sso/callback/"
    return "https://report.imv.uz/sso/callback/"

