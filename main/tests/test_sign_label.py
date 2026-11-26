"""PDF yozuvida har bir imzolovchining usuli: ERI yoki Face ID."""
import os
import tempfile

from django.test import TestCase
from django.utils import timezone
from PyPDF2 import PdfReader
from reportlab.pdfgen import canvas

from main.models import Deed
from main.testing import make_employee, make_org, make_region
from main.utils import sign_pdf_inplace


class SignLabelTests(TestCase):
    def setUp(self):
        org, region = make_org("worker"), make_region()
        _, self.sender = make_employee(org, region, last="Yuboruvchi")
        _, self.receiver = make_employee(org, region, last="Qabulqiluvchi")
        self.org = org

    def _stamp(self, **fields):
        now = timezone.now()
        deed = Deed.objects.create(sender=self.sender, receiver=self.receiver, organization=self.org,
                                   date_sender=now, date_receiver=now, **fields)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.pdf")
            c = canvas.Canvas(path, pagesize=(595, 842))
            c.showPage()
            c.save()
            sign_pdf_inplace(path, None, "x", deed.id)
            with open(path, "rb") as f:
                lines = PdfReader(f).pages[0].extract_text().splitlines()
        return [line for line in lines if "tizimi orqali" in line]

    def test_each_signer_has_own_method(self):
        first, second = self._stamp(sign_method_sender="faceid", sign_method_receiver="eri")
        self.assertIn("Face ID bilan", first)
        self.assertIn("ERI bilan", second)

    def test_old_deeds_without_method_show_eri(self):
        for line in self._stamp():
            self.assertIn("ERI bilan", line)
