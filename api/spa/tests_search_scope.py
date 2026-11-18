"""Ro'yxat va qidiruvlar ruxsat doirasida: 'all_organization' yo'q foydalanuvchi faqat o'z tashkilotini ko'radi."""
from django.test import TestCase
from rest_framework.test import APIClient

from main.testing import make_employee, make_org, make_region


class SearchScopeTests(TestCase):
    def setUp(self):
        self.region = make_region()
        self.mine = make_org("client")
        self.worker = make_org("worker")
        self.other = make_org("client")
        self.user, self.me = make_employee(self.mine, self.region, perms=["main.view_employee"], last="Mijoz")
        make_employee(self.mine, self.region, last="Hamkasb")
        make_employee(self.worker, self.region, last="Usta")
        make_employee(self.other, self.region, last="Begona")
        self.c = APIClient()
        self.c.force_login(self.user)

    def _names(self, params):
        r = self.c.get("/api/v1/employees/", params)
        self.assertEqual(r.status_code, 200, r.data)
        return {x["last_name"] if "last_name" in x else x["full_name"] for x in r.data["results"]}

    def test_employee_search_only_own_organization(self):
        for params in ({"search": "Usta"}, {"search": "Begona"}, {"organization": self.worker.id}, {"organization": self.other.id, "search": "Begona"}):
            self.assertEqual(self._names(params), set(), params)
        self.assertEqual(len(self._names({"search": "Hamkasb"})), 1)

    def test_organizations_only_own(self):
        r = self.c.get("/api/v1/organizations/", {"search": "", "page_size": 50})
        self.assertEqual({o["id"] for o in r.data["results"]}, {self.mine.id})

    def test_all_organization_sees_everyone(self):
        user, _ = make_employee(self.worker, self.region, perms=["main.view_employee", "main.all_organization"], last="Katta")
        c = APIClient()
        c.force_login(user)
        r = c.get("/api/v1/employees/", {"search": "Begona"})
        self.assertEqual(r.data["count"], 1)


class MaterialCategoryScopeTests(TestCase):
    """/material-categories/ — superuser va all_organization bo'lsa ham faqat o'z tashkiloti (materiallar ham shunday)."""

    def test_only_own_organization(self):
        from main.models import MaterialCategory
        region = make_region()
        mine, other = make_org("client"), make_org("client")
        a = MaterialCategory.objects.create(organization=mine, name="Meniki")
        MaterialCategory.objects.create(organization=other, name="Begona")
        for kw in ({"perms": ["main.all_organization"]}, {"superuser": True}):
            user, _ = make_employee(mine, region, **kw)
            c = APIClient()
            c.force_login(user)
            r = c.get("/api/v1/material-categories/", {"page_size": 50})
            self.assertEqual([x["id"] for x in r.data["results"]], [a.id], kw)
