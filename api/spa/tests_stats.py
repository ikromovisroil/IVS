"""api/spa/stats.py — Statistika: texnikalar, xodimlar, tashkilotlar (+ xodim modali)."""
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient

from django.test import TestCase

from main.models import Category, Group, Order, Technics
from main.testing import make_department, make_employee, make_goal, make_org, make_region

URL = "/api/v1/spa/stats/"


class StatsSpaTests(TestCase):
    def setUp(self):
        self.atm = make_org("worker")
        self.client_org = make_org("client")
        self.region = make_region()
        self.other_region = make_region()
        self.dep = make_department(self.client_org, self.region)
        self.user, self.emp = make_employee(org=self.atm, region=self.region, perms=["main.status_employee"])
        self.api = APIClient()
        self.api.force_authenticate(self.user)

        g1 = Group.objects.create(name="Kompyuter")
        g2 = Group.objects.create(name="Printer")
        c1 = Category.objects.create(group=g1, name="Noutbuk")
        c2 = Category.objects.create(group=g2, name="Lazer")
        for i in range(3):
            Technics.objects.create(group=g1, category=c1, organization=self.client_org, region=self.region,
                                    department=self.dep, name=f"N{i}", is_active=True)
        Technics.objects.create(group=g2, category=c2, organization=self.client_org, region=self.region, name="P", is_active=True)
        Technics.objects.create(group=g2, category=c2, organization=self.client_org, region=self.region, name="Old", is_active=False)

    # ---- ruxsat

    def test_requires_permission(self):
        user, _ = make_employee(org=self.atm, region=self.region)
        api = APIClient()
        api.force_authenticate(user)
        for path in ("technics/", "employees/", "organizations/"):
            self.assertEqual(api.get(URL + path).status_code, 403, path)

    def test_foreign_region_forbidden_without_all_region(self):
        r = self.api.get(URL + "technics/", {"organization": self.client_org.id, "region": self.other_region.id})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.api.get(URL + "employees/", {"region": "all"}).status_code, 403)

    def test_foreign_org_hidden_without_all_organization(self):
        r = self.api.get(URL + "technics/", {"organization": self.client_org.id, "region": self.region.id})
        self.assertEqual(r.status_code, 404)

    # ---- texnikalar

    def test_technics_defaults_to_own_org(self):
        r = self.api.get(URL + "technics/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["filters"]["organization"], str(self.atm.id))
        self.assertEqual(r.data["filters"]["region"], str(self.region.id))
        self.assertTrue(r.data["ready"])
        self.assertEqual(r.data["kpi"]["total"], 0)

    def test_technics_counts(self):
        user, _ = make_employee(org=self.atm, region=self.region, perms=["main.status_employee", "main.all_organization"])
        self.api.force_authenticate(user)
        r = self.api.get(URL + "technics/", {"organization": self.client_org.id, "region": self.region.id})
        self.assertEqual(r.status_code, 200)
        kpi = r.data["kpi"]
        self.assertEqual((kpi["total"], kpi["groups"], kpi["categories"], kpi["top_name"]), (4, 2, 2, "Kompyuter"))
        self.assertEqual(r.data["groups"][0]["share"], 75.0)
        # Department filtri
        r = self.api.get(URL + "technics/", {"organization": self.client_org.id, "region": self.region.id, "department": self.dep.id})
        self.assertEqual(r.data["kpi"]["total"], 3)

    def test_technics_missing_region_message(self):
        r = self.api.get(URL + "technics/", {"organization": self.atm.id, "region": ""})
        self.assertFalse(r.data["ready"])
        self.assertEqual(r.data["message"], "Tashkilot va hududni tanlang")

    # ---- xodimlar

    def _orders(self):
        goal = make_goal(self.atm, "Kompyuter ta'miri")
        _, receiver = make_employee(org=self.atm, region=self.region, first="Bekzod", last="Tursunov")
        _, sender = make_employee(org=self.client_org, region=self.region, department=self.dep, first="Sardor", last="Nazarov")
        for status in ("approved", "approved", "process", "rejected"):
            Order.objects.create(goal=goal, sender=sender, receiver=receiver, receiver_region=self.region, status=status, rating=5)
        old = Order.objects.create(goal=goal, sender=sender, receiver=receiver, receiver_region=self.region, status="finished")
        Order.objects.filter(pk=old.pk).update(date_creat=timezone.now() - timedelta(days=400))
        return goal, receiver, sender

    def test_employees_requires_region(self):
        self._orders()
        r = self.api.get(URL + "employees/")
        self.assertFalse(r.data["ready"])
        self.assertEqual(r.data["employees"], [])
        self.assertTrue(r.data["filters"]["date1"])          # joriy oy

    def test_employees_counts(self):
        _, receiver, _ = self._orders()
        r = self.api.get(URL + "employees/", {"region": self.region.id})
        self.assertEqual(r.status_code, 200)
        row = r.data["employees"][0]
        self.assertEqual(row["receiver_id"], receiver.id)
        self.assertEqual((row["approved_count"], row["process_count"], row["rejected_count"], row["total_count"]), (2, 1, 1, 5))
        self.assertEqual(r.data["goals"][0]["total"], 5)
        today = timezone.localdate().isoformat()
        r = self.api.get(URL + "employees/", {"region": self.region.id, "date1": today, "date2": today})
        self.assertEqual(r.data["employees"][0]["total_count"], 4)

    def test_bad_date(self):
        self.assertEqual(self.api.get(URL + "employees/", {"date1": "2026-13-45"}).status_code, 400)

    # ---- tashkilotlar

    def test_organizations(self):
        _, _, sender = self._orders()
        user, _ = make_employee(org=self.atm, region=self.region, perms=["main.status_employee", "main.all_organization"])
        self.api.force_authenticate(user)
        self.assertEqual(self.api.get(URL + "organizations/").data["searched"], False)
        r = self.api.get(URL + "organizations/", {"organization": self.client_org.id, "region": self.region.id})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["searched"])
        self.assertEqual(r.data["kind_label"], "ATMga")
        self.assertEqual(r.data["totals"], {"employees": 1, "orders": 4, "active_senders": 1})
        self.assertEqual(r.data["results"][0]["id"], sender.id)
        self.assertEqual(r.data["results"][0]["order_count"], 4)

        # Modal: main.views.org_status_employee (sessiya)
        web = self.client
        web.force_login(user)
        r = web.get(f"{URL}organizations/employee/{sender.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["total"], 5)
