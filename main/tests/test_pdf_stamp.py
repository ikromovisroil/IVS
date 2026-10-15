"""PDF ga QR va hujjat kodi urish (overlay)."""
import io

from django.test import SimpleTestCase
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from main.utils import build_overlay_pdf_bytes


def _blank_page():
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(595, 842))
    c.showPage()
    c.save()
    return PdfReader(io.BytesIO(buf.getvalue())).pages[0]


def _stamped_text(code):
    page = _blank_page()
    overlay = PdfReader(io.BytesIO(
        build_overlay_pdf_bytes(595, 842, "REPORT.YATM.UZ tizimi orqali sinov", "https://report.yatm.uz/x/1/", code=code)
    )).pages[0]
    page.merge_page(overlay)
    writer = PdfWriter()
    writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return PdfReader(io.BytesIO(out.getvalue())).pages[0].extract_text()


class PdfStampTests(SimpleTestCase):
    def test_deed_code_is_written_next_to_qr(self):
        text = _stamped_text("MP-123456")
        self.assertIn("MP-123456", text)
        self.assertIn("REPORT.YATM.UZ", text)

    def test_empty_code_writes_nothing_extra(self):
        text = _stamped_text("")
        self.assertIn("REPORT.YATM.UZ", text)
        self.assertNotIn("MP-", text)
