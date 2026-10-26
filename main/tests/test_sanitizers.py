"""Hujjat matnidagi o'zbekcha apostroflar (o‘ g‘ ’) yagona bo'ladi."""
from django.test import SimpleTestCase

from main.sanitizers import normalize_uz_apostrophes, sanitize_deed_body


class UzApostropheTests(SimpleTestCase):
    def test_o_and_g_use_left_quote(self):
        for src in ("O'zbekiston", "Oʻzbekiston", "O’zbekiston", "O`zbekiston", "O‘zbekiston"):
            self.assertEqual(normalize_uz_apostrophes(src), "O‘zbekiston", src)
        self.assertEqual(normalize_uz_apostrophes("NARZULLAYEV O'G'LI"), "NARZULLAYEV O‘G‘LI")
        self.assertEqual(normalize_uz_apostrophes("Qoraqalpog'iston, ko'rsatish, bo'yicha"), "Qoraqalpog‘iston, ko‘rsatish, bo‘yicha")

    def test_tutuq_uses_right_quote(self):
        self.assertEqual(normalize_uz_apostrophes("a'zolari, ma‘lumot, Sa'dullayev"), "a’zolari, ma’lumot, Sa’dullayev")

    def test_tags_and_attributes_untouched(self):
        html = """<span style="font-family:'Times New Roman'">o'zbek</span><b id="g'x">g'oya</b>"""
        out = normalize_uz_apostrophes(html)
        self.assertIn("font-family:'Times New Roman'", out)
        self.assertIn('id="g\'x"', out)
        self.assertIn("o‘zbek", out)
        self.assertIn("g‘oya", out)

    def test_other_quotes_not_changed(self):
        self.assertEqual(normalize_uz_apostrophes("'quoted' and 'o' alone"), "'quoted' and 'o' alone")

    def test_sanitizer_applies_it(self):
        self.assertEqual(sanitize_deed_body("<div>O'zbekiston va g'oya</div>"), "<div>O‘zbekiston va g‘oya</div>")
