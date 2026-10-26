"""ajax_load_departments (select2 ro'yxati): hudud doirasi, `all_regions` va `order=id` — API (/spa/reports/data/departments/) orqali."""
from django.test import TestCase
from rest_framework.test import APIClient

from main.models import Department
from main.testing import make_employee, make_org, make_region


class AjaxLoadDepartmentsTests(TestCase):
    def setUp(self):
        self.org = make_org("client")
        # Nomlar alifbo tartibiga TESKARI: ID tartibi nom tartibidan farq qilishi uchun
        self.region1 = make_region("Zzz hudud")
        self.region2 = make_region("Aaa hudud")
        self.dep_z = Department.objects.create(name="Zzz dep", organization=self.org, region=self.region1)
        self.dep_a = Department.objects.create(name="Aaa dep", organization=self.org, region=self.region1)
        self.dep_other = Department.objects.create(name="Boshqa hudud dep", organization=self.org, region=self.region2)
        user, _ = make_employee(make_org("worker"), self.region1, perms=["main.shop_employee"])      # hisobot ruxsati kerak
        self.api = APIClient()
        self.api.force_authenticate(user)
        self.url = "/api/v1/spa/reports/data/departments/"

    def _ids(self, params):
        return [int(item["id"]) for item in self.api.get(self.url, params).json()["results"]]

    def test_limited_to_user_region_by_default(self):
        self.assertEqual(set(self._ids({"organization": self.org.id})), {self.dep_z.id, self.dep_a.id})

    def test_all_regions_flag_lists_every_region(self):
        self.assertEqual(set(self._ids({"organization": self.org.id, "all_regions": "1"})),
                         {self.dep_z.id, self.dep_a.id, self.dep_other.id})

    def test_selected_region_is_applied(self):
        params = {"organization": self.org.id, "all_regions": "1", "region": self.region2.id}
        self.assertEqual(self._ids(params), [self.dep_other.id])

    def test_order_by_id_when_requested(self):
        params = {"organization": self.org.id, "region": self.region1.id, "order": "id"}
        self.assertEqual(self._ids(params), [self.dep_z.id, self.dep_a.id])
        self.assertEqual(self._ids({**params, "page": 1}), [self.dep_z.id, self.dep_a.id])        # sahifalangan rejim ham

    def test_default_order_is_by_name(self):
        params = {"organization": self.org.id, "region": self.region1.id, "page": 1}
        self.assertEqual(self._ids(params), [self.dep_a.id, self.dep_z.id])
