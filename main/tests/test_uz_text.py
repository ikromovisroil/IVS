"""Hujjatlardagi lavozim yozilishi: faqat birinchi harf katta."""
from django.template import Context, Template
from django.test import SimpleTestCase

from main.templatetags.uz_text import rank_case


class RankCaseTests(SimpleTestCase):
    def test_sentence_case(self):
        cases = {
            "Bosh Mutaxassis": "Bosh mutaxassis",
            "DIREKTOR": "Direktor",
            "Direktor Birinchi O'rinbosari": "Direktor birinchi o'rinbosari",
            "2-toifali Mutaxassis": "2-toifali mutaxassis",
            "ATM Mutaxassisi": "ATM mutaxassisi",
            "  Boshqarma  Boshlig'i ": "Boshqarma  boshlig'i",
            "": "",
            None: "",
        }
        for src, want in cases.items():
            self.assertEqual(rank_case(src), want, src)

    def test_template_filter(self):
        out = Template("{% load uz_text %}{{ r|rank_case }}").render(Context({"r": "Bosh Mutaxassis"}))
        self.assertEqual(out, "Bosh mutaxassis")
