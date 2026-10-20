from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from django.test import TestCase

from main.models import Employee, Goal, Order, Organization, Technics

URL = "/api/v1/spa/dashboard/overview/"


class DashboardOverviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        org = Organization.objects.create(name="ATM", type="worker")
        cls.admin = User.objects.create_superuser("boss", password="x")
        cls.user = User.objects.create_user("oddiy", password="x")
        # Employee foydalanuvchi bilan birga signal orqali yaratiladi
        sender, _ = Employee.objects.update_or_create(user=cls.user, defaults={"last_name": "Aliyev", "first_name": "Vali", "organization": org})
        executor, _ = Employee.objects.update_or_create(user=cls.admin, defaults={"last_name": "Karimov", "first_name": "Aziz", "organization": org})
        goal = Goal.objects.create(name="Printer ta'miri", organization=org)

        now = timezone.now()
        o1 = Order.objects.create(goal=goal, sender=sender, receiver=executor, status="viewed")
        o2 = Order.objects.create(goal=goal, sender=sender, receiver=executor, status="finished", rating=4)
        Order.objects.filter(pk=o2.pk).update(date_process=now - timedelta(hours=5), date_finished=now - timedelta(hours=1))
        # oldingi davrdagi ariza (30 kunlik davr uchun solishtirish)
        o3 = Order.objects.create(goal=goal, sender=sender, status="canceled")
        Order.objects.filter(pk=o3.pk).update(date_creat=now - timedelta(days=40))
        cls.orders = (o1, o2, o3)

        Technics.objects.create(name="PC", status="active", organization=org)
        Technics.objects.create(name="Printer", status="repair", organization=org)
        Technics.objects.create(name="Eski", status="defect", organization=org, is_active=False)

    def get(self, user, **params):
        c = APIClient()
        c.force_authenticate(user)
        return c.get(URL, params)

    def test_only_superuser(self):
        self.assertEqual(self.get(self.user).status_code, 403)
        self.assertEqual(APIClient().get(URL).status_code, 401)

    def test_overview_numbers(self):
        r = self.get(self.admin)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["period"]["days"], 30)
        self.assertEqual(d["kpis"]["orders_new"], {"value": 2, "prev": 1})
        self.assertEqual(d["kpis"]["orders_done"]["value"], 1)
        self.assertEqual(d["kpis"]["avg_hours"]["value"], 4.0)
        self.assertEqual(d["orders_status"], {"viewed": 1, "process": 0, "done": 1, "closed": 0})
        self.assertEqual(d["technics_status"], {"active": 1, "free": 0, "repair": 1, "defect": 0})
        self.assertEqual(d["technics_groups"], [{"name": "Turi ko'rsatilmagan", "count": 2}])
        self.assertEqual(d["top_executors"][0]["done"], 1)
        self.assertEqual(d["top_executors"][0]["rating"], 4.0)
        self.assertEqual(d["top_goals"][0], {"name": "Printer ta'miri", "barn": False, "count": 2})
        self.assertEqual(len(d["recent_orders"]), 3)
        self.assertEqual(sum(t["created"] for t in d["trend"]), 2)

    def test_periods(self):
        self.assertEqual(len(self.get(self.admin, days=7).json()["trend"]), 7)
        weekly = self.get(self.admin, days=90).json()
        self.assertEqual(weekly["period"]["bucket_days"], 7)
        self.assertEqual(len(weekly["trend"]), 13)  # 13 hafta — 90 kunlik KPI davrini to'liq qamraydi
        self.assertEqual(self.get(self.admin, days="abc").json()["period"]["days"], 30)
        self.assertEqual(self.get(self.admin, days=365).json()["period"]["days"], 30)
