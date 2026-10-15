"""Xodimni o'chirish (faolsizlantirish) va tahrirlash qoidalari."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from main.models import Employee, Order
from main.testing import make_department, make_employee, make_goal, make_org, make_region

User = get_user_model()
BOSS_PERMS = ["main.view_employee", "main.delete_employee", "main.change_employee"]


class EmployeeRemovalTests(TestCase):
    def setUp(self):
        self.org = make_org("worker")
        self.region = make_region()
        self.dep = make_department(self.org, self.region)
        self.boss_user, self.boss = make_employee(self.org, self.region, perms=BOSS_PERMS, first="Boss", last="Rahbar")
        self.t_user, self.target = make_employee(
            self.org, self.region, self.dep, first="Sardor", last="Egamberdiyev", password="secret-pass-1",
        )
        self.client.force_login(self.boss_user)

    def _delete(self, employee):
        return self.client.post(reverse("employee_delete"), {"employee_id": employee.id})

    def test_delete_clears_org_fields_but_keeps_record(self):
        self._delete(self.target)
        emp = Employee.objects.get(pk=self.target.pk)          # bazadan o'chmaydi
        self.assertFalse(User.objects.get(pk=self.t_user.pk).is_active)
        for field in ("organization", "department", "directorate", "division", "rank", "region"):
            self.assertIsNone(getattr(emp, field), field)

    def test_deleted_employee_cannot_login(self):
        self.assertTrue(Client().login(username=self.t_user.username, password="secret-pass-1"))
        self._delete(self.target)
        self.assertFalse(Client().login(username=self.t_user.username, password="secret-pass-1"))

    def test_deleted_employee_is_hidden_from_table(self):
        url = reverse("employee") + f"?organization={self.org.id}"
        self.assertContains(self.client.get(url), "Egamberdiyev")
        self._delete(self.target)
        self.assertNotContains(self.client.get(url), "Egamberdiyev")

    def test_cannot_delete_yourself(self):
        self._delete(self.boss)
        self.assertTrue(User.objects.get(pk=self.boss_user.pk).is_active)

    def test_delete_requires_permission(self):
        user, _ = make_employee(self.org, self.region)           # ruxsatsiz
        self.client.force_login(user)
        self.assertEqual(self._delete(self.target).status_code, 403)
        self.assertTrue(User.objects.get(pk=self.t_user.pk).is_active)

    def test_cannot_delete_employee_of_other_organization(self):
        other = make_org("worker")
        _, stranger = make_employee(other, make_region())
        self.assertEqual(self._delete(stranger).status_code, 403)

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
        self.client.force_login(self.boss_user)

    def _update(self, **extra):
        data = {"employee_id": self.target.id, "first_name": "Yangi", "last_name": "Ismi", "pinfl": ""}
        data.update(extra)
        return self.client.post(reverse("employee_update"), data)

    def test_pinfl_is_optional(self):
        self._update(pinfl="")
        emp = Employee.objects.get(pk=self.target.pk)
        self.assertEqual(emp.first_name, "Yangi")
        self.assertIsNone(emp.pinfl)

    def test_valid_pinfl_saved(self):
        self._update(pinfl="12345678901234")
        self.assertEqual(Employee.objects.get(pk=self.target.pk).pinfl, "12345678901234")

    def test_bad_pinfl_rejected(self):
        for bad in ("123", "abcdefghijklmn", "123456789012345"):
            self._update(first_name="Boshqa", pinfl=bad)
            self.assertEqual(Employee.objects.get(pk=self.target.pk).first_name, "Eski", bad)

    def test_duplicate_pinfl_rejected(self):
        make_employee(self.org, self.region, pinfl="11111111111111")
        self._update(first_name="Boshqa", pinfl="11111111111111")
        self.assertEqual(Employee.objects.get(pk=self.target.pk).first_name, "Eski")

    def test_names_required(self):
        self._update(first_name="")
        self.assertEqual(Employee.objects.get(pk=self.target.pk).first_name, "Eski")
