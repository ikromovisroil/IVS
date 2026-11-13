"""api/roles.py — mijoz (worker bo'lmagan tashkilot) xodimiga sarflash va Zoom ruxsatlari ko'rinmaydi va berilmaydi."""
from django.test import TestCase
from rest_framework.test import APIClient

from main.models import OrderGoal
from main.testing import make_employee, make_goal, make_org, make_region

CLIENT_HIDDEN = {"material_service", "view_meeting", "add_meeting", "delete_meeting"}
ADMIN_PERMS = ["main.permission_employee", "main.change_employee", "main.view_employee"]


class ClientRolesTests(TestCase):
    def setUp(self):
        self.region = make_region()
        self.client_org = make_org("client")
        self.worker_org = make_org("worker")
        self.admin_user, self.admin = make_employee(self.client_org, self.region, perms=ADMIN_PERMS, last="Admin")
        self.client_user, self.client_emp = make_employee(self.client_org, self.region, last="Mijoz")
        self.worker_user, self.worker_emp = make_employee(self.worker_org, self.region, last="Usta")
        self.super_user, _ = make_employee(self.worker_org, self.region, superuser=True, last="Super")

    def _get(self, user, emp):
        c = APIClient()
        c.force_login(user)
        return c.get(f"/api/v1/employees/{emp.id}/permissions/")

    def test_client_target_has_no_service_or_zoom(self):
        r = self._get(self.admin_user, self.client_emp)
        self.assertEqual(r.status_code, 200, r.data)
        editable = {p["key"] for p in r.data["permissions"] if p["editable"]}
        self.assertFalse(editable & CLIENT_HIDDEN)
        self.assertIn("view_material", editable)
        self.assertIn("all_material_employee", {p["key"] for p in r.data["permissions"]})

    def test_worker_target_keeps_service_and_zoom(self):
        r = self._get(self.super_user, self.worker_emp)
        editable = {p["key"] for p in r.data["permissions"] if p["editable"]}
        self.assertTrue(CLIENT_HIDDEN <= editable)

    def test_permission_employee_alone_can_save(self):
        only_user, _ = make_employee(self.client_org, self.region, perms=["main.permission_employee"], last="Faqat")
        c = APIClient()
        c.force_login(only_user)
        r = c.put(f"/api/v1/employees/{self.client_emp.id}/permissions/",
                  {"permissions": {"view_material": True}}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["permissions"][[p["key"] for p in r.data["permissions"]].index("view_material")]["granted"])

    def test_cannot_grant_service_or_zoom_to_client(self):
        c = APIClient()
        c.force_login(self.admin_user)
        r = c.put(f"/api/v1/employees/{self.client_emp.id}/permissions/",
                  {"permissions": {"view_material": True, "material_service": True, "view_meeting": True}}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertCountEqual(r.data["ignored"], ["material_service", "view_meeting"])
        self.client_user.refresh_from_db()
        direct = set(self.client_user.user_permissions.values_list("codename", flat=True))
        self.assertIn("view_material", direct)
        self.assertNotIn("material_service", direct)
        self.assertNotIn("view_meeting", direct)


class GoalOptionsTests(TestCase):
    """"Ariza bajarish" ariza turlari: xodimning o'z tashkilotidagilari (tahrirlovchi superuser bo'lsa ham)."""

    def setUp(self):
        self.region = make_region()
        self.atm = make_org("worker")
        self.atm2 = make_org("worker")
        self.client_org = make_org("client")
        self.g_atm = make_goal(self.atm, "ATM turi")
        self.g_atm2 = make_goal(self.atm2, "Boshqa ATM turi")
        self.g_client = make_goal(self.client_org, "Mijoz turi")
        self.super_user, _ = make_employee(self.atm, self.region, superuser=True, last="Super")
        _, self.worker = make_employee(self.atm, self.region, last="Usta")
        _, self.keeper = make_employee(self.client_org, self.region, last="Omborchi")
        self.c = APIClient()
        self.c.force_login(self.super_user)

    def _goals(self, emp):
        r = self.c.get(f"/api/v1/employees/{emp.id}/permissions/")
        self.assertEqual(r.status_code, 200, r.data)
        return r.data["goals"]

    def test_worker_sees_only_own_org_goals(self):
        self.assertEqual([g["id"] for g in self._goals(self.worker)["options"]], [self.g_atm.id])

    def test_client_target_sees_own_org_goals_even_for_worker_superuser(self):
        self.assertEqual([g["id"] for g in self._goals(self.keeper)["options"]], [self.g_client.id])

    def test_foreign_goal_rejected_and_not_selected(self):
        og = OrderGoal.objects.create(employee=self.worker)
        og.goal.set([self.g_atm, self.g_atm2])          # eski ma'lumot: boshqa tashkilot turi ham biriktirilgan
        self.assertEqual(self._goals(self.worker)["selected"], [self.g_atm.id])
        r = self.c.put(f"/api/v1/employees/{self.worker.id}/permissions/",
                       {"permissions": {"change_order": True}, "goals": [self.g_atm2.id]}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.c.put(f"/api/v1/employees/{self.worker.id}/permissions/",
                       {"permissions": {"change_order": True}}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        ids = set(OrderGoal.goal.through.objects.filter(ordergoal__employee=self.worker).values_list("goal_id", flat=True))
        self.assertEqual(ids, {self.g_atm.id})          # boshqa tashkilot turi saqlanib qolmaydi
