"""/api/v1/spa/reports/ — "Hisobotlar" bo'limi (api/spa/reports.py).

    .venv/Scripts/python.exe manage.py test api.spa.tests_reports
"""
import base64
from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from main.testing import make_employee
from main.models import (
    Contract, Deed, Department, Employee, Goal, Liable, Material, Order, OrderMaterial, Organization, Rank, Region, Unit,
)

URL = "/api/v1/spa/reports/"


def make_emp(org, region, dep=None, rank=None, perms=(), last="Familiya"):
    user, emp = make_employee(org=org, region=region, department=dep, perms=perms, last=last)
    if rank:
        emp.rank = rank
        emp.save()
    return emp


@mock.patch("main.views.notify_deed_sender", lambda *a, **k: None)
@mock.patch("main.views.notify_deed_watchers", lambda *a, **k: None)
@mock.patch("main.views._save_deed_pdf", lambda deed: None)
class ReportsApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name="Toshkent shahri")
        cls.atm = Organization.objects.create(name="ATM", type="worker")
        cls.client_org = Organization.objects.create(name="Mijoz", type="client", contract="12-sonli shartnoma")
        cls.dep283 = Department.objects.create(id=283, name="Rahbariyat", organization=cls.atm, region=cls.region)
        cls.rank = Rank.objects.create(name="Muhandis")

        cls.worker = make_emp(cls.atm, cls.region, rank=cls.rank, last="Ishchi",
                              perms=("main.shop_employee", "main.change_order", "main.material_service"))
        cls.boss = make_emp(cls.atm, cls.region, dep=cls.dep283, rank=cls.rank, last="Rahbar")
        cls.client_user = make_emp(cls.client_org, cls.region, last="Mijoz")

        # Dalolatnoma ruxsati: kamida bitta shartnoma biriktirilgan (Employee.can_make_document)
        liable = Liable.objects.create(employee=cls.worker)
        liable.contracts.add(Contract.objects.create(name="1.1. Kompyuterlar"))

        # Yakunlangan ariza + material (Svod uchun)
        unit = Unit.objects.create(name="dona")
        mat = Material.objects.create(name="Kartrij", code="1C-1", price=100, unit=unit, organization=cls.atm, employee=cls.worker)
        goal = Goal.objects.create(name="Nosozlik", organization=cls.atm)
        order = Order.objects.create(goal=goal, sender=cls.client_user, receiver=cls.worker, status="finished")
        Order.objects.filter(pk=order.pk).update(date_finished=timezone.now() - timedelta(days=1))
        OrderMaterial.objects.create(order=order, material=mat, number=3)

    def login(self, emp):
        self.client.force_login(emp.user)

    # ── meta / ruxsatlar ──
    def test_meta_requires_login(self):
        self.assertIn(self.client.get(URL).status_code, (401, 403))

    def test_meta_permissions(self):
        self.login(self.worker)
        data = self.client.get(URL).json()
        self.assertEqual(data["reports"], {"document": True, "svod": True, "reestr": True, "akt": True, "service": True})
        self.assertEqual(data["employee"]["full_name"], self.worker.full_name)

        self.login(self.client_user)
        self.assertFalse(any(self.client.get(URL).json()["reports"].values()))

    def test_form_forbidden_without_permission(self):
        self.login(self.client_user)
        for kind in ("document", "svod", "reestr", "akt", "service"):
            self.assertEqual(self.client.get(f"{URL}{kind}/form/").status_code, 403, kind)
        self.assertEqual(self.client.get(f"{URL}nope/form/").status_code, 404)

    def test_svod_form_lists(self):
        self.login(self.worker)
        data = self.client.get(f"{URL}svod/form/").json()
        self.assertEqual([o["id"] for o in data["organizations"]], [self.client_org.id])  # ATM Svodga kirmaydi
        self.assertEqual([e["id"] for e in data["senders"]], [self.boss.id])  # department 283

    def test_service_form_period(self):
        self.login(self.worker)
        data = self.client.get(f"{URL}service/form/").json()
        self.assertEqual(data["my_org"]["id"], self.atm.id)
        self.assertIn(data["report_quarter"], ("I", "II", "III", "IV"))

    # ── eski AJAX funksiyalari ──
    def test_svod_materials_passthrough(self):
        self.login(self.worker)
        today = timezone.localdate()
        res = self.client.get(f"{URL}data/svod-materials/", {
            "organizations[]": [self.client_org.id], "region": "all",
            "date1": (today - timedelta(days=10)).isoformat(), "date2": today.isoformat(),
        })
        self.assertEqual(res.status_code, 200)
        orgs = res.json()["organizations"]
        self.assertEqual(orgs[0]["organization_name"], "Mijoz")
        item = orgs[0]["regions"][0]["materials"][0]
        self.assertEqual((item["material__name"], item["total_number"], item["total_sum"]), ("Kartrij", 3.0, 300.0))

    def test_unknown_data_404(self):
        self.login(self.worker)
        self.assertEqual(self.client.get(f"{URL}data/nope/").status_code, 404)

    @mock.patch("main.ajax_views.html_to_pdf_bytes", return_value=b"%PDF-1.4 test")
    def test_pdf(self, _pdf):
        self.login(self.worker)
        res = self.client.post(f"{URL}pdf/", {"body_html": "<b>Salom</b>", "orientation": "Portrait", "filename": "svod"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/pdf")

    # ── Imzolashga yuborish (main.views.*_post) ──
    def test_submit_error_message(self):
        self.login(self.worker)
        res = self.client.post(f"{URL}svod/submit/", {"organizations[]": [self.client_org.id]})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["detail"], "Imzolovchi xodim tanlanmadi yoki ruxsat etilmagan")
        self.assertFalse(Deed.objects.exists())

    def test_submit_creates_deed(self):
        self.login(self.worker)
        body = base64.b64encode("<div>Yakuniy hisobot</div>".encode()).decode()
        res = self.client.post(f"{URL}svod/submit/", {
            "organizations[]": [self.client_org.id], "sender": self.boss.id, "message": "izoh", "body_encoded": body,
        })
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.json()["detail"], "Imzolashga yuborildi")
        deed = Deed.objects.get()
        self.assertEqual((deed.status, deed.sender_id, deed.organization_id), ("svod", self.boss.id, self.client_org.id))

    def test_submit_forbidden(self):
        self.login(self.client_user)
        self.assertEqual(self.client.post(f"{URL}document/submit/", {}).status_code, 403)
