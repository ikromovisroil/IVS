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

    def test_parent_category_grants_children_but_not_vice_versa(self):
        """Ota kategoriya berilsa ichki kategoriyalari ham ruxsat etiladi; ichki berilsa ota ochilmaydi."""
        child = MaterialCategory.objects.create(name="Ruchkalar", organization=self.org, parent=self.cat)
        child_mat = Material.objects.create(name="Shariqli ruchka", organization=self.org, category=child, number=3)
        self.assertEqual(self._toggle(child_mat).status_code, 200)         # ota (self.cat) berilgan

        MaterialEmployee.objects.filter(employee=self.emp).delete()
        MaterialEmployee.objects.create(employee=self.emp).category.set([child])
        self.assertEqual(self._toggle(self.mat).status_code, 400)          # faqat ichki berilgan — ota yopiq
        self.assertEqual(MaterialCategory.allowed_ids(self.emp), {child.id})

    def test_catalog_tree_and_category_filter(self):
        child = MaterialCategory.objects.create(name="Ruchkalar", organization=self.org, parent=self.cat)
        child_mat = Material.objects.create(name="Shariqli ruchka", organization=self.org, category=child, number=3)
        tree = self.api.get("/api/v1/orders/selectable-categories/").data
        self.assertEqual(tree, [{"id": self.cat.id, "name": "Kanselyariya", "selectable": True, "children": [
            {"id": child.id, "name": "Ruchkalar", "selectable": True, "children": []}]}])         # "Boshqa" ruxsat etilmagan — ko'rinmaydi

        def ids(**q):
            return {m["id"] for m in self.api.get("/api/v1/orders/selectable-materials/", q).data["results"]}
        self.assertEqual(ids(), {self.mat.id, self.mat2.id, child_mat.id})
        self.assertEqual(ids(category=self.cat.id), {self.mat.id, self.mat2.id, child_mat.id})     # ota — ichkisi bilan
        self.assertEqual(ids(category=child.id), {child_mat.id})
        self.assertEqual(ids(category=self.hidden_cat.id), set())                                 # ruxsatsiz kategoriya filtrdan ham o'tmaydi

        # Faqat ichki berilsa: ota sarlavha sifatida chiqadi, lekin tanlab bo'lmaydi
        MaterialEmployee.objects.filter(employee=self.emp).delete()
        MaterialEmployee.objects.create(employee=self.emp).category.set([child])
        tree = self.api.get("/api/v1/orders/selectable-categories/").data
        self.assertEqual([(n["id"], n["selectable"], [c["id"] for c in n["children"]]) for n in tree],
                         [(self.cat.id, False, [child.id])])

    def test_deep_category_tree(self):
        """Ichma-ich kategoriyalar: avlodlari ham ruxsatga, filtrga va katalogga kiradi."""
        mid = MaterialCategory.objects.create(name="Qalamlar", organization=self.org, parent=self.cat)
        leaf = MaterialCategory.objects.create(name="Rangli qalamlar", organization=self.org, parent=mid)
        leaf_mat = Material.objects.create(name="Rangli qalam 12", organization=self.org, category=leaf, number=2)
        self.assertEqual(self._toggle(leaf_mat).status_code, 200)                                 # bobo berilgan — nevara ham ruxsat etilgan
        tree = self.api.get("/api/v1/orders/selectable-categories/").data
        self.assertEqual(tree[0]["children"][0]["children"][0]["id"], leaf.id)

        def ids(cat):
            return {m["id"] for m in self.api.get("/api/v1/orders/selectable-materials/", {"category": cat.id}).data["results"]}
        self.assertEqual(ids(mid), {leaf_mat.id})
        self.assertIn(leaf_mat.id, ids(self.cat))
        self.assertEqual(MaterialCategory.subtree_ids([self.cat.id]), {self.cat.id, mid.id, leaf.id})

        MaterialEmployee.objects.filter(employee=self.emp).delete()
        MaterialEmployee.objects.create(employee=self.emp).category.set([leaf])                   # faqat eng ichkisi: zanjir sarlavha bo'lib chiqadi
        tree = self.api.get("/api/v1/orders/selectable-categories/").data
        self.assertEqual([(tree[0]["selectable"], tree[0]["children"][0]["selectable"], tree[0]["children"][0]["children"][0]["selectable"])],
                         [(False, False, True)])

    def test_category_parent_rules(self):
        from django.core.exceptions import ValidationError
        child = MaterialCategory(name="Ichki", organization=self.org, parent=self.cat)
        child.full_clean()
        child.save()
        grand = MaterialCategory(name="3-daraja", organization=self.org, parent=child)            # ichma-ich bo'ladi
        grand.full_clean()
        grand.save()
        with self.assertRaises(ValidationError):                                                  # boshqa tashkilot
            MaterialCategory(name="Begona", organization=self.other_org, parent=self.cat).full_clean()
        self.cat.parent = grand                                                                   # o'z avlodi ichiga o'tmaydi (aylana)
        with self.assertRaises(ValidationError):
            self.cat.full_clean()
        self.cat.parent = self.hidden_cat                                                         # ostidagilari bilan 4 daraja bo'lib qoladi
        with self.assertRaises(ValidationError):
            self.cat.full_clean()
        self.cat.parent = None
        child.parent = self.hidden_cat                                                            # ostidagisi bilan 3 daraja — mumkin
        child.full_clean()
        child.parent = self.cat
        with self.assertRaises(ValidationError):                                                  # 4-daraja yaratib bo'lmaydi
            MaterialCategory(name="4-daraja", organization=self.org, parent=grand).full_clean()
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):                                                   # ichkisi bor — o'chmaydi
            self.cat.delete()

    def test_cart_add_saves_number_and_updates_existing(self):
        r = self.api.post(f"{BASE}/cart/add/", {"material": self.mat.id, "number": 4}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual([(i["material"], i["number"]) for i in self.api.get(f"{BASE}/cart/").data], [(self.mat.id, 4)])
        self.api.post(f"{BASE}/cart/add/", {"material": self.mat.id, "number": 7}, format="json")
        self.assertEqual(OrderMaterial.objects.filter(order__isnull=True, user=self.emp).count(), 1)
        self.assertEqual(OrderMaterial.objects.get(order__isnull=True, user=self.emp).number, 7)

    def test_cart_add_validates_number_and_material(self):
        for bad in (0, -1, "x", None, 1.5):
            r = self.api.post(f"{BASE}/cart/add/", {"material": self.mat.id, "number": bad}, format="json")
            self.assertEqual(r.status_code, 400, bad)
        self.assertEqual(self.api.post(f"{BASE}/cart/add/", {"material": self.hidden.id, "number": 1}, format="json").status_code, 400)
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
