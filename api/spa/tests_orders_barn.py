"""api/spa/orders_barn.py — omborxona arizalari (savat, ariza yaratish, tafsilotlar, arizadagi materialni o'chirish)."""
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from main.models import Material, MaterialCategory, MaterialEmployee, MaterialMovement, Order, OrderGoal, OrderMaterial
from main.testing import make_employee, make_goal, make_org, make_region

BASE = "/api/v1/spa/orders-barn"


class BarnSpaTests(TestCase):
    def setUp(self):
        self.org = make_org("client")
        self.other_org = make_org("client")
        self.worker_org = make_org("worker")
        self.region = make_region()
        self.goal = make_goal(self.org)
        self.cat = MaterialCategory.objects.create(name="Kanselyariya", organization=self.org)
        self.hidden_cat = MaterialCategory.objects.create(name="Boshqa", organization=self.org)
        self.mat = Material.objects.create(name="Qog'oz", organization=self.org, category=self.cat, number=10, price=100)
        self.mat2 = Material.objects.create(name="Ruchka", organization=self.org, category=self.cat, number=5, price=10)
        self.hidden = Material.objects.create(name="Yashirin", organization=self.org, category=self.hidden_cat, number=5)

        self.user, self.emp = make_employee(self.org, self.region, first="Ali", last="Valiyev")
        MaterialEmployee.objects.create(employee=self.emp).category.set([self.cat])
        self.keeper_user, self.keeper = make_employee(self.org, self.region, perms=["main.change_order"], first="Omborchi")
        OrderGoal.objects.create(employee=self.keeper).goal.set([self.goal])

        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def _toggle(self, material):
        return self.api.post(f"{BASE}/cart/toggle/", {"material": material.id}, format="json")

    # ---------- savat ----------

    def test_cart_toggle_adds_and_removes(self):
        r = self._toggle(self.mat)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["action"], "added")
        self.assertEqual([i["material"] for i in self.api.get(f"{BASE}/cart/").data], [self.mat.id])
        r = self._toggle(self.mat)
        self.assertEqual(r.data["action"], "removed")
        self.assertEqual(self.api.get(f"{BASE}/cart/").data, [])

    def test_cart_toggle_rejects_material_outside_allowed_categories(self):
        self.assertEqual(self._toggle(self.hidden).status_code, 400)
        foreign = Material.objects.create(name="Begona", organization=self.other_org, category=self.cat)
        self.assertEqual(self._toggle(foreign).status_code, 400)
        self.assertFalse(OrderMaterial.objects.filter(order__isnull=True).exists())

    def test_cart_delete_only_own_items(self):
        self._toggle(self.mat)
        item = OrderMaterial.objects.get(order__isnull=True, user=self.emp)
        other_user, _ = make_employee(self.org, self.region)
        other = APIClient()
        other.force_authenticate(other_user)
        self.assertEqual(other.delete(f"{BASE}/cart/{item.id}/").status_code, 404)
        self.assertEqual(self.api.delete(f"{BASE}/cart/{item.id}/").status_code, 204)
        self.assertFalse(OrderMaterial.objects.filter(pk=item.id).exists())

    def test_worker_employee_forbidden(self):
        worker_user, _ = make_employee(self.worker_org, self.region)
        c = APIClient()
        c.force_authenticate(worker_user)
        self.assertEqual(c.get(f"{BASE}/cart/").status_code, 403)
        self.assertEqual(c.post(f"{BASE}/cart/submit/", {"goal": self.goal.id}, format="json").status_code, 403)

    # ---------- ariza yaratish ----------

    @mock.patch("api.spa.orders_barn.notify_eligible_employees_new_order")
    def test_submit_creates_order_from_cart(self, notify):
        self._toggle(self.mat)
        self._toggle(self.mat2)
        item = OrderMaterial.objects.get(order__isnull=True, material=self.mat)
        r = self.api.post(f"{BASE}/cart/submit/", {"goal": self.goal.id, "body": " Kerak ", "numbers": {str(item.id): 7}}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        order = Order.objects.get(pk=r.data["id"])
        self.assertEqual((order.status, order.sender_id, order.message_sender), ("viewed", self.emp.id, "Kerak"))
        self.assertEqual(dict(order.materials.values_list("material_id", "number")), {self.mat.id: 7, self.mat2.id: 1})
        self.assertFalse(OrderMaterial.objects.filter(order__isnull=True, user=self.emp).exists())
        notify.assert_called_once()

    def test_submit_validation(self):
        r = self.api.post(f"{BASE}/cart/submit/", {"goal": self.goal.id}, format="json")
        self.assertEqual(r.status_code, 400)   # savat bo'sh
        self._toggle(self.mat)
        self.assertEqual(self.api.post(f"{BASE}/cart/submit/", {}, format="json").status_code, 400)
        foreign_goal = make_goal(self.other_org)
        self.assertEqual(self.api.post(f"{BASE}/cart/submit/", {"goal": foreign_goal.id}, format="json").status_code, 400)
        item = OrderMaterial.objects.get(order__isnull=True)
        r = self.api.post(f"{BASE}/cart/submit/", {"goal": self.goal.id, "numbers": {str(item.id): 0}}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Order.objects.exists())

    # ---------- tafsilotlar ----------

    def _order(self, status="viewed", receiver=None, given=None):
        order = Order.objects.create(goal=self.goal, sender=self.emp, status="viewed")
        OrderMaterial.objects.create(order=order, user=self.emp, material=self.mat, number=3, given=given)
        if receiver:
            order.receiver = receiver
        order.status = status
        order.save()
        return order

    def test_detail_for_sender_and_new_order_for_keeper(self):
        order = self._order()
        r = self.api.get(f"{BASE}/orders/{order.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["people"]["sender"]["full_name"], self.emp.full_name)
        self.assertIsNone(r.data["people"]["receiver"])
        self.assertEqual(r.data["materials"][0]["stock"], 10)

        keeper = APIClient()
        keeper.force_authenticate(self.keeper_user)
        self.assertEqual(keeper.get(f"{BASE}/orders/{order.id}/").status_code, 200)   # barn_receiver_new

        stranger_user, _ = make_employee(self.other_org, make_region())
        stranger = APIClient()
        stranger.force_authenticate(stranger_user)
        self.assertEqual(stranger.get(f"{BASE}/orders/{order.id}/").status_code, 404)

    # ---------- arizadagi materialni o'chirish (ordermaterial_delete) ----------

    def test_receiver_deletes_given_material_and_stock_returns(self):
        order = self._order("finished", receiver=self.keeper, given=2)
        om = order.materials.get()
        keeper = APIClient()
        keeper.force_authenticate(self.keeper_user)
        r = keeper.post(f"{BASE}/order-materials/{om.id}/delete/")
        self.assertEqual(r.status_code, 200, getattr(r, "data", r.content))
        self.assertFalse(OrderMaterial.objects.filter(pk=om.id).exists())
        self.mat.refresh_from_db()
        self.assertEqual(self.mat.number, 12)
        self.assertTrue(MaterialMovement.objects.filter(material=self.mat, income=2).exists())

    def test_non_receiver_cannot_delete_material(self):
        order = self._order("process", receiver=self.keeper)
        om = order.materials.get()
        self.assertEqual(self.api.post(f"{BASE}/order-materials/{om.id}/delete/").status_code, 403)
        self.assertTrue(OrderMaterial.objects.filter(pk=om.id).exists())

    def test_cannot_delete_material_of_closed_order(self):
        order = self._order("approved", receiver=self.keeper, given=1)
        om = order.materials.get()
        keeper = APIClient()
        keeper.force_authenticate(self.keeper_user)
        r = keeper.post(f"{BASE}/order-materials/{om.id}/delete/")
        self.assertEqual(r.status_code, 400)
        self.assertTrue(OrderMaterial.objects.filter(pk=om.id).exists())
