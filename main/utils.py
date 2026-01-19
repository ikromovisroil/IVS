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




def decode_jwt(token):
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def get_sso_redirect_uri(request):
    host = request.get_host()
    if "localhost" in host or "127.0.0.1" in host:
        return "http://localhost:8000/sso/callback/"
    return "https://report.imv.uz/sso/callback/"

