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
        self.assertEqual(d["orders_status"], {"viewed": 1, "process": 0, "done": 1, "finished": 1, "approved": 0, "closed": 0})
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


class DashboardScopeTests(TestCase):
    """status_employee huquqi bor xodim — o'z ko'rish doirasida; mijoz — faqat o'z omborxona arizalari va materiallari."""

    def setUp(self):
        from main.models import Material, MaterialCategory, MaterialEmployee
        from main.testing import make_employee, make_goal, make_org, make_region

        self.region = make_region()
        self.region2 = make_region()
        self.atm = make_org("worker")
        self.client_org = make_org("client")
        self.other_client = make_org("client")
        self.atm_goal = make_goal(self.atm)
        self.barn_goal = make_goal(self.client_org)
        self.other_barn_goal = make_goal(self.other_client)

        self.boss_user, self.boss = make_employee(self.atm, self.region, perms=["main.status_employee"], last="Boss")
        self.exec_user, self.executor = make_employee(self.atm, self.region, last="Ijrochi")
        self.cl_user, self.cl = make_employee(self.client_org, self.region, perms=["main.status_employee"], last="Mijoz")
        self.cl2_user, self.cl2 = make_employee(self.client_org, self.region, last="Mijoz2")
        self.oc_user, self.oc = make_employee(self.other_client, self.region, last="Begona")
        self.far_user, self.far = make_employee(self.client_org, self.region2, last="Uzoq")

        # ATM arizalari (maqsad — ATM tashkiloti) va omborxona arizalari
        self.o_atm_own = Order.objects.create(goal=self.atm_goal, sender=self.boss, receiver=self.executor, status="viewed")
        self.o_atm_client = Order.objects.create(goal=self.atm_goal, sender=self.cl, status="viewed")
        self.o_barn = Order.objects.create(goal=self.barn_goal, sender=self.cl2, status="viewed")
        self.o_barn_other = Order.objects.create(goal=self.other_barn_goal, sender=self.oc, status="viewed")
        self.o_barn_far = Order.objects.create(goal=self.barn_goal, sender=self.far, status="viewed")

        cat = MaterialCategory.objects.create(name="Kans", organization=self.client_org)
        self.keeper_user, self.keeper = make_employee(self.client_org, self.region, perms=["main.shop_employee"], last="Omborchi")
        MaterialEmployee.objects.create(employee=self.cl).category.set([cat])
        self.mat = Material.objects.create(name="Qog'oz", organization=self.client_org, category=cat, employee=self.keeper,
                                           number=5, price=100)
        Material.objects.create(name="Boshqa", organization=self.other_client, employee=self.oc, number=9, price=1)

    def get(self, user, **params):
        c = APIClient()
        c.force_authenticate(user)
        return c.get(URL, params)

    def _ids(self, r):
        return {o["id"] for o in r.json()["recent_orders"]}

    def test_without_stats_permission_forbidden(self):
        self.assertEqual(self.get(self.exec_user).status_code, 403)
        self.assertEqual(self.get(self.cl2_user).status_code, 403)

    def test_worker_sees_only_own_org_and_region(self):
        r = self.get(self.boss_user)
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertEqual(d["scope"]["mode"], "worker")
        # o'z tashkiloti yuborgan/ijro etgan ariza; mijozlarniki ko'rinmaydi
        self.assertEqual(self._ids(r), {self.o_atm_own.id})
        self.assertEqual(d["totals"]["organizations"], 1)
        # view_technics/view_material yo'q — bloklar yashirin
        self.assertIsNone(d["technics_status"])
        self.assertIsNone(d["materials"])
        self.assertIsNone(d["totals"]["technics"])

    def test_all_organization_defaults_to_own_and_widens_on_request(self):
        from main.testing import grant
        user = grant(self.boss_user, "main.all_organization", "main.all_region")
        everything = {o.id for o in (self.o_atm_own, self.o_atm_client, self.o_barn, self.o_barn_other, self.o_barn_far)}
        r = self.get(user)
        self.assertEqual(self._ids(r), {self.o_atm_own.id})            # standart — o'z tashkiloti
        self.assertTrue(r.json()["scope"]["can_widen"])
        r = self.get(user, scope="all")
        self.assertEqual(self._ids(r), everything)
        self.assertEqual(r.json()["scope"]["mode"], "all")

    def test_scope_all_ignored_without_permission(self):
        r = self.get(self.boss_user, scope="all")                       # all_organization yo'q
        self.assertEqual(self._ids(r), {self.o_atm_own.id})
        self.assertFalse(r.json()["scope"]["can_widen"])

    def test_superuser_defaults_to_own_organization(self):
        from main.testing import make_employee
        su, _ = make_employee(self.atm, self.region, superuser=True, last="Super")
        r = self.get(su)
        self.assertEqual(self._ids(r), {self.o_atm_own.id})
        self.assertEqual(r.json()["scope"]["organization"], self.atm.name)
        r = self.get(su, scope="all")
        self.assertEqual(len(self._ids(r)), 5)

    def test_client_superuser_cannot_widen(self):
        from main.testing import make_employee
        su, _ = make_employee(self.client_org, self.region, superuser=True, last="SuperMijoz")
        r = self.get(su, scope="all")
        d = r.json()
        self.assertEqual(d["scope"]["mode"], "client")
        self.assertFalse(d["scope"]["can_widen"])
        # superuserda all_region bor — hudud cheklanmaydi, lekin tashkilot doirasi faqat o'zi (boshqa mijoz yo'q)
        self.assertEqual(self._ids(r), {self.o_barn.id, self.o_barn_far.id})

    def test_all_region_alone_keeps_organization_limit(self):
        from main.testing import grant
        r = self.get(grant(self.boss_user, "main.all_region"))
        self.assertEqual(self._ids(r), {self.o_atm_own.id})

    def test_client_sees_only_own_barn_orders(self):
        from main.testing import grant
        user = grant(self.cl_user, "main.all_organization", "main.view_material")   # all_organization mijozga ta'sir qilmaydi
        r = self.get(user)
        d = r.json()
        self.assertEqual(d["scope"]["mode"], "client")
        self.assertEqual(d["scope"]["barn"], True)
        # ATM arizasi (o_atm_client), boshqa tashkilot va boshqa hudud arizalari ko'rinmaydi
        self.assertEqual(self._ids(r), {self.o_barn.id})
        self.assertEqual(d["totals"]["organizations"], 1)
        self.assertEqual(d["orders_status"]["viewed"], 1)

    def test_client_materials_block_follows_view_material(self):
        self.assertIsNone(self.get(self.cl_user).json()["materials"])
        from main.testing import grant
        d = self.get(grant(self.cl_user, "main.view_material", "main.all_material_employee")).json()
        self.assertEqual(d["materials"]["items"], 1)
        self.assertEqual(float(d["materials"]["total_sum"]), 500.0)
        self.mat.refresh_from_db()   # saqlashda nomdagi tutuq belgisi normallashtiriladi
        self.assertEqual([m["name"] for m in d["materials"]["top"]], [self.mat.name])
        self.assertEqual(d["totals"]["materials"], 1)   # boshqa tashkilot materiali kirmaydi
