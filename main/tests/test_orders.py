"""Ariza: "surat" (snapshot), ATM arizasi tasdiqlanmasligi, qabul qilish, bot orqali baholash."""
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from bot import services as bot_services
from main.models import Order
from main.testing import make_department, make_employee, make_goal, make_org, make_region


class OrderSnapshotTests(TestCase):
    def setUp(self):
        self.client_org = make_org("client")
        self.worker_org = make_org("worker")
        self.region = make_region()
        self.dep = make_department(self.client_org, self.region)
        self.goal = make_goal(self.worker_org)

    def test_snapshot_filled_on_create(self):
        _, sender = make_employee(self.client_org, self.region, self.dep)
        order = Order.objects.create(sender=sender, goal=self.goal)
        self.assertEqual(order.sender_organization_id, self.client_org.id)
        self.assertEqual(order.sender_region_id, self.region.id)
        self.assertEqual(order.sender_department_id, self.dep.id)

    def test_snapshot_does_not_change_when_sender_moves(self):
        _, sender = make_employee(self.client_org, self.region, self.dep)
        order = Order.objects.create(sender=sender, goal=self.goal)
        sender.organization = self.worker_org
        sender.region = make_region()
        sender.department = None
        sender.save()
        order.refresh_from_db()
        self.assertEqual(order.sender_organization_id, self.client_org.id)
        self.assertEqual(order.sender_region_id, self.region.id)
        self.assertEqual(order.sender_department_id, self.dep.id)

    def test_sender_without_region_has_empty_region_snapshot(self):
        # Bu holatda ariza hududga qarab filtrlanganda hech kimga ko'rinmaydi (admin panelda tuzatiladi)
        _, sender = make_employee(self.client_org, None, None)
        order = Order.objects.create(sender=sender, goal=self.goal)
        self.assertEqual(order.sender_organization_id, self.client_org.id)
        self.assertIsNone(order.sender_region_id)

    def test_receiver_region_set_when_receiver_assigned(self):
        _, sender = make_employee(self.client_org, self.region)
        _, receiver = make_employee(self.worker_org, make_region())
        order = Order.objects.create(sender=sender, goal=self.goal)
        self.assertIsNone(order.receiver_region_id)
        order.receiver = receiver
        order.status = "process"
        order.save()
        order.refresh_from_db()
        self.assertEqual(order.receiver_region_id, receiver.region_id)


class AtmOrderApprovalTests(TestCase):
    """ATM (worker) arizasi hech qachon 'Tasdiqlandi' bo'lmasligi kerak: bu faqat omborxona arizasida."""

    def setUp(self):
        self.client_org = make_org("client")
        self.worker_org = make_org("worker")
        self.region = make_region()
        self.atm_goal = make_goal(self.worker_org)
        _, self.sender = make_employee(self.client_org, self.region)
        _, self.receiver = make_employee(self.worker_org, self.region)

    def _finished_order(self, goal):
        order = Order.objects.create(sender=self.sender, goal=goal, receiver=self.receiver, status="finished")
        order.refresh_from_db()
        return order

    def test_client_confirmer_cannot_approve_atm_order_on_site(self):
        order = self._finished_order(self.atm_goal)
        user, _ = make_employee(self.client_org, self.region, perms=["main.confirm_order", "main.change_order"])
        self.client.force_login(user)
        self.client.post(reverse("order_agrement_material"), {"order_id": order.id, "action": "approved"})
        order.refresh_from_db()
        self.assertEqual(order.status, "finished")

    def test_worker_cannot_confirm_on_site(self):
        order = self._finished_order(self.atm_goal)
        user, _ = make_employee(self.worker_org, self.region, perms=["main.confirm_order", "main.change_order"])
        self.client.force_login(user)
        response = self.client.post(reverse("order_agrement_material"), {"order_id": order.id, "action": "approved"})
        self.assertEqual(response.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.status, "finished")

    def test_api_confirm_rejects_atm_order(self):
        order = self._finished_order(self.atm_goal)
        user, _ = make_employee(self.client_org, self.region, perms=["main.confirm_order", "main.change_order"])
        api = APIClient()
        api.force_authenticate(user)
        response = api.post(f"/api/v1/orders/{order.id}/confirm/", {"action": "approved", "items": []}, format="json")
        self.assertIn(response.status_code, (400, 403, 404))
        order.refresh_from_db()
        self.assertEqual(order.status, "finished")


class OrderDecideAndBotRatingTests(TestCase):
    def setUp(self):
        self.client_org = make_org("client")
        self.worker_org = make_org("worker")
        self.region = make_region()
        self.atm_goal = make_goal(self.worker_org)
        self.barn_goal = make_goal(self.client_org)
        self.sender_user, self.sender = make_employee(self.client_org, self.region)
        _, self.receiver = make_employee(self.worker_org, self.region)

    def _order(self, goal, status):
        return Order.objects.create(sender=self.sender, goal=goal, receiver=self.receiver, status=status)

    def test_sender_accepts_with_rating(self):
        order = self._order(self.atm_goal, "finished")
        self.client.force_login(self.sender_user)
        with mock.patch("main.order_views.notify_order_status_change"):
            self.client.post(reverse("order_decide", args=[order.id]), {"action": "accepted", "rating": "5"})
        order.refresh_from_db()
        self.assertEqual((order.status, order.rating), ("accepted", 5))

    def test_bad_rating_rejected(self):
        order = self._order(self.atm_goal, "finished")
        self.client.force_login(self.sender_user)
        self.client.post(reverse("order_decide", args=[order.id]), {"action": "accepted", "rating": "9"})
        order.refresh_from_db()
        self.assertEqual(order.status, "finished")

    def test_stranger_cannot_decide(self):
        order = self._order(self.atm_goal, "finished")
        user, _ = make_employee(self.client_org, self.region)
        self.client.force_login(user)
        response = self.client.post(reverse("order_decide", args=[order.id]), {"action": "accepted", "rating": "5"})
        self.assertEqual(response.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.status, "finished")

    def test_bot_rating_accepts_finished_atm_order(self):
        order = self._order(self.atm_goal, "finished")
        with mock.patch.object(bot_services, "_push_status_change"):
            result = bot_services.rate_order(self.sender, order.id, 4)
        self.assertTrue(result.ok)
        order.refresh_from_db()
        self.assertEqual((order.status, order.rating), ("accepted", 4))

    def test_bot_rating_does_not_touch_barn_or_unfinished_orders(self):
        barn = self._order(self.barn_goal, "finished")
        process = self._order(self.atm_goal, "process")
        for order in (barn, process):
            with mock.patch.object(bot_services, "_push_status_change"):
                result = bot_services.rate_order(self.sender, order.id, 5)
            self.assertFalse(result.ok)
            order.refresh_from_db()
            self.assertNotEqual(order.status, "accepted")

    def test_bot_rating_range(self):
        order = self._order(self.atm_goal, "finished")
        self.assertFalse(bot_services.rate_order(self.sender, order.id, 0).ok)
        self.assertFalse(bot_services.rate_order(self.sender, order.id, 6).ok)
