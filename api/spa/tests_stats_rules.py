"""
Statistika (api/spa/stats.py) biznes qoidalari: tashkilot/hudud doirasi, majburiy filtrlar, saralash, sahifalash,
sana oralig'i, ATM/omborxona turi. (Eski HTML sahifalar o'chirilgach, shu qoidalar API orqali tekshiriladi.)
"""
from datetime import datetime

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from main.models import Category, Department, Directorate, Division, Goal, Group, Order, Technics
from main.testing import make_employee, make_goal, make_org, make_region

URL = "/api/v1/spa/stats/"
STATS = ["main.status_employee"]


def at(year, month, day):
    return timezone.make_aware(datetime(year, month, day, 12, 0))


def api_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


# ───────────────────────────── Tashkilotlar ─────────────────────────────

class OrganizationStatsTests(TestCase):
    def setUp(self):
        self.worker = make_org("worker")
        self.client_org = make_org("client")
        self.other_org = make_org("client")
        self.region = make_region()
        self.dept_a = Department.objects.create(name="Dep A", organization=self.client_org, region=self.region)
        self.dept_b = Department.objects.create(name="Dep B", organization=self.client_org, region=self.region)
        self.dir_a = Directorate.objects.create(name="Boshqarma A", department=self.dept_a)
        self.div_a = Division.objects.create(name="Bo'lim A", directorate=self.dir_a)
        self.atm_goal = make_goal(self.worker)
        self.barn_goal = make_goal(self.client_org)

        self.viewer_user, self.viewer = make_employee(self.worker, self.region, perms=STATS + ["main.all_organization"])
        _, self.in_div = make_employee(self.client_org, self.region, first="Bo'lim", last="Xodimi")
        self.in_div.division = self.div_a
        self.in_div.save()
        _, self.in_dep_b = make_employee(self.client_org, self.region, first="DepB", last="Xodimi")
        self.in_dep_b.department = self.dept_b
        self.in_dep_b.save()
        _, self.idle = make_employee(self.client_org, self.region, first="Hech", last="Yozmagan")
        make_employee(self.other_org, self.region, first="Begona", last="Tashkilot")
        make_employee(self.client_org, self.region, first="Ketgan", last="Xodim", active=False)
        self.api = api_for(self.viewer_user)

    def _order(self, sender, goal, when):
        order = Order.objects.create(sender=sender, goal=goal, status="viewed")
        Order.objects.filter(pk=order.pk).update(date_creat=when)

    def _get(self, **params):
        params.setdefault("organization", self.client_org.id)
        params.setdefault("region", self.region.id)
        params.setdefault("date1", "2026-10-01")
        params.setdefault("date2", "2026-10-31")
        return self.api.get(URL + "organizations/", params)

    def _names(self, response):
        return [row["full_name"] for row in response.data["results"]]

    def test_nothing_searched_without_params(self):
        response = self.api.get(URL + "organizations/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["searched"])
        self.assertIsNone(response.data["message"])
        self.assertEqual(response.data["totals"], {"employees": 0, "orders": 0, "active_senders": 0})

    def test_organization_and_region_required(self):
        for params in ({"organization": self.client_org.id}, {"region": self.region.id}):
            response = self.api.get(URL + "organizations/", {**params, "date1": "2026-10-01"})
            self.assertFalse(response.data["searched"], params)
            self.assertEqual(response.data["message"], "Tashkilot va hududni tanlang")

    def test_counts_orders_in_date_range_for_atm_viewer(self):
        for day in (5, 20):
            self._order(self.in_div, self.atm_goal, at(2026, 10, day))
        self._order(self.in_div, self.barn_goal, at(2026, 10, 31))            # omborxona: ATM xodimi ko'rmaydi
        self._order(self.in_div, self.atm_goal, at(2026, 9, 30))              # oraliqdan oldin
        self._order(self.in_div, self.atm_goal, at(2026, 11, 1))              # oraliqdan keyin
        self._order(self.in_dep_b, self.barn_goal, at(2026, 10, 10))
        response = self._get()
        self.assertEqual(self._names(response), [self.in_div.full_name])
        self.assertEqual(response.data["results"][0]["order_count"], 2)
        self.assertEqual(response.data["kind_label"], "ATMga")
        self.assertEqual(response.data["totals"]["orders"], 2)

    def test_non_atm_viewer_counts_warehouse_orders(self):
        self._order(self.in_div, self.atm_goal, at(2026, 10, 5))
        self._order(self.in_div, self.barn_goal, at(2026, 10, 6))
        self._order(self.in_div, self.barn_goal, at(2026, 10, 7))
        self._order(self.in_dep_b, self.barn_goal, at(2026, 10, 8))
        user, _ = make_employee(self.client_org, self.region, perms=STATS)
        response = api_for(user).get(URL + "organizations/", {
            "organization": self.client_org.id, "region": self.region.id, "date1": "2026-10-01", "date2": "2026-10-31"})
        self.assertEqual(response.data["kind_label"], "Omborxonaga")
        counts = {row["full_name"]: row["order_count"] for row in response.data["results"]}
        self.assertEqual(counts, {self.in_div.full_name: 2, self.in_dep_b.full_name: 1})

    def test_only_senders_listed_but_totals_count_all_active_staff(self):
        self._order(self.in_div, self.atm_goal, at(2026, 10, 5))
        self._order(self.in_dep_b, self.atm_goal, at(2026, 9, 5))             # davrdan tashqarida
        response = self._get()
        self.assertEqual(self._names(response), [self.in_div.full_name])
        self.assertEqual(response.data["totals"]["employees"], 3)             # in_div, in_dep_b, idle (nofaol va begona yo'q)
        self.assertEqual(response.data["totals"]["active_senders"], 1)

    def test_nobody_sent_orders(self):
        response = self._get()
        self.assertEqual(response.data["results"], [])
        self.assertEqual(response.data["count"], 0)
        self.assertTrue(response.data["searched"])

    def test_ordered_by_count_then_structure_ids(self):
        for _ in range(3):
            self._order(self.in_dep_b, self.atm_goal, at(2026, 10, 7))
        self._order(self.in_div, self.atm_goal, at(2026, 10, 7))
        self._order(self.idle, self.atm_goal, at(2026, 10, 7))
        names = self._names(self._get())
        self.assertEqual(names[0], self.in_dep_b.full_name)                  # eng ko'p
        self.assertLess(names.index(self.in_div.full_name), names.index(self.idle.full_name))   # teng: tuzilmali oldin
        self.assertEqual(names[-1], self.idle.full_name)                      # tuzilmasiz oxirida

    def test_structure_filters(self):
        for emp in (self.in_div, self.in_dep_b):
            self._order(emp, self.atm_goal, at(2026, 10, 5))
        self.assertEqual(self._names(self._get(department=self.dept_b.id)), [self.in_dep_b.full_name])
        self.assertEqual(self._names(self._get(department=self.dept_a.id)), [self.in_div.full_name])   # bo'linma xodimi dep ga ham kiradi
        by_div = self._get(department=self.dept_a.id, directorate=self.dir_a.id, division=self.div_a.id)
        self.assertEqual(self._names(by_div), [self.in_div.full_name])

    def test_foreign_structure_rejected_with_message(self):
        foreign = Department.objects.create(name="Begona dep", organization=self.other_org, region=self.region)
        response = self._get(department=foreign.id)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["searched"])
        self.assertTrue(response.data["message"])

    def test_pagination_20_per_page(self):
        for i in range(60):
            _, emp = make_employee(self.client_org, self.region, first=f"Xodim{i:02d}", last="Ommaviy")
            self._order(emp, self.atm_goal, at(2026, 10, 5))
        first = self._get()
        self.assertEqual((len(first.data["results"]), first.data["count"], first.data["page_size"]), (20, 60, 20))
        self.assertEqual(len(self._get(page=3).data["results"]), 20)
        self.assertEqual(self._get(page=99).data["page"], 3)              # oxirgi sahifaga tushadi

    def test_default_dates_are_current_month(self):
        response = self.api.get(URL + "organizations/")
        today = timezone.localdate()
        self.assertEqual(response.data["filters"]["date1"], today.replace(day=1).isoformat())

    # ---- ko'rish doirasi ----
    def test_other_organization_hidden_without_all_organization(self):
        user, _ = make_employee(self.client_org, self.region, perms=STATS)
        client = api_for(user)
        params = {"region": self.region.id}
        self.assertEqual(client.get(URL + "organizations/", {**params, "organization": self.other_org.id}).status_code, 404)
        self.assertEqual(client.get(URL + "organizations/", {**params, "organization": self.client_org.id}).status_code, 200)

    def test_region_scope(self):
        other_region = make_region()
        # all_region yo'q: o'z hududidan boshqasi - 403
        self.assertEqual(self._get(region=other_region.id).status_code, 403)
        user, _ = make_employee(self.worker, self.region, perms=STATS + ["main.all_organization", "main.all_region"])
        wide = api_for(user)
        ok = wide.get(URL + "organizations/", {"organization": self.client_org.id, "region": other_region.id})
        self.assertEqual(ok.status_code, 200)
        missing = wide.get(URL + "organizations/", {"organization": self.client_org.id, "region": 999999})
        self.assertEqual(missing.status_code, 404)

    def test_requires_permission(self):
        user, _ = make_employee(self.worker, self.region)
        self.assertEqual(api_for(user).get(URL + "organizations/").status_code, 403)


class OrganizationStatsEmployeeModalTests(TestCase):
    """Modal: xodim sana oralig'ida qaysi kategoriyadan nechta ariza bergani (main.views.org_status_employee)."""

    def setUp(self):
        self.worker = make_org("worker")
        self.client_org = make_org("client")
        self.other_org = make_org("client")
        self.region = make_region()
        self.atm_net = Goal.objects.create(name="Tarmoq muammosi", organization=self.worker)
        self.atm_print = Goal.objects.create(name="Printer ta'miri", organization=self.worker)
        self.barn_goal = Goal.objects.create(name="Qog'oz so'rovi", organization=self.client_org)
        self.viewer_user, _ = make_employee(self.worker, self.region, perms=STATS + ["main.all_organization"])
        _, self.person = make_employee(self.client_org, self.region, first="Ali", last="Valiyev")
        self.client.force_login(self.viewer_user)

    def _order(self, goal, when, sender=None):
        order = Order.objects.create(sender=sender or self.person, goal=goal, status="viewed")
        Order.objects.filter(pk=order.pk).update(date_creat=when)

    def _detail(self, employee=None, **params):
        params.setdefault("date1", "2026-10-01")
        params.setdefault("date2", "2026-10-31")
        return self.client.get(f"{URL}organizations/employee/{(employee or self.person).pk}/", params)

    def test_counts_per_category_sorted_by_count(self):
        for day in (3, 4, 5):
            self._order(self.atm_net, at(2026, 10, day))
        self._order(self.atm_print, at(2026, 10, 9))
        self._order(self.barn_goal, at(2026, 10, 9))                 # ATM xodimi omborxona arizasini ko'rmaydi
        data = self._detail().json()
        self.assertEqual([(i["goal"], i["count"]) for i in data["items"]], [("Tarmoq muammosi", 3), ("Printer ta'miri", 1)])
        self.assertEqual((data["total"], data["kind"]), (4, "ATMga"))

    def test_date_range_and_zero_categories(self):
        self._order(self.atm_net, at(2026, 9, 30))
        self._order(self.atm_net, at(2026, 10, 15))
        self.assertEqual(self._detail().json()["total"], 1)
        data = self._detail(date1="2026-12-01", date2="2026-12-31").json()
        self.assertEqual(data["total"], 0)
        self.assertEqual({i["goal"] for i in data["items"]}, {"Tarmoq muammosi", "Printer ta'miri"})
        self.assertTrue(all(i["count"] == 0 for i in data["items"]))

    def test_non_atm_viewer_gets_warehouse_categories(self):
        self._order(self.barn_goal, at(2026, 10, 6))
        Goal.objects.create(name="Boshqa tashkilot kategoriyasi", organization=self.other_org)     # ko'rinmaydi
        user, _ = make_employee(self.client_org, self.region, perms=STATS)
        self.client.force_login(user)
        data = self._detail().json()
        self.assertEqual(data["kind"], "Omborxonaga")
        self.assertEqual([i["goal"] for i in data["items"]], ["Qog'oz so'rovi"])

    def test_scope_and_permissions(self):
        _, stranger = make_employee(self.other_org, self.region, first="Begona", last="Xodim")
        _, fired = make_employee(self.client_org, self.region, first="Ketgan", last="Xodim", active=False)
        self.assertEqual(self._detail(fired).status_code, 404)
        user, _ = make_employee(self.client_org, self.region, perms=STATS)
        self.client.force_login(user)
        self.assertEqual(self._detail(stranger).status_code, 404)           # all_organization yo'q: boshqa tashkilot
        self.assertEqual(self._detail(self.person).status_code, 200)
        no_perm, _ = make_employee(self.worker, self.region)
        self.client.force_login(no_perm)
        self.assertEqual(self._detail().status_code, 403)

    def test_region_scope(self):
        other_region = make_region()
        _, elsewhere = make_employee(self.client_org, other_region, first="Boshqa", last="Hudud")
        user, _ = make_employee(self.worker, self.region, perms=STATS + ["main.all_organization"])
        self.client.force_login(user)
        self.assertEqual(self._detail(elsewhere).status_code, 404)
        wide, _ = make_employee(self.worker, self.region, perms=STATS + ["main.all_organization", "main.all_region"])
        self.client.force_login(wide)
        self.assertEqual(self._detail(elsewhere).status_code, 200)


# ───────────────────────────── Xodimlar ─────────────────────────────

class EmployeeStatsRegionTests(TestCase):
    def setUp(self):
        self.client_org = make_org("client")
        self.worker = make_org("worker")
        self.region_a = make_region("Hudud A")
        self.region_b = make_region("Hudud B")
        self.goal = make_goal(self.worker)
        _, self.sender = make_employee(self.client_org, self.region_a, first="Yuboruvchi", last="Mijoz")
        _, self.in_a = make_employee(self.worker, self.region_a, first="Birinchi", last="HududA")
        _, self.in_b = make_employee(self.worker, self.region_b, first="Ikkinchi", last="HududB")
        for receiver in (self.in_a, self.in_b, self.in_b):
            Order.objects.create(sender=self.sender, receiver=receiver, goal=self.goal, status="process")

    def _api(self, *, all_regions, region):
        user, _ = make_employee(self.worker, region, perms=STATS + (["main.all_region"] if all_regions else []))
        return api_for(user)

    @staticmethod
    def _totals(response):
        return {row["receiver_id"]: row["total_count"] for row in response.data["employees"]}

    def test_region_required(self):
        for all_regions in (False, True):
            response = self._api(all_regions=all_regions, region=self.region_a).get(URL + "employees/")
            self.assertEqual(self._totals(response), {})
            self.assertFalse(response.data["ready"])
            self.assertEqual(response.data["goals"], [])

    def test_dates_only_search_without_region_shows_nothing(self):
        response = self._api(all_regions=True, region=self.region_a).get(URL + "employees/", {"date1": "2020-01-01", "date2": "2099-01-01"})
        self.assertEqual(self._totals(response), {})

    def test_restricted_user_sees_only_own_region(self):
        client = self._api(all_regions=False, region=self.region_a)
        own = client.get(URL + "employees/", {"region": self.region_a.id})
        self.assertEqual(self._totals(own), {self.in_a.id: 1})
        self.assertEqual({g["id"]: g["total"] for g in own.data["goals"]}, {self.goal.id: 1})
        self.assertEqual(client.get(URL + "employees/", {"region": self.region_b.id}).status_code, 403)
        self.assertEqual(client.get(URL + "employees/", {"region": "all"}).status_code, 403)

    def test_all_region_user_can_pick_any_region_or_all(self):
        client = self._api(all_regions=True, region=self.region_a)
        self.assertEqual(self._totals(client.get(URL + "employees/", {"region": self.region_b.id})), {self.in_b.id: 2})
        everything = client.get(URL + "employees/", {"region": "all"})
        self.assertEqual(self._totals(everything), {self.in_a.id: 1, self.in_b.id: 2})
        self.assertEqual({g["id"]: g["total"] for g in everything.data["goals"]}, {self.goal.id: 3})

    def test_default_dates_are_current_month(self):
        response = self._api(all_regions=False, region=self.region_a).get(URL + "employees/")
        self.assertEqual(response.data["filters"]["date1"], timezone.localdate().replace(day=1).isoformat())


# ───────────────────────────── Texnikalar ─────────────────────────────

class TechnicsStatsRulesTests(TestCase):
    def setUp(self):
        self.org = make_org("worker")
        self.other_org = make_org("client")
        self.region_a = make_region("Hudud A")
        self.region_b = make_region("Hudud B")
        self.dept = Department.objects.create(name="Dep", organization=self.org, region=self.region_a)
        self.directorate = Directorate.objects.create(name="Boshqarma", department=self.dept)
        self.division = Division.objects.create(name="Bolim", directorate=self.directorate)
        self.group = Group.objects.create(name="Kompyuter")
        self.category = Category.objects.create(name="Noutbuk", group=self.group)
        self._tech(self.org, self.region_a, self.dept, self.directorate, self.division)
        self._tech(self.org, self.region_a, self.dept)
        self._tech(self.org, self.region_b)
        self._tech(self.other_org, self.region_a)
        self._tech(self.org, self.region_a, active=False)
        self.user, _ = make_employee(self.org, self.region_a, perms=STATS)
        self.api = api_for(self.user)

    def _tech(self, org, region, dept=None, directorate=None, division=None, active=True):
        return Technics.objects.create(
            name="T", group=self.group, category=self.category, organization=org, region=region,
            department=dept, directorate=directorate, division=division, is_active=active)

    def _total(self, response):
        return {g["id"]: g["total"] for g in response.data["groups"]}[self.group.id]

    def _get(self, **params):
        params.setdefault("organization", self.org.id)
        params.setdefault("region", self.region_a.id)
        return self.api.get(URL + "technics/", params)

    def _login(self, *perms, region=None):
        user, _ = make_employee(self.org, region or self.region_a, perms=STATS + list(perms))
        self.api = api_for(user)

    def test_default_uses_own_org_region_and_department(self):
        _, member = make_employee(self.org, self.region_a, perms=STATS)
        member.department = self.dept
        member.save()
        response = api_for(member.user).get(URL + "technics/")
        filters = response.data["filters"]
        self.assertEqual((filters["organization"], filters["region"], filters["department"]),
                         (str(self.org.id), str(self.region_a.id), str(self.dept.id)))
        self.assertEqual(self._total(response), 2)

    def test_default_without_department_shows_whole_region(self):
        self.assertEqual(self._total(self.api.get(URL + "technics/")), 2)

    def test_organization_and_region_required_when_submitted(self):
        for params in ({"organization": self.org.id}, {"region": self.region_a.id}, {"organization": "", "region": ""}):
            response = self.api.get(URL + "technics/", params)
            self.assertEqual(self._total(response), 0, params)
            self.assertEqual(response.data["message"], "Tashkilot va hududni tanlang")

    def test_filters(self):
        self.assertEqual(self._total(self._get()), 2)
        self.assertEqual(self._total(self._get(department=self.dept.id)), 2)
        self.assertEqual(self._total(self._get(department=self.dept.id, directorate=self.directorate.id)), 1)
        deep = self._get(department=self.dept.id, directorate=self.directorate.id, division=self.division.id)
        self.assertEqual(self._total(deep), 1)

    def test_foreign_structure_rejected(self):
        foreign = Department.objects.create(name="Begona", organization=self.other_org, region=self.region_a)
        response = self._get(department=foreign.id)
        self.assertEqual(self._total(response), 2)
        self.assertTrue(response.data["message"])

    def test_kpi_and_ordering(self):
        small = Group.objects.create(name="Kichik")
        Category.objects.create(name="Bo'sh kategoriya", group=small)
        second = Category.objects.create(name="Ikkinchi", group=self.group)
        for _ in range(3):
            Technics.objects.create(name="X", group=self.group, category=second, organization=self.org, region=self.region_a)
        response = self._get()
        kpi = response.data["kpi"]
        self.assertEqual((kpi["total"], kpi["groups"], kpi["categories"]), (5, 1, 2))
        self.assertEqual(kpi["top_name"], self.group.name)
        self.assertEqual([g["id"] for g in response.data["groups"]], [self.group.id, small.id])      # bo'sh guruh oxirida
        self.assertEqual([c["count"] for c in response.data["groups"][0]["categories"]], [3, 2])

    def test_scope(self):
        self.assertEqual(self._get(organization=self.other_org.id).status_code, 404)
        self.assertEqual(self._get(region=self.region_b.id).status_code, 403)
        self._login("main.all_organization", "main.all_region")
        self.assertEqual(self._total(self._get(organization=self.other_org.id)), 1)
        self.assertEqual(self._total(self._get(region=self.region_b.id)), 1)
        self.assertEqual(self._total(self._get(region="all")), 3)

    def test_all_regions_forbidden_without_permission(self):
        self.assertEqual(self._get(region="all").status_code, 403)

    def test_default_for_all_region_user_without_region_is_all_regions(self):
        user, _ = make_employee(self.org, None, perms=STATS + ["main.all_region"])
        response = api_for(user).get(URL + "technics/")
        self.assertEqual(response.data["filters"]["region"], "all")
        self.assertEqual(self._total(response), 3)
