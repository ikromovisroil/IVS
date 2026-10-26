"""Xodimni o'chirish (faolsizlantirish) va tahrirlash qoidalari (API: /api/v1/employees/)."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from rest_framework.test import APIClient

from main.models import Employee, Order
from main.testing import make_department, make_employee, make_goal, make_org, make_region

User = get_user_model()
BOSS_PERMS = ["main.view_employee", "main.delete_employee", "main.change_employee"]
URL = "/api/v1/employees/"


def api_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


class EmployeeRemovalTests(TestCase):
    def setUp(self):
        self.org = make_org("worker")
        self.region = make_region()
        self.dep = make_department(self.org, self.region)
        self.boss_user, self.boss = make_employee(self.org, self.region, perms=BOSS_PERMS, first="Boss", last="Rahbar")
        self.t_user, self.target = make_employee(
            self.org, self.region, self.dep, first="Sardor", last="Egamberdiyev", password="secret-pass-1",
        )
        self.api = api_for(self.boss_user)

    def _delete(self, employee, api=None):
        return (api or self.api).delete(f"{URL}{employee.id}/")

    def test_delete_clears_org_fields_but_keeps_record(self):
        self.assertEqual(self._delete(self.target).status_code, 204)
        emp = Employee.objects.get(pk=self.target.pk)          # bazadan o'chmaydi
        self.assertFalse(User.objects.get(pk=self.t_user.pk).is_active)
        for field in ("organization", "department", "directorate", "division", "rank", "region"):
            self.assertIsNone(getattr(emp, field), field)

    def test_deleted_employee_cannot_login(self):
        self.assertTrue(Client().login(username=self.t_user.username, password="secret-pass-1"))
        self._delete(self.target)
        self.assertFalse(Client().login(username=self.t_user.username, password="secret-pass-1"))

    def test_deleted_employee_is_hidden_from_list(self):
        def names():
            data = self.api.get(URL, {"organization": self.org.id}).json()
            return str(data["results"] if "results" in data else data)
        self.assertIn("Egamberdiyev", names())
        self._delete(self.target)
        self.assertNotIn("Egamberdiyev", names())

    def test_cannot_delete_yourself(self):
        self.assertEqual(self._delete(self.boss).status_code, 400)
        self.assertTrue(User.objects.get(pk=self.boss_user.pk).is_active)

    def test_delete_requires_permission(self):
        user, _ = make_employee(self.org, self.region)           # ruxsatsiz
        self.assertEqual(self._delete(self.target, api_for(user)).status_code, 403)
        self.assertTrue(User.objects.get(pk=self.t_user.pk).is_active)

    def test_cannot_delete_employee_of_other_organization(self):
        other = make_org("worker")
        _, stranger = make_employee(other, make_region())
        self.assertIn(self._delete(stranger).status_code, (403, 404))
        self.assertTrue(User.objects.get(pk=stranger.user_id).is_active)

    def test_order_snapshot_survives_deletion(self):
        goal = make_goal(self.org)
        order = Order.objects.create(sender=self.target, goal=goal, status="viewed")
        self.assertEqual(order.sender_organization_id, self.org.id)
        self._delete(self.target)
        order.refresh_from_db()
        self.assertEqual(order.sender_id, self.target.id)                # xodim bog'lanishi saqlanadi
        self.assertEqual(order.sender_organization_id, self.org.id)      # "surat" saqlanadi
        self.assertEqual(order.sender_region_id, self.region.id)


class EmployeeUpdateTests(TestCase):
    def setUp(self):
        self.org = make_org("worker")
        self.region = make_region()
        self.boss_user, _ = make_employee(self.org, self.region, perms=BOSS_PERMS)
        _, self.target = make_employee(self.org, self.region, first="Eski", last="Ism")
        self.api = api_for(self.boss_user)

    def _update(self, **extra):
        data = {"first_name": "Yangi", "last_name": "Ismi", "pinfl": ""}
        data.update(extra)
        return self.api.patch(f"{URL}{self.target.id}/", data, format="json")

    def _first_name(self):
        return Employee.objects.get(pk=self.target.pk).first_name

    def test_partial_update_without_pinfl_keeps_it(self):
        self.target.pinfl = "22222222222222"
        self.target.save()
        response = self.api.patch(f"{URL}{self.target.id}/", {"first_name": "Yangi"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        emp = Employee.objects.get(pk=self.target.pk)
        self.assertEqual((emp.first_name, emp.pinfl), ("Yangi", "22222222222222"))

    def test_blank_pinfl_rejected(self):
        self.assertEqual(self._update(pinfl="").status_code, 400)
        self.assertEqual(self._first_name(), "Eski")

    def test_valid_pinfl_saved(self):
        self._update(pinfl="12345678901234")
        self.assertEqual(Employee.objects.get(pk=self.target.pk).pinfl, "12345678901234")

    def test_bad_pinfl_rejected(self):
        for bad in ("123", "abcdefghijklmn", "123456789012345"):
            response = self._update(first_name="Boshqa", pinfl=bad)
            self.assertEqual(response.status_code, 400, bad)
            self.assertEqual(self._first_name(), "Eski", bad)

    def test_duplicate_pinfl_rejected(self):
        make_employee(self.org, self.region, pinfl="11111111111111")
        self.assertEqual(self._update(first_name="Boshqa", pinfl="11111111111111").status_code, 400)
        self.assertEqual(self._first_name(), "Eski")

    def test_names_required(self):
        self.assertEqual(self._update(first_name="").status_code, 400)
        self.assertEqual(self._first_name(), "Eski")
