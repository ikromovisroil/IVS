import os
import subprocess
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.colors import red
from PyPDF2 import PdfReader, PdfWriter
import qrcode
import shutil
import base64
import json
from django.conf import settings


# ==========================================================
# 1) DOCX → PDF (LIBREOFFICE)  → (pdf_path, debug)
# ==========================================================
def convert_docx_to_pdf_libre(docx_path: str) -> tuple[str | None, str]:
    if not os.path.exists(docx_path):
        return None, f"DOCX topilmadi: {docx_path}"

    output_dir = os.path.dirname(docx_path)
    expected_pdf = os.path.splitext(docx_path)[0] + ".pdf"

    # ✅ soffice aniqlash (tez + to'g'ri)
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
            stdout=subprocess.DEVNULL,   # ✅ stdout/stderr ni o'qimaslik tezroq
            stderr=subprocess.DEVNULL,
            env=env,
            timeout=30                  # ✅ osilib qolmasin
        )
    except Exception as e:
        return None, str(e)

    if proc.returncode != 0:
        return None, f"LibreOffice returncode={proc.returncode}"

    if os.path.exists(expected_pdf):
        return expected_pdf, "OK"

    # LibreOffice ba'zan nomni o'zgartirishi mumkin → fallback
    pdfs = [f for f in os.listdir(output_dir) if f.lower().endswith(".pdf")]
    if pdfs:
        return os.path.join(output_dir, pdfs[0]), "OK (fallback)"

    return None, "PDF yaratilmadi"




def decode_jwt(token):
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def get_sso_redirect_uri(request):
    host = request.get_host()
    if "localhost" in host or "127.0.0.1" in host:
        return "http://localhost:8000/sso/callback/"
    return "https://report.imv.uz/sso/callback/"

