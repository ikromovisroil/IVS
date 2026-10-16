"""Statistika -> Tashkilotlar: tanlangan tuzilmadagi xodimlar va ularning sana oralig'idagi arizalari."""
from datetime import date, datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from main.models import Department, Directorate, Division, Goal, Order, Region
from main.testing import make_employee, make_goal, make_org, make_region

STATS_PERMS = ["main.status_employee"]


def at(year, month, day):
    return timezone.make_aware(datetime(year, month, day, 12, 0))


class OrgStatusTests(TestCase):
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

        # Statistika ko'ruvchi: ATM xodimi, barcha tashkilotlarni ko'ra oladi
        self.viewer_user, self.viewer = make_employee(
            self.worker, self.region, perms=STATS_PERMS + ["main.all_organization"],
        )
        # Tanlangan tashkilot xodimlari
        _, self.in_div = make_employee(self.client_org, self.region, first="Bo'lim", last="Xodimi")
        self.in_div.division = self.div_a
        self.in_div.save()
        _, self.in_dep_b = make_employee(self.client_org, self.region, first="DepB", last="Xodimi")
        self.in_dep_b.department = self.dept_b
        self.in_dep_b.save()
        _, self.idle = make_employee(self.client_org, self.region, first="Hech", last="Yozmagan")
        _, self.stranger = make_employee(self.other_org, self.region, first="Begona", last="Tashkilot")
        _, self.fired = make_employee(self.client_org, self.region, first="Ketgan", last="Xodim", active=False)
        self.client.force_login(self.viewer_user)

    def _order(self, sender, goal, when):
        order = Order.objects.create(sender=sender, goal=goal, status="viewed")
        Order.objects.filter(pk=order.pk).update(date_creat=when)
        return order

    def _get(self, **params):
        params.setdefault("date1", "2026-10-01")
        params.setdefault("date2", "2026-10-31")
        if "organization" in params:
            params.setdefault("region", self.region.id)          # tashkilot ham, hudud ham majburiy
        return self.client.get(reverse("org_status"), params)

    def _rows(self, response):
        return {e.full_name: e for e in response.context["page_obj"]}

    # ---- ruxsat va ko'rinish ----
    def test_requires_statistics_permission(self):
        user, _ = make_employee(self.worker, self.region)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("org_status")).status_code, 403)

    def test_empty_form_without_organization(self):
        response = self.client.get(reverse("org_status"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["searched"])

    def test_table_with_empty_message_shown_before_search(self):
        html = self.client.get(reverse("org_status")).content.decode()
        self.assertIn("Ma'lumot topilmadi", html)                    # boshqa jadvallardagidek
        self.assertIn('id="org-status-table"', html)
        self.assertIn("F.I.O", html)
        self.assertIn("Ariza bergan xodimlar", html)                # xulosa kartochkalari qidiruvdan oldin ham bor
        self.assertRegex(html, r"Xodimlar</div><b>0</b>")            # ... hammasi 0 bilan
        self.assertRegex(html, r"Ariza bergan xodimlar</div><b>0</b>")
        self.assertRegex(html, r"ATMga yuborilgan arizalar</div><b>0</b>")

    def test_empty_message_when_nobody_found(self):
        empty_org = make_org("client")
        response = self._get(organization=empty_org.id)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ma'lumot topilmadi")
        self.assertContains(response, "Ariza bergan xodimlar")

    def test_menu_has_organizations_item(self):
        html = self.client.get(reverse("org_status")).content.decode()
        self.assertIn(reverse("org_status"), html)
        self.assertIn("Tashkilotlar", html)

    def test_default_dates_are_current_month(self):
        response = self.client.get(reverse("org_status"))
        today = timezone.localdate()
        self.assertTrue(response.context["date1"].startswith(f"{today.year}-{today.month:02d}-01"))

    # ---- hisoblash ----
    def test_counts_orders_in_date_range_per_employee(self):
        self._order(self.in_div, self.atm_goal, at(2026, 10, 5))
        self._order(self.in_div, self.atm_goal, at(2026, 10, 20))
        self._order(self.in_div, self.barn_goal, at(2026, 10, 31))
        self._order(self.in_div, self.atm_goal, at(2026, 9, 30))        # oraliqdan oldin
        self._order(self.in_div, self.atm_goal, at(2026, 11, 1))        # oraliqdan keyin
        self._order(self.in_dep_b, self.barn_goal, at(2026, 10, 10))
        response = self._get(organization=self.client_org.id)
        rows = self._rows(response)
        # Ko'ruvchi ATM (worker) xodimi: faqat ATMga yuborilgan arizalar, omborxonaniki ko'rinmaydi
        self.assertEqual(rows[self.in_div.full_name].order_count, 2)
        self.assertEqual(rows[self.in_dep_b.full_name].order_count, 0)
        self.assertEqual(response.context["totals"]["orders"], 2)
        self.assertEqual(response.context["kind_label"], "ATMga")
        self.assertNotContains(response, "Omborxonaga yuborilgan")

    def test_employees_without_orders_are_listed_with_zero(self):
        response = self._get(organization=self.client_org.id)
        rows = self._rows(response)
        self.assertEqual(rows[self.idle.full_name].order_count, 0)
        self.assertEqual(response.context["totals"]["employees"], 3)      # in_div, in_dep_b, idle (nofaol va begona tashkilot kirmaydi)

    def test_inactive_and_other_organization_staff_excluded(self):
        names = set(self._rows(self._get(organization=self.client_org.id)))
        self.assertNotIn(self.fired.full_name, names)
        self.assertNotIn(self.stranger.full_name, names)

    def test_sorted_by_most_orders_first(self):
        for _ in range(3):
            self._order(self.in_dep_b, self.atm_goal, at(2026, 10, 7))
        self._order(self.in_div, self.atm_goal, at(2026, 10, 7))
        ordered = [e.full_name for e in self._get(organization=self.client_org.id).context["page_obj"]]
        self.assertEqual(ordered[0], self.in_dep_b.full_name)
        self.assertEqual(ordered[1], self.in_div.full_name)

    def test_non_atm_viewer_sees_warehouse_orders_only(self):
        self._order(self.in_div, self.atm_goal, at(2026, 10, 5))
        self._order(self.in_div, self.barn_goal, at(2026, 10, 6))
        self._order(self.in_div, self.barn_goal, at(2026, 10, 7))
        self._order(self.in_dep_b, self.barn_goal, at(2026, 10, 8))
        user, _ = make_employee(self.client_org, self.region, perms=STATS_PERMS)
        self.client.force_login(user)
        response = self._get(organization=self.client_org.id)
        self.assertEqual(response.status_code, 200)
        rows = self._rows(response)
        self.assertEqual(rows[self.in_div.full_name].order_count, 2)         # ATM arizasi hisobga kirmaydi
        self.assertEqual(rows[self.in_dep_b.full_name].order_count, 1)
        self.assertEqual(response.context["totals"]["orders"], 3)
        self.assertEqual(response.context["kind_label"], "Omborxonaga")
        self.assertContains(response, "Omborxonaga yuborilgan arizalar")           # kartochka sarlavhasi
        self.assertContains(response, '<th class="text-center">Soni</th>')

    def test_atm_viewer_page_labels(self):
        response = self._get(organization=self.client_org.id)
        self.assertContains(response, "ATMga yuborilgan arizalar")                  # kartochka sarlavhasi
        self.assertContains(response, '<th class="text-center">Soni</th>')
        self.assertNotContains(response, "ATM / Omborxona")                  # birlashgan ko'rsatkich olib tashlangan

    def test_page_opens_for_anyone_with_the_permission(self):
        # Ruxsat (status_employee) bo'lsa, tashkilot turidan qat'i nazar sahifa ochiladi; ruxsatsiz - yo'q
        with_perm, _ = make_employee(self.client_org, self.region, perms=STATS_PERMS)
        without_perm, _ = make_employee(self.client_org, self.region)
        self.client.force_login(with_perm)
        self.assertEqual(self.client.get(reverse("org_status")).status_code, 200)
        self.client.force_login(without_perm)
        self.assertEqual(self.client.get(reverse("org_status")).status_code, 403)

    # ---- tashkilot va hudud majburiy ----
    def test_organization_and_region_are_required_fields_in_form(self):
        html = self.client.get(reverse("org_status")).content.decode()
        self.assertRegex(html, r'<select id="organization" name="organization" class="form-select" required>')
        self.assertRegex(html, r'<select id="region" name="region" class="form-select" required>')

    def test_search_without_region_gives_no_results(self):
        response = self.client.get(reverse("org_status"), {
            "organization": self.client_org.id, "date1": "2026-10-01", "date2": "2026-10-31",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["searched"])
        self.assertContains(response, "Tashkilot va hududni tanlang")

    def test_search_without_organization_gives_no_results(self):
        response = self.client.get(reverse("org_status"), {"region": self.region.id, "date1": "2026-10-01", "date2": "2026-10-31"})
        self.assertFalse(response.context["searched"])
        self.assertContains(response, "Tashkilot va hududni tanlang")

    def test_first_open_shows_no_warning(self):
        self.assertNotContains(self.client.get(reverse("org_status")), "Tashkilot va hududni tanlang")

    def test_unknown_region(self):
        # o'z hududidan boshqasi - ruxsatsiz (403); barcha hududni ko'ra oladigan xodim uchun mavjud bo'lmagan hudud - 404
        self.assertEqual(self._get(organization=self.client_org.id, region=999999).status_code, 403)
        user, _ = make_employee(self.worker, self.region, perms=STATS_PERMS + ["main.all_organization", "main.all_region"])
        self.client.force_login(user)
        self.assertEqual(self._get(organization=self.client_org.id, region=999999).status_code, 404)

    # ---- tuzilma filtrlari ----
    def test_filter_by_department_directorate_division(self):
        base = {"organization": self.client_org.id}
        by_dep_b = set(self._rows(self._get(department=self.dept_b.id, **base)))
        self.assertEqual(by_dep_b, {self.in_dep_b.full_name})
        by_dep_a = set(self._rows(self._get(department=self.dept_a.id, **base)))
        self.assertEqual(by_dep_a, {self.in_div.full_name})            # bo'linma xodimi uning departamentiga ham kiradi
        by_dir = set(self._rows(self._get(department=self.dept_a.id, directorate=self.dir_a.id, **base)))
        self.assertEqual(by_dir, {self.in_div.full_name})
        by_div = set(self._rows(self._get(department=self.dept_a.id, directorate=self.dir_a.id, division=self.div_a.id, **base)))
        self.assertEqual(by_div, {self.in_div.full_name})

    def test_orders_counted_only_for_filtered_staff(self):
        self._order(self.in_div, self.atm_goal, at(2026, 10, 5))
        self._order(self.in_dep_b, self.atm_goal, at(2026, 10, 5))
        response = self._get(organization=self.client_org.id, department=self.dept_b.id)
        self.assertEqual(response.context["totals"]["orders"], 1)

    def test_structure_from_other_organization_rejected(self):
        foreign_dep = Department.objects.create(name="Begona dep", organization=self.other_org, region=self.region)
        response = self._get(organization=self.client_org.id, department=foreign_dep.id)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["searched"])

    # ---- tashkilot doirasi ----
    def test_without_all_organization_only_own_organization(self):
        user, _ = make_employee(self.client_org, self.region, perms=STATS_PERMS)
        self.client.force_login(user)
        own = self.client.get(reverse("org_status"), {"organization": self.client_org.id, "region": self.region.id, "date1": "2026-10-01", "date2": "2026-10-31"})
        self.assertEqual(own.status_code, 200)
        self.assertTrue(own.context["searched"])
        foreign = self.client.get(reverse("org_status"), {"organization": self.other_org.id, "region": self.region.id})
        self.assertEqual(foreign.status_code, 404)
        listed = {o.id for o in own.context["organizations"]}
        self.assertEqual(listed, {self.client_org.id})

    def test_pagination_20_per_page_with_pager(self):
        for i in range(60):
            make_employee(self.client_org, self.region, first=f"Xodim{i:02d}", last="Ommaviy")
        first = self._get(organization=self.client_org.id)
        self.assertEqual(len(first.context["page_obj"]), 20)
        self.assertContains(first, 'aria-label="Sahifalash"')          # sahifalash tugmalari (‹ 1 2 3 4 ›)
        second = self._get(organization=self.client_org.id, page=2)
        self.assertEqual(len(second.context["page_obj"]), 20)
        self.assertEqual(second.context["row_start"], 21)
        last = self._get(organization=self.client_org.id, page=4)
        self.assertEqual(len(last.context["page_obj"]), 3)              # 63 xodim: 20 + 20 + 20 + 3

    def test_pager_keeps_filters_in_links(self):
        for i in range(25):
            make_employee(self.client_org, self.region, first=f"Havola{i:02d}", last="Sinov")
        html = self._get(organization=self.client_org.id).content.decode()
        self.assertIn(f"organization={self.client_org.id}", html.split('aria-label="Sahifalash"')[1])
        self.assertIn("date1=2026-10-01", html.split('aria-label="Sahifalash"')[1])

    def test_no_pager_for_single_page(self):
        self.assertNotContains(self._get(organization=self.client_org.id), 'aria-label="Sahifalash"')

    def test_query_count_does_not_grow_with_staff(self):
        def queries():
            from django.db import connection
            from django.test.utils import CaptureQueriesContext
            with CaptureQueriesContext(connection) as ctx:
                self._get(organization=self.client_org.id)
            return len(ctx)

        base = queries()
        for i in range(15):
            _, emp = make_employee(self.client_org, self.region, first=f"Q{i}", last="Soni")
            emp.division = self.div_a
            emp.save()
            self._order(emp, self.atm_goal, at(2026, 10, 3))
        self.assertLessEqual(queries(), base + 2)


class OrgStatusAjaxTests(TestCase):
    def test_departments_loaded_for_all_regions_when_requested(self):
        org = make_org("client")
        region1, region2 = make_region(), make_region()
        d1 = Department.objects.create(name="Birinchi hudud", organization=org, region=region1)
        d2 = Department.objects.create(name="Ikkinchi hudud", organization=org, region=region2)
        user, _ = make_employee(make_org("worker"), region1)
        self.client.force_login(user)
        url = reverse("ajax_load_departments")
        default = self.client.get(url, {"organization": org.id}).json()["results"]          # foydalanuvchi hududi bilan cheklanadi
        everything = self.client.get(url, {"organization": org.id, "all_regions": "1"}).json()["results"]
        ids = lambda data: {int(item["id"]) for item in data}
        self.assertEqual(ids(default), {d1.id})
        self.assertEqual(ids(everything), {d1.id, d2.id})


class OrgStatusEmployeeModalTests(TestCase):
    """Qator bosilganda modalda: xodim sana oralig'ida qaysi kategoriyadan nechta ariza bergani."""

    def setUp(self):
        self.worker = make_org("worker")
        self.client_org = make_org("client")
        self.other_org = make_org("client")
        self.region = make_region()
        self.atm_net = Goal.objects.create(name="Tarmoq muammosi", organization=self.worker)
        self.atm_print = Goal.objects.create(name="Printer ta'miri", organization=self.worker)
        self.barn_goal = Goal.objects.create(name="Qog'oz so'rovi", organization=self.client_org)
        self.viewer_user, _ = make_employee(self.worker, self.region, perms=STATS_PERMS + ["main.all_organization"])
        _, self.person = make_employee(self.client_org, self.region, first="Ali", last="Valiyev")
        self.client.force_login(self.viewer_user)

    def _order(self, goal, when, sender=None):
        order = Order.objects.create(sender=sender or self.person, goal=goal, status="viewed")
        Order.objects.filter(pk=order.pk).update(date_creat=when)

    def _detail(self, employee=None, **params):
        params.setdefault("date1", "2026-10-01")
        params.setdefault("date2", "2026-10-31")
        return self.client.get(reverse("org_status_employee", args=[(employee or self.person).pk]), params)

    def test_counts_per_category_sorted_by_count(self):
        for day in (3, 4, 5):
            self._order(self.atm_net, at(2026, 10, day))
        self._order(self.atm_print, at(2026, 10, 9))
        self._order(self.barn_goal, at(2026, 10, 9))                 # ATM xodimi omborxona arizasini ko'rmaydi
        data = self._detail().json()
        self.assertEqual([(i["goal"], i["count"]) for i in data["items"]], [("Tarmoq muammosi", 3), ("Printer ta'miri", 1)])
        self.assertEqual(data["total"], 4)
        self.assertEqual(data["kind"], "ATMga")
        self.assertEqual(data["employee"]["full_name"], self.person.full_name)

    def test_date_range_is_applied(self):
        self._order(self.atm_net, at(2026, 9, 30))
        self._order(self.atm_net, at(2026, 10, 15))
        self._order(self.atm_net, at(2026, 11, 1))
        self.assertEqual(self._detail().json()["total"], 1)
        self.assertEqual(self._detail(date1="2026-09-01", date2="2026-12-31").json()["total"], 3)

    def test_all_atm_categories_listed_with_zero_for_unused(self):
        self._order(self.atm_print, at(2026, 10, 9))
        data = self._detail().json()
        # Hamma ATM kategoriyalari chiqadi; ariza berilmagani 0 bilan, omborxona kategoriyasi chiqmaydi
        self.assertEqual([(i["goal"], i["count"]) for i in data["items"]], [("Printer ta'miri", 1), ("Tarmoq muammosi", 0)])
        self.assertEqual(data["total"], 1)

    def test_no_orders_lists_categories_with_zeros(self):
        data = self._detail().json()
        self.assertEqual(data["total"], 0)
        self.assertEqual({i["goal"] for i in data["items"]}, {"Tarmoq muammosi", "Printer ta'miri"})
        self.assertTrue(all(i["count"] == 0 for i in data["items"]))

    def test_categories_alphabetical_when_counts_equal(self):
        names = [i["goal"] for i in self._detail().json()["items"]]
        self.assertEqual(names, sorted(names, key=str.lower))

    def test_no_categories_at_all_gives_empty_list(self):
        Goal.objects.all().delete()
        data = self._detail().json()
        self.assertEqual((data["items"], data["total"]), ([], 0))

    def test_non_atm_viewer_gets_warehouse_categories(self):
        self._order(self.atm_net, at(2026, 10, 5))
        self._order(self.barn_goal, at(2026, 10, 6))
        self._order(self.barn_goal, at(2026, 10, 7))
        user, _ = make_employee(self.client_org, self.region, perms=STATS_PERMS)
        self.client.force_login(user)
        Goal.objects.create(name="Mebel so'rovi", organization=self.client_org)
        Goal.objects.create(name="Boshqa tashkilot kategoriyasi", organization=self.other_org)    # ko'rinmaydi
        data = self._detail().json()
        self.assertEqual([(i["goal"], i["count"]) for i in data["items"]], [("Qog'oz so'rovi", 2), ("Mebel so'rovi", 0)])
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["kind"], "Omborxonaga")

    def test_requires_permission(self):
        user, _ = make_employee(self.worker, self.region)
        self.client.force_login(user)
        self.assertEqual(self._detail().status_code, 403)

    def test_other_organization_hidden_without_all_organization(self):
        _, stranger = make_employee(self.other_org, self.region, first="Begona", last="Xodim")
        user, _ = make_employee(self.client_org, self.region, perms=STATS_PERMS)
        self.client.force_login(user)
        self.assertEqual(self._detail(stranger).status_code, 404)
        self.assertEqual(self._detail(self.person).status_code, 200)        # o'z tashkiloti

    def test_inactive_employee_not_found(self):
        _, fired = make_employee(self.client_org, self.region, first="Ketgan", last="Xodim", active=False)
        self.assertEqual(self._detail(fired).status_code, 404)

    def test_table_rows_are_clickable_and_modal_is_rendered(self):
        _, row_person = make_employee(self.client_org, self.region, first="Qator", last="Xodimi")
        html = self.client.get(reverse("org_status"), {
            "organization": self.client_org.id, "region": self.region.id, "date1": "2026-10-01", "date2": "2026-10-31",
        }).content.decode()
        self.assertIn('class="org-row"', html)
        self.assertIn(f'data-emp-id="{row_person.id}"', html)
        self.assertIn('id="empOrdersModal"', html)
        self.assertIn(reverse("org_status_employee", args=[0]), html)         # JS dagi "/0/" o'rniga qo'yiladigan shablon


class OrgStatusRegionTests(TestCase):
    """Hudud filtri: `all_region` ruxsati bo'lsa hamma hudud, bo'lmasa faqat o'z hududi."""

    def setUp(self):
        self.worker = make_org("worker")
        self.org = make_org("client")
        self.region_a = make_region("Hudud A")
        self.region_b = make_region("Hudud B")
        self.goal = make_goal(self.worker)
        _, self.in_a = make_employee(self.org, self.region_a, first="Birinchi", last="HududA")
        _, self.in_b = make_employee(self.org, self.region_b, first="Ikkinchi", last="HududB")
        Order.objects.create(sender=self.in_a, goal=self.goal, status="viewed")
        Order.objects.create(sender=self.in_b, goal=self.goal, status="viewed")
        Order.objects.create(sender=self.in_b, goal=self.goal, status="viewed")

    def _viewer(self, *, all_regions, region):
        perms = STATS_PERMS + ["main.all_organization"] + (["main.all_region"] if all_regions else [])
        user, _ = make_employee(self.worker, region, perms=perms)
        self.client.force_login(user)

    def _get(self, **params):
        params.setdefault("organization", self.org.id)
        params.setdefault("region", self.region_a.id)
        params.setdefault("date1", "2000-01-01")
        params.setdefault("date2", "2100-01-01")
        return self.client.get(reverse("org_status"), params)

    def _names(self, response):
        return {e.full_name for e in response.context["page_obj"]}

    def test_all_region_permission_can_pick_any_region(self):
        self._viewer(all_regions=True, region=self.region_a)
        response = self._get(region=self.region_a.id)
        self.assertEqual(self._names(response), {self.in_a.full_name})
        self.assertEqual({r.id for r in response.context["regions"]}, {self.region_a.id, self.region_b.id})
        self.assertEqual(self._names(self._get(region=self.region_b.id)), {self.in_b.full_name})

    def test_region_filter_narrows_staff_and_totals(self):
        self._viewer(all_regions=True, region=self.region_a)
        response = self._get(region=self.region_b.id)
        self.assertEqual(self._names(response), {self.in_b.full_name})
        self.assertEqual(response.context["totals"]["orders"], 2)
        self.assertContains(response, "Hudud B")

    def test_without_all_region_only_own_region(self):
        self._viewer(all_regions=False, region=self.region_a)
        response = self._get(region=self.region_a.id)
        self.assertEqual(self._names(response), {self.in_a.full_name})
        self.assertEqual({r.id for r in response.context["regions"]}, {self.region_a.id})

    def test_other_region_is_forbidden_without_all_region(self):
        self._viewer(all_regions=False, region=self.region_a)
        self.assertEqual(self._get(region=self.region_b.id).status_code, 403)
        self.assertEqual(self._get(region=self.region_a.id).status_code, 200)

    def test_viewer_without_region_and_without_all_region_cannot_search(self):
        self._viewer(all_regions=False, region=None)
        self.assertEqual(self._get(region=self.region_a.id).status_code, 403)       # hech qaysi hudud ruxsat etilmagan
        self.assertEqual(list(self._get(region="").context["regions"]), [])

    def test_region_select_is_rendered(self):
        self._viewer(all_regions=True, region=self.region_a)
        html = self.client.get(reverse("org_status")).content.decode()
        self.assertIn('id="region"', html)
        self.assertIn("Hudud A", html)
        self.assertIn("Hudud B", html)

    def test_modal_respects_region_scope(self):
        self._viewer(all_regions=False, region=self.region_a)
        url = lambda emp: reverse("org_status_employee", args=[emp.pk])
        self.assertEqual(self.client.get(url(self.in_a)).status_code, 200)
        self.assertEqual(self.client.get(url(self.in_b)).status_code, 404)
        self._viewer(all_regions=True, region=self.region_a)
        self.assertEqual(self.client.get(url(self.in_b)).status_code, 200)

    def test_departments_ajax_uses_selected_region(self):
        dep_a = Department.objects.create(name="Dep A", organization=self.org, region=self.region_a)
        dep_b = Department.objects.create(name="Dep B", organization=self.org, region=self.region_b)
        self._viewer(all_regions=True, region=self.region_a)
        url = reverse("ajax_load_departments")
        ids = lambda response: {int(item["id"]) for item in response.json()["results"]}
        self.assertEqual(ids(self.client.get(url, {"organization": self.org.id, "all_regions": "1"})), {dep_a.id, dep_b.id})
        self.assertEqual(ids(self.client.get(url, {"organization": self.org.id, "all_regions": "1", "region": self.region_b.id})), {dep_b.id})
        self.assertEqual(ids(self.client.get(url, {"organization": self.org.id, "region": self.region_a.id})), {dep_a.id})

