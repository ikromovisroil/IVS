"""Admin panel: arizalar ro'yxati (materiallar ID), surat maydonlarini tahrirlash, o'chirish qoidalari."""
from django.contrib import admin
from django.forms.models import model_to_dict
from django.test import RequestFactory, TestCase

from main.admin import OrderAdmin
from main.models import Deed, Employee, Material, Order, OrderMaterial
from main.testing import make_employee, make_goal, make_org, make_region

ADMIN_ORDERS = "/ivc_service_admin_panel/main/order/"


class OrderAdminTests(TestCase):
    def setUp(self):
        self.org = make_org("client")
        self.worker = make_org("worker")
        self.region = make_region()
        self.su, self.su_emp = make_employee(self.org, self.region, superuser=True)
        _, self.sender = make_employee(self.org, None)          # hududi yo'q xodim
        self.goal = make_goal(self.worker)
        self.client.force_login(self.su)

    def test_list_shows_attached_material_ids(self):
        m1 = Material.objects.create(name="Kabel", employee=self.su_emp, number=10)
        m2 = Material.objects.create(name="Sichqoncha", employee=self.su_emp, number=10)
        with_materials = Order.objects.create(sender=self.sender, goal=self.goal)
        Order.objects.create(sender=self.sender, goal=self.goal)          # materialsiz
        OrderMaterial.objects.create(order=with_materials, material=m1, number=1)
        OrderMaterial.objects.create(order=with_materials, material=m2, number=2)
        response = self.client.get(ADMIN_ORDERS)
        self.assertContains(response, "Materiallar (ID)")
        self.assertContains(response, f"{m1.id}, {m2.id}")

    def test_snapshot_fields_editable_in_admin_form(self):
        order = Order.objects.create(sender=self.sender, goal=self.goal)
        self.assertIsNone(order.sender_region_id)
        model_admin = OrderAdmin(Order, admin.site)
        request = RequestFactory().post("/")
        request.user = self.su
        form_class = model_admin.get_form(request, order)
        data = {k: ("" if v is None else v) for k, v in model_to_dict(order).items() if k in form_class.base_fields}
        data.update({"sender_region": self.region.pk, "sender_organization": self.org.pk, "receiver_region": ""})
        form = form_class(data, instance=order)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        model_admin.save_model(request, form.save(commit=False), form, True)
        order.refresh_from_db()
        self.assertEqual(order.sender_region_id, self.region.pk)
        self.assertIsNone(order.receiver_region_id)

    def test_order_admin_page_has_snapshot_selects(self):
        order = Order.objects.create(sender=self.sender, goal=self.goal)
        response = self.client.get(f"{ADMIN_ORDERS}{order.pk}/change/")
        self.assertEqual(response.status_code, 200)
        for name in ("sender_region", "sender_department", "receiver_region", "sender_organization"):
            self.assertContains(response, f'name="{name}"')


class AdminDeletePermissionTests(TestCase):
    """Hujjat va xodim admin panelda o'chiriladi; ariza va material harakati - yo'q."""

    def setUp(self):
        org = make_org("worker")
        self.su, _ = make_employee(org, make_region(), superuser=True)
        self.request = RequestFactory().get("/")
        self.request.user = self.su

    def _can_delete(self, model):
        return admin.site._registry[model].has_delete_permission(self.request)

    def test_deed_and_employee_can_be_deleted(self):
        self.assertTrue(self._can_delete(Deed))
        self.assertTrue(self._can_delete(Employee))

    def test_order_cannot_be_deleted(self):
        self.assertFalse(self._can_delete(Order))
