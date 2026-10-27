"""api/spa/orders.py — ATM arizalari: ma'lumotnomalar, tafsilotlar, texnikalar, materialni o'chirish, akt."""
import base64
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from main.models import (
    Deed, DeedConsent, Material, MaterialMovement, Order, OrderGoal, OrderMaterial, Technics,
)
from main.testing import make_department, make_employee, make_goal, make_org, make_region

BASE = "/api/v1/spa/orders"


def client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


class OrdersSpaTests(TestCase):
    def setUp(self):
        self.atm = make_org("worker")
        self.client_org = make_org("client")
        self.region = make_region()
        self.dep = make_department(self.client_org, self.region)
        self.goal = make_goal(self.atm, "Kompyuter ta'miri")
        self.client_goal = make_goal(self.client_org, "Omborxona")

        self.sender_user, self.sender = make_employee(self.client_org, self.region, self.dep, first="Sardor", last="Toshmatov")
        self.worker_user, self.worker = make_employee(self.atm, self.region, perms=["main.change_order"], first="Bekzod")
        self.other_worker_user, self.other_worker = make_employee(self.atm, self.region, perms=["main.change_order"])
        self.stranger_user, self.stranger = make_employee(self.client_org, self.region)
        OrderGoal.objects.create(employee=self.worker).goal.set([self.goal])

        self.order = Order.objects.create(sender=self.sender, goal=self.goal, message_sender="Yoqilmayapti", status="viewed")
        self.order.receiver = self.worker
        self.order.status = "process"
        self.order.save()

    # ---------- ma'lumotnomalar ----------

    def test_goals_lists_only_worker_goals_for_any_employee(self):
        r = client(self.sender_user).get(f"{BASE}/goals/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual([g["id"] for g in r.data], [self.goal.id])

    def test_organizations_and_employees_require_add_order(self):
        self.assertEqual(client(self.sender_user).get(f"{BASE}/organizations/").status_code, 403)
        self.assertEqual(client(self.sender_user).get(f"{BASE}/organizations/{self.client_org.id}/employees/").status_code, 403)
        user, _ = make_employee(self.atm, self.region, perms=["main.add_order"])
        r = client(user).get(f"{BASE}/organizations/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(self.client_org.id, [o["id"] for o in r.data])
        r = client(user).get(f"{BASE}/organizations/{self.client_org.id}/employees/")
        self.assertEqual(r.status_code, 200)
        ids = [e["id"] for e in r.json()["results"]]
        self.assertIn(self.sender.id, ids)

    # ---------- tafsilotlar ----------

    def test_detail_visible_to_participants_with_person_info(self):
        r = client(self.sender_user).get(f"{BASE}/{self.order.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["sender_info"]["full_name"], self.sender.full_name)
        self.assertEqual(r.data["sender_info"]["department"], self.dep.name)
        self.assertEqual(r.data["receiver_info"]["id"], self.worker.id)
        self.assertEqual(client(self.worker_user).get(f"{BASE}/{self.order.id}/").status_code, 200)

    def test_detail_hidden_from_unrelated_employee(self):
        self.assertEqual(client(self.stranger_user).get(f"{BASE}/{self.order.id}/").status_code, 404)

    def test_new_order_visible_to_eligible_receiver(self):
        new = Order.objects.create(sender=self.sender, goal=self.goal, status="viewed")
        self.assertEqual(client(self.worker_user).get(f"{BASE}/{new.id}/").status_code, 200)

    # ---------- yangi arizani qabul qilish / rad etish (izoh bilan) ----------

    API = "/api/v1/orders"

    def post(self, user, order, action, data=None):
        return client(user).post(f"{self.API}/{order.id}/{action}/", data or {}, format="json")

    def test_accept_saves_comment(self):
        new = Order.objects.create(sender=self.sender, goal=self.goal, status="viewed")
        r = self.post(self.worker_user, new, "accept", {"message": "Ertaga boraman"})
        self.assertEqual(r.status_code, 200, r.data)
        new.refresh_from_db()
        self.assertEqual((new.status, new.receiver_id, new.message_receiver), ("process", self.worker.id, "Ertaga boraman"))

    def test_reject_new_order_with_reason(self):
        new = Order.objects.create(sender=self.sender, goal=self.goal, status="viewed")
        r = self.post(self.worker_user, new, "reject", {"message": "Sabab"})
        self.assertEqual(r.status_code, 200, r.data)
        new.refresh_from_db()
        self.assertEqual((new.status, new.receiver_id, new.message_receiver), ("rejected", self.worker.id, "Sabab"))
        # qayta amal bajarib bo'lmaydi; bekor qilish ijrochi uchun yo'q
        self.assertEqual(self.post(self.worker_user, new, "reject").status_code, 400)
        self.assertEqual(self.post(self.worker_user, new, "cancel").status_code, 404)

    def test_reject_new_order_only_by_eligible_worker(self):
        new = Order.objects.create(sender=self.sender, goal=self.goal, status="viewed")
        # kategoriyaga biriktirilmagan ATM xodimi / oddiy xodim
        self.assertEqual(self.post(self.other_worker_user, new, "reject").status_code, 400)
        self.assertEqual(self.post(self.stranger_user, new, "reject").status_code, 403)
        new.refresh_from_db()
        self.assertEqual(new.status, "viewed")

    def test_reject_requires_a_reason(self):
        new = Order.objects.create(sender=self.sender, goal=self.goal, status="viewed")
        for body in ({}, {"message": ""}, {"message": "   "}):
            r = self.post(self.worker_user, new, "reject", body)
            self.assertEqual(r.status_code, 400, body)
            self.assertIn("message", r.data)
        new.refresh_from_db()
        self.assertEqual(new.status, "viewed")

    def test_reject_blocked_after_accept(self):
        self.assertEqual(self.post(self.worker_user, self.order, "reject").status_code, 400)

    def test_finish_comment_is_saved(self):
        r = self.post(self.worker_user, self.order, "finish", {"message": "Almashtirildi"})
        self.assertEqual(r.status_code, 200, r.data)
        self.order.refresh_from_db()
        self.assertEqual((self.order.status, self.order.message_receiver), ("finished", "Almashtirildi"))

    # ---------- texnikalar ----------

    def test_technics_of_sender_only_for_receiver(self):
        t = Technics.objects.create(name="HP ProBook", employee=self.sender, serial="SN1")
        Technics.objects.create(name="Begona", employee=self.stranger)
        r = client(self.worker_user).get(f"{BASE}/{self.order.id}/technics/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual([x["id"] for x in r.json()["results"]], [t.id])
        self.assertEqual(client(self.other_worker_user).get(f"{BASE}/{self.order.id}/technics/").status_code, 403)
        self.assertEqual(client(self.sender_user).get(f"{BASE}/{self.order.id}/technics/").status_code, 403)

    # ---------- materialni o'chirish ----------

    def _material_line(self, n=2):
        mat = Material.objects.create(name="Toner", organization=self.atm, number=5)
        om = OrderMaterial.objects.create(order=self.order, material=mat, number=n)
        return mat, om

    def test_material_delete_returns_stock(self):
        mat, om = self._material_line(2)
        r = client(self.worker_user).post(f"{BASE}/materials/{om.id}/delete/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(OrderMaterial.objects.filter(pk=om.pk).exists())
        mat.refresh_from_db()
        self.assertEqual(mat.number, 7)
        self.assertTrue(MaterialMovement.objects.filter(material=mat, income=2).exists())

    def test_material_delete_only_by_receiver(self):
        _, om = self._material_line()
        self.assertEqual(client(self.other_worker_user).post(f"{BASE}/materials/{om.id}/delete/").status_code, 403)
        self.assertEqual(client(self.sender_user).post(f"{BASE}/materials/{om.id}/delete/").status_code, 403)
        self.assertTrue(OrderMaterial.objects.filter(pk=om.pk).exists())

    def test_material_delete_blocked_after_accept(self):
        _, om = self._material_line()
        Order.objects.filter(pk=self.order.pk).update(status="accepted")
        self.assertEqual(client(self.worker_user).post(f"{BASE}/materials/{om.id}/delete/").status_code, 400)

    # ---------- akt ----------

    def test_deed_get_returns_signers_and_body(self):
        self._material_line(1)
        r = client(self.worker_user).get(f"{BASE}/{self.order.id}/deed/")
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertIn(f"DALOLATNOMA № {self.order.id}", r.data["body"])
        self.assertIn('id="sender_name1"', r.data["body"])
        self.assertIn(self.sender.id, [e["id"] for e in r.data["employees"]])
        self.assertNotIn(self.worker.id, [e["id"] for e in r.data["employees"]])


    def test_deed_only_for_receiver(self):
        self.assertEqual(client(self.other_worker_user).get(f"{BASE}/{self.order.id}/deed/").status_code, 403)
        self.assertEqual(client(self.sender_user).get(f"{BASE}/{self.order.id}/deed/").status_code, 403)

    @mock.patch("api.spa.orders.notify_deed_sender")
    @mock.patch("main.order_views.add_text_watermark_pdf_bytes", side_effect=lambda b, t: b)
    @mock.patch("main.order_views.deed_to_pdf_bytes", return_value=b"%PDF-1.4 test")
    def test_deed_post_creates_deed_with_consents(self, pdf, wm, notify):
        signer = self.stranger
        body = '<div><b>DALOLATNOMA</b><script>alert(1)</script></div>'
        r = client(self.worker_user).post(
            f"{BASE}/{self.order.id}/deed/",
            {"sender": signer.id, "message": "Iltimos imzolang", "body_encoded": base64.b64encode(body.encode()).decode()},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        deed = Deed.objects.get(pk=r.data["id"])
        self.assertEqual(deed.sender_id, signer.id)
        self.assertEqual(deed.user_id, self.worker.id)
        self.assertEqual(list(deed.orders.values_list("id", flat=True)), [self.order.id])
        self.assertNotIn("<script>", deed.body)
        self.assertEqual(
            set(DeedConsent.objects.filter(deed=deed).values_list("employee_id", flat=True)),
            {self.sender.id, self.worker.id},
        )
        self.assertTrue(deed.file)
        notify.assert_called_once()

    def test_deed_post_validates_signer_and_body(self):
        c = client(self.worker_user)
        enc = base64.b64encode(b"<p>x</p>").decode()
        r = c.post(f"{BASE}/{self.order.id}/deed/", {"sender": self.worker.id, "body_encoded": enc}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("sender", r.data)
        r = c.post(f"{BASE}/{self.order.id}/deed/", {"sender": self.sender.id, "body_encoded": ""}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("body", r.data)
        self.assertFalse(Deed.objects.exists())
