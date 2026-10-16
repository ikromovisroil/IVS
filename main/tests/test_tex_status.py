"""Statistika -> Texnikalar: tashkilot, hudud, department, boshqarma, bo'lim filtrlari va ruxsat doirasi."""
from django.test import TestCase
from django.urls import reverse

from main.models import Category, Department, Directorate, Division, Group, Technics
from main.testing import make_employee, make_org, make_region

STATS_PERMS = ["main.status_employee"]


class TexStatusTests(TestCase):
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

        self.user, _ = make_employee(self.org, self.region_a, perms=STATS_PERMS)
        self.client.force_login(self.user)

    def _tech(self, org, region, dept=None, directorate=None, division=None, active=True):
        return Technics.objects.create(
            name="T", group=self.group, category=self.category, organization=org, region=region,
            department=dept, directorate=directorate, division=division, is_active=active,
        )

    def _total(self, response):
        return {g["id"]: g["technics_count"] for g in response.context["groups_qs"]}[self.group.id]

    def _login(self, *perms, region=None, org=None):
        user, _ = make_employee(org or self.org, region or self.region_a, perms=STATS_PERMS + list(perms))
        self.client.force_login(user)

    def _get(self, **params):
        """Forma yuborilgandek: tashkilot va hudud majburiy."""
        params.setdefault("organization", self.org.id)
        params.setdefault("region", self.region_a.id)
        return self.client.get(reverse("tex_status"), params)

    def test_default_uses_own_organization_region_and_department(self):
        _, member = make_employee(self.org, self.region_a, perms=STATS_PERMS)
        member.department = self.dept
        member.save()
        self.client.force_login(member.user)
        response = self.client.get(reverse("tex_status"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_org"], str(self.org.id))
        self.assertEqual(response.context["selected_region"], str(self.region_a.id))
        self.assertEqual(response.context["sel_department"], self.dept)
        self.assertEqual(self._total(response), 2)                         # o'z departamentidagi 2 ta (begona, nofaol va boshqa hudud kirmaydi)

    def test_default_without_department_shows_whole_organization_in_own_region(self):
        response = self.client.get(reverse("tex_status"))
        self.assertIsNone(response.context["sel_department"])
        self.assertEqual(self._total(response), 2)                         # hudud A: 2 ta faol (boshqa hudud, begona, nofaol kirmaydi)

    def test_default_for_all_region_user_without_region_is_all_regions(self):
        user, emp = make_employee(self.org, None, perms=STATS_PERMS + ["main.all_region"])
        self.client.force_login(user)
        response = self.client.get(reverse("tex_status"))
        self.assertEqual(response.context["selected_region"], "all")
        self.assertEqual(self._total(response), 3)

    def test_submitted_form_without_department_is_not_narrowed_to_own_department(self):
        _, member = make_employee(self.org, self.region_a, perms=STATS_PERMS)
        member.department = self.dept
        member.save()
        self.client.force_login(member.user)
        self.assertEqual(self._total(self._get()), 2)
        self.assertIsNone(self._get().context["sel_department"])

    def test_organization_and_region_are_required(self):
        html = self.client.get(reverse("tex_status")).content.decode()
        self.assertRegex(html, r'<select id="organization" name="organization" class="form-select" required>')
        self.assertRegex(html, r'<select id="region" name="region" class="form-select" required>')
        for params in ({"organization": self.org.id}, {"region": self.region_a.id}, {"organization": "", "region": ""}):
            response = self.client.get(reverse("tex_status"), params)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self._total(response), 0, params)
            self.assertContains(response, "Tashkilot va hududni tanlang")

    def test_requires_statistics_permission(self):
        user, _ = make_employee(self.org, self.region_a)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("tex_status")).status_code, 403)

    def test_region_filter(self):
        self.assertEqual(self._total(self._get()), 2)

    def test_department_directorate_division_filters(self):
        self.assertEqual(self._total(self._get(department=self.dept.id)), 2)
        self.assertEqual(self._total(self._get(department=self.dept.id, directorate=self.directorate.id)), 1)
        params = {"department": self.dept.id, "directorate": self.directorate.id, "division": self.division.id}
        response = self._get(**params)
        self.assertEqual(self._total(response), 1)
        self.assertEqual(response.context["sel_division"], self.division)

    def test_category_counts_follow_filters(self):
        response = self._get()
        category = response.context["groups_qs"][0]["category_list"][0]
        self.assertEqual(category["soni"], 2)

    def test_structure_of_other_organization_is_rejected(self):
        foreign = Department.objects.create(name="Begona", organization=self.other_org, region=self.region_a)
        response = self._get(department=foreign.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._total(response), 2)                         # noto'g'ri tuzilma e'tiborsiz qoldiriladi
        self.assertContains(response, "tegishli emas")

    # ---- ruxsat doirasi ----
    def test_other_organization_requires_all_organization(self):
        self.assertEqual(self._get(organization=self.other_org.id).status_code, 404)
        self._login("main.all_organization")
        response = self._get(organization=self.other_org.id)
        self.assertEqual(self._total(response), 1)
        self.assertEqual({o.id for o in response.context["organizations"]} >= {self.org.id, self.other_org.id}, True)

    def test_organizations_list_limited_without_permission(self):
        response = self._get()
        self.assertEqual([o.id for o in response.context["organizations"]], [self.org.id])

    def test_other_region_requires_all_region(self):
        self.assertEqual(self._get(region=self.region_b.id).status_code, 403)
        self.assertEqual([r.id for r in self.client.get(reverse("tex_status")).context["regions"]], [self.region_a.id])
        self._login("main.all_region")
        response = self._get(region=self.region_b.id)
        self.assertEqual(self._total(response), 1)
        self.assertEqual({r.id for r in response.context["regions"]}, {self.region_a.id, self.region_b.id})

    def test_all_regions_option_only_with_all_region_permission(self):
        self.assertNotContains(self.client.get(reverse("tex_status")), 'value="all"')
        self.assertEqual(self._get(region="all").status_code, 403)
        self._login("main.all_region")
        self.assertContains(self.client.get(reverse("tex_status")), 'value="all"')
        response = self._get(region="all")
        self.assertEqual(self._total(response), 3)
        self.assertContains(response, 'value="all" selected')

    def test_form_has_all_filters(self):
        html = self.client.get(reverse("tex_status")).content.decode()
        for name in ("organization", "region", "department", "directorate", "division"):
            self.assertIn(f'name="{name}"', html)

    # ---- dashboard ma'lumotlari: KPI, guruhlar va kategoriyalar ko'pdan kamga ----
    def test_kpi_and_ordering(self):
        small = Group.objects.create(name="Kichik")
        Category.objects.create(name="Bo'sh kategoriya", group=small)
        second = Category.objects.create(name="Ikkinchi", group=self.group)
        Technics.objects.create(name="X", group=self.group, category=second, organization=self.org, region=self.region_a)
        Technics.objects.create(name="X", group=self.group, category=second, organization=self.org, region=self.region_a)
        Technics.objects.create(name="X", group=self.group, category=second, organization=self.org, region=self.region_a)
        response = self._get()
        kpi = response.context["kpi"]
        self.assertEqual(kpi["total"], 5)
        self.assertEqual(kpi["groups"], 1)
        self.assertEqual(kpi["categories"], 2)
        self.assertEqual(kpi["top_name"], self.group.name)
        groups = response.context["groups_qs"]
        self.assertEqual([g["id"] for g in groups], [self.group.id, small.id])       # bo'sh guruh oxirida
        self.assertEqual([c["soni"] for c in groups[0]["category_list"]], [3, 2])    # ko'pdan kamga
        self.assertEqual([g["name"] for g in response.context["dashboard"]["groups"]], [self.group.name])

    def test_empty_state_when_nothing_selected(self):
        response = self.client.get(reverse("tex_status"), {"organization": self.org.id})
        self.assertContains(response, "Ma'lumot topilmadi")
        self.assertEqual(response.context["kpi"]["total"], 0)
