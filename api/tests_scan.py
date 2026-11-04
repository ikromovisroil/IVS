from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from main.models import Deed, DeedConsent, Technics
from main.testing import make_employee, make_org, make_region

URL = "/api/v1/scan/"
BASE = "https://report.example.uz"


@override_settings(SITE_BASE_URL=BASE, ALLOWED_HOSTS=["report.example.uz", "testserver"])
class ScanTests(TestCase):
    def setUp(self):
        cache.clear()
        self.org, self.region = make_org("worker"), make_region()
        self.user, self.emp = make_employee(self.org, self.region)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.tex = Technics.objects.create(
            name="Kompyuter", organization=self.org, region=self.region, serial="SN-1", inventory="INV-7",
        )
        self.creator = make_employee(self.org, self.region)[1]
        self.deed = Deed.objects.create(sender=self.emp, user=self.creator, organization=self.org,
                                        message_user="Yuborildi", file="deed/x.pdf")

    def scan(self, text, user=None):
        client = self.client
        if user is not None:
            client = APIClient()
            client.force_authenticate(user)
        return client.post(URL, {"text": text}, format="json")

    def technics_url(self, pk=None):
        return f"{BASE}/technics/{pk or self.tex.pk}/"

    def deed_url(self, code=None, pk=None):
        return f"{BASE}/deed/status/{code or self.deed.code}/{pk or self.deed.pk}/"

    # ---- tanish
    def test_requires_login(self):
        res = APIClient().post(URL, {"text": self.technics_url()}, format="json")
        self.assertEqual(res.status_code, 401)

    def test_unknown_text_is_rejected(self):
        for text in ("salom", "https://boshqa.example.com/technics/1/", "ftp://report.example.uz/technics/1/",
                     f"{BASE}/technics/abc/", f"{BASE}/admin/"):
            res = self.scan(text)
            self.assertEqual(res.status_code, 400, text)
            self.assertEqual(res.json()["type"], "unknown")

    def test_empty_text_is_validation_error(self):
        self.assertEqual(self.scan("").status_code, 400)

    def test_relative_path_is_accepted(self):
        self.assertEqual(self.scan(f"/technics/{self.tex.pk}/").json()["type"], "technics")

    # ---- texnika
    def test_technics_card(self):
        res = self.scan(self.technics_url())
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["type"], "technics")
        self.assertEqual(body["technics"]["id"], self.tex.pk)
        self.assertEqual(body["technics"]["inventory"], "INV-7")
        self.assertFalse(body["can_edit"])
        self.assertIsNone(body["detail"])           # tahrirlash huquqisiz to'liq ma'lumot berilmaydi

    def test_inactive_or_missing_technics_is_404(self):
        self.tex.is_active = False
        self.tex.save()
        self.assertEqual(self.scan(self.technics_url()).status_code, 404)
        self.assertEqual(self.scan(self.technics_url(999999)).status_code, 404)

    def test_can_edit_with_permission_in_scope(self):
        user, _ = make_employee(self.org, self.region, perms=("main.change_technics",))
        body = self.scan(self.technics_url(), user=user).json()
        self.assertTrue(body["can_edit"])
        self.assertEqual(body["detail"]["id"], self.tex.pk)

    def test_cannot_edit_other_organization_technics(self):
        other = Technics.objects.create(name="Begona", organization=make_org("worker"), region=self.region)
        user, _ = make_employee(self.org, self.region, perms=("main.change_technics",))
        body = self.scan(self.technics_url(other.pk), user=user).json()
        self.assertEqual(body["type"], "technics")   # kartani ko'radi (saytdagi QR sahifasi kabi)
        self.assertFalse(body["can_edit"])
        self.assertIsNone(body["detail"])

    def test_cannot_edit_other_region_technics(self):
        other = Technics.objects.create(name="Boshqa hudud", organization=self.org, region=make_region())
        user, _ = make_employee(self.org, self.region, perms=("main.change_technics",))
        self.assertFalse(self.scan(self.technics_url(other.pk), user=user).json()["can_edit"])

    # ---- hujjat
    def test_deed_info_for_stranger_has_no_file(self):
        stranger = make_employee(make_org("client"), make_region())[0]
        res = self.scan(self.deed_url(), user=stranger)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["type"], "deed")
        self.assertFalse(body["can_open"])
        self.assertIsNone(body["deed"]["file"])
        self.assertEqual(body["deed"]["code"], self.deed.code)
        self.assertEqual(body["deed"]["signers"][0]["status"], "viewed")
        self.assertEqual(body["deed"]["created_by"]["full_name"], self.creator.full_name)

    def test_deed_participant_can_open_and_gets_file(self):
        body = self.scan(self.deed_url()).json()          # self.emp — imzolovchi
        self.assertTrue(body["can_open"])
        self.assertTrue(body["deed"]["file"].endswith("deed/x.pdf"))

    def test_deed_lists_receiver_and_consents(self):
        receiver = make_employee(self.org, self.region)[1]
        self.deed.receiver = receiver
        self.deed.save()
        agreer = make_employee(self.org, self.region)[1]
        DeedConsent.objects.create(deed=self.deed, employee=agreer, status="approved", message="Ma'qul")
        body = self.scan(self.deed_url()).json()["deed"]
        self.assertEqual([s["role"] for s in body["signers"]], ["sender", "receiver"])
        self.assertEqual(body["consents"][0]["status"], "approved")
        self.assertEqual(body["consents"][0]["message"], "Ma'qul")
        self.assertIsNotNone(body["consents"][0]["date"])

    def test_wrong_code_or_id_is_404(self):
        self.assertEqual(self.scan(self.deed_url(code="XXXXXXXXXX")).status_code, 404)
        self.assertEqual(self.scan(self.deed_url(pk=999999)).status_code, 404)

    def test_scan_is_throttled(self):
        for _ in range(60):
            self.scan("salom")
        self.assertEqual(self.scan("salom").status_code, 429)
