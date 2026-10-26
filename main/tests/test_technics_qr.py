"""Texnika QR kodi (manzil SITE_BASE_URL dan), qayta yaratish buyrug'i, ochiq sahifa, qurilma oynasidagi xodim."""
import io
import os
import shutil
import tempfile

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from main.models import Structure, Technics
from main.testing import make_employee, make_org, make_region

class TempMediaMixin:
    """Har bir test uchun alohida vaqtinchalik MEDIA_ROOT (testlar orasida fayl nomlari to'qnashmasligi uchun)."""

    def setUp(self):
        super().setUp()
        self.media_root = tempfile.mkdtemp(prefix="ivs_test_media_")
        self.addCleanup(shutil.rmtree, self.media_root, True)
        override = override_settings(MEDIA_ROOT=self.media_root)
        override.enable()
        self.addCleanup(override.disable)


@override_settings(SITE_BASE_URL="https://example.test/")
class TechnicsQrTests(TempMediaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.org = make_org("client")
        self.region = make_region()

    def _technics(self, **kw):
        return Technics.objects.create(name="Kompyuter", organization=self.org, **kw)

    def test_qr_url_uses_site_base_url(self):
        tech = self._technics()
        self.assertEqual(tech.get_qr_data(), f"https://example.test/technics/{tech.pk}/")

    def test_qr_image_created_on_save(self):
        tech = self._technics()
        self.assertTrue(tech.qr_code)
        self.assertTrue(os.path.exists(tech.qr_code.path))

    def test_regenerate_command_rewrites_image_without_leftovers(self):
        tech = self._technics()
        with override_settings(SITE_BASE_URL="https://yangi.test"):
            call_command("regenerate_technics_qr", stdout=io.StringIO())
        tech.refresh_from_db()
        self.assertEqual(os.path.basename(tech.qr_code.name), f"technics_{tech.pk}.png")
        leftovers = [f for f in os.listdir(os.path.join(self.media_root, "qk")) if f.startswith(f"technics_{tech.pk}")]
        self.assertEqual(len(leftovers), 1)

    def test_regenerate_dry_run_changes_nothing(self):
        tech = self._technics()
        before = open(tech.qr_code.path, "rb").read()
        with override_settings(SITE_BASE_URL="https://yangi.test"):
            call_command("regenerate_technics_qr", "--dry-run", stdout=io.StringIO())
        tech.refresh_from_db()
        self.assertEqual(open(tech.qr_code.path, "rb").read(), before)

    def test_detail_page_is_public(self):
        tech = self._technics()
        response = self.client.get(reverse("technics_detail", args=[tech.pk]))
        self.assertEqual(response.status_code, 200)

    def test_inactive_technics_page_not_found(self):
        tech = self._technics(is_active=False)
        self.assertEqual(self.client.get(reverse("technics_detail", args=[tech.pk])).status_code, 404)


