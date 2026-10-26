"""api/spa/people.py — Profil, Hujjatlar qidiruvi, tahrirlash ruxsati, ilovalar, Gateway orqali xodim qo'shish."""
import shutil
import tempfile
from unittest import mock

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from main.models import Deed, DeedConsent, DeedFiles, Employee
from main.testing import make_employee, make_org, make_region

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class PeopleSpaTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.org = make_org("worker")
        self.other = make_org("client")
        self.region = make_region()
        self.user, self.emp = make_employee(org=self.org, region=self.region, first="Aziz", last="Karimov")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _deed(self, **kw):
        d = Deed(organization=kw.pop("organization", self.org), user=kw.pop("user", self.emp), **kw)
        d.file.save("t.pdf", ContentFile(b"%PDF-1.4"), save=False)
        d.save()
        return d

    # ---- profil

    def test_profile(self):
        self.user.email = "a@b.uz"
        self.user.save()
        r = self.client.get("/api/v1/spa/people/profile/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["full_name"], self.emp.full_name)
        self.assertEqual(r.data["organization_name"], self.org.name)
        self.assertEqual(r.data["email"], "a@b.uz")

    def test_profile_requires_login(self):
        self.assertIn(APIClient().get("/api/v1/spa/people/profile/").status_code, (401, 403))

    # ---- hujjatlar

    def test_files_empty_without_filter(self):
        self._deed(status="act")
        r = self.client.get("/api/v1/spa/people/files/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 0)

    def test_files_filters(self):
        _, sender = make_employee(org=self.other, first="Bekzod", last="Tursunov")
        a = self._deed(status="act", sender=sender, status_sender="approved")
        b = self._deed(status="svod", organization=self.other)
        DeedConsent.objects.create(deed=a, employee=sender, status="rejected", message="yo'q")
        DeedFiles.objects.create(deed=a, file=ContentFile(b"x", name="i.pdf"))

        r = self.client.get("/api/v1/spa/people/files/", {"status": "act"})
        self.assertEqual([x["id"] for x in r.data["results"]], [a.id])
        row = r.data["results"][0]
        self.assertEqual(row["overall"], "approved")
        self.assertEqual(row["attachments_count"], 1)
        self.assertEqual(row["consents"][0]["status"], "rejected")

        r = self.client.get("/api/v1/spa/people/files/", {"organization": self.other.id})
        self.assertEqual([x["id"] for x in r.data["results"]], [b.id])
        r = self.client.get("/api/v1/spa/people/files/", {"name": "tursunov"})
        self.assertEqual([x["id"] for x in r.data["results"]], [a.id])
        r = self.client.get("/api/v1/spa/people/files/", {"name": a.code})
        self.assertEqual([x["id"] for x in r.data["results"]], [a.id])
        r = self.client.get("/api/v1/spa/people/files/", {"date1": "bad-date"})
        self.assertEqual(r.status_code, 200)

    def test_files_filter_by_overall_state(self):
        _, signer = make_employee(org=self.other, first="Bekzod", last="Tursunov")
        ok = self._deed(status="act", sender=signer, status_sender="approved")
        bad = self._deed(status="act", sender=signer, status_sender="rejected")
        wait = self._deed(status="act", sender=signer)
        half = self._deed(status="act", sender=signer, receiver=signer, status_sender="approved", status_receiver="viewed")
        both = self._deed(status="act", sender=signer, receiver=signer, status_sender="approved", status_receiver="approved")

        def ids(overall):
            r = self.client.get("/api/v1/spa/people/files/", {"overall": overall})
            self.assertEqual(r.status_code, 200)
            for row in r.data["results"]:
                self.assertEqual(row["overall"], overall)
            return {x["id"] for x in r.data["results"]}

        self.assertEqual(ids("approved"), {ok.id, both.id})
        self.assertEqual(ids("rejected"), {bad.id})
        self.assertEqual(ids("pending"), {wait.id, half.id})
        # noto'g'ri qiymat — filtr berilmagandek (bo'sh ro'yxat)
        self.assertEqual(self.client.get("/api/v1/spa/people/files/", {"overall": "x"}).data["count"], 0)

    def test_files_filters_refs(self):
        r = self.client.get("/api/v1/spa/people/files/filters/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual({o["id"] for o in r.data["organizations"]}, {self.org.id, self.other.id})
        self.assertIn("act", [s["value"] for s in r.data["statuses"]])

    def test_toggle_user_edit_requires_change_deed(self):
        d = self._deed(status="act", user_edit=True)
        url = f"/api/v1/spa/people/files/{d.id}/toggle-user-edit/"
        self.assertEqual(self.client.post(url).status_code, 403)

        user, _ = make_employee(org=self.org, perms=("main.change_deed",))
        c = APIClient()
        c.force_authenticate(user)
        r = c.post(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, {"success": True, "user_edit": False})
        d.refresh_from_db()
        self.assertFalse(d.user_edit)

    def test_attachments(self):
        d = self._deed(status="act")
        url = f"/api/v1/spa/people/files/{d.id}/attachments/"
        self.assertEqual(self.client.get(url).status_code, 404)
        DeedFiles.objects.create(deed=d, file=ContentFile(b"one", name="a.pdf"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r["Content-Disposition"])
        DeedFiles.objects.create(deed=d, file=ContentFile(b"two", name="b.pdf"))
        r = self.client.get(url)
        self.assertEqual(r["Content-Type"], "application/zip")

    # ---- Gateway orqali qo'shish

    def test_gateway_create_requires_permission(self):
        r = self.client.post("/api/v1/spa/people/employees/gateway-create/", {"pinfl": "12345678901234"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_gateway_create_messages(self):
        user, _ = make_employee(org=self.org, perms=("main.add_employee",))
        c = APIClient()
        c.force_authenticate(user)
        url = "/api/v1/spa/people/employees/gateway-create/"
        r = c.post(url, {"pinfl": ""}, format="json")
        self.assertEqual((r.status_code, r.data["detail"]), (400, "PINFL kiritilmadi"))

        make_employee(org=self.org, pinfl="12345678901234")
        r = c.post(url, {"pinfl": "12345678901234"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("allaqachon", r.data["detail"])

        with mock.patch("main.gateway.GatewayClient.current_citizen", side_effect=RuntimeError("down")):
            r = c.post(url, {"pinfl": "99999999999999"}, format="json")
        self.assertEqual(r.status_code, 502)

        with mock.patch("main.gateway.GatewayClient.current_citizen", return_value={"result": {"positions": []}}):
            r = c.post(url, {"pinfl": "99999999999999"}, format="json")
        self.assertEqual((r.status_code, r.data["detail"]), (400, "Gatewayda ish joyi topilmadi"))
        self.assertFalse(Employee.objects.filter(pinfl="99999999999999").exists())
