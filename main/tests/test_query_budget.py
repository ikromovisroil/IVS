"""
So'rovlar byudjeti (N+1 ga qarshi qo'riqchi): ro'yxat sahifasida qatorlar soni oshganda bazaga so'rovlar soni
oshmasligi kerak. Agar biror sahifa har qator uchun alohida so'rov yuborsa, bu test yiqiladi.
"""
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from chat.models import Meeting
from core.models import Notification
from main.models import Material, Order, OrderGoal, OrderMaterial
from main.testing import make_department, make_employee, make_goal, make_org, make_region

SMALL, LARGE, TOLERANCE = 1, 12, 2


class QueryBudgetMixin:
    def queries(self, url, params=None):
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url, params or {})
        self.assertEqual(response.status_code, 200, url)
        return len(ctx)

    def assert_flat(self, url, make_row, params=None):
        for _ in range(SMALL):
            make_row()
        base = self.queries(url, params)
        for _ in range(LARGE - SMALL):
            make_row()
        grown = self.queries(url, params)
        self.assertLessEqual(
            grown, base + TOLERANCE,
            f"{url}: {SMALL} qatorda {base} ta, {LARGE} qatorda {grown} ta so'rov (N+1 bo'lishi mumkin)",
        )


class OrderPagesQueryBudget(QueryBudgetMixin, TestCase):
    def setUp(self):
        self.client_org = make_org("client")
        self.worker_org = make_org("worker")
        self.region = make_region()
        self.dep = make_department(self.worker_org, self.region)
        self.goal = make_goal(self.worker_org)
        self.material = Material.objects.create(name="Kabel", number=1000)

    def _order(self, sender, receiver=None, status="viewed"):
        order = Order.objects.create(sender=sender, goal=self.goal, receiver=receiver, status=status)
        OrderMaterial.objects.create(order=order, material=self.material, number=1)
        return order

    def test_sender_page(self):
        user, sender = make_employee(self.client_org, self.region)
        self.client.force_login(user)

        def row():
            _, receiver = make_employee(self.worker_org, self.region, self.dep)
            self._order(sender, receiver, "process")

        self.assert_flat(reverse("order_sender"), row)

    def test_receiver_new_page(self):
        user, receiver = make_employee(self.worker_org, self.region, self.dep, perms=["main.change_order"])
        OrderGoal.objects.create(employee=receiver).goal.add(self.goal)
        self.client.force_login(user)

        def row():
            _, sender = make_employee(self.client_org, self.region)
            self._order(sender, None, "viewed")

        self.assert_flat(reverse("order_receiver"), row)

    def test_receiver_active_page(self):
        user, receiver = make_employee(self.worker_org, self.region, self.dep, perms=["main.change_order"])
        OrderGoal.objects.create(employee=receiver).goal.add(self.goal)
        self.client.force_login(user)

        def row():
            _, sender = make_employee(self.client_org, self.region)
            self._order(sender, receiver, "process")

        self.assert_flat(reverse("order_receiver_activ"), row)


class BarnOrderPagesQueryBudget(QueryBudgetMixin, TestCase):
    """Omborxona (client) arizalari sahifalari."""

    def setUp(self):
        self.org = make_org("client")
        self.region = make_region()
        self.goal = make_goal(self.org)
        self.material = Material.objects.create(name="Qog'oz", number=1000)

    def _order(self, sender, receiver=None, status="viewed"):
        order = Order.objects.create(sender=sender, goal=self.goal, receiver=receiver, status=status)
        OrderMaterial.objects.create(order=order, material=self.material, number=2, given=2)
        return order

    def test_sender_barn_page(self):
        user, sender = make_employee(self.org, self.region)
        self.client.force_login(user)

        def row():
            _, receiver = make_employee(self.org, self.region)
            self._order(sender, receiver, "approved")

        self.assert_flat(reverse("order_sender_barn"), row)

    def test_receiver_barn_new_page(self):
        user, receiver = make_employee(self.org, self.region, perms=["main.change_order"])
        OrderGoal.objects.create(employee=receiver).goal.add(self.goal)
        self.client.force_login(user)

        def row():
            _, sender = make_employee(self.org, self.region)
            self._order(sender, None, "viewed")

        self.assert_flat(reverse("order_receiver_barn"), row)

    def test_receiver_active_barn_page(self):
        user, receiver = make_employee(self.org, self.region, perms=["main.change_order"])
        self.client.force_login(user)

        def row():
            _, sender = make_employee(self.org, self.region)
            self._order(sender, receiver, "process")

        self.assert_flat(reverse("order_receiver_activ_barn"), row)

    def test_agrement_page(self):
        user, _ = make_employee(self.org, self.region, perms=["main.confirm_order"])
        self.client.force_login(user)

        def row():
            _, sender = make_employee(self.org, self.region)
            _, receiver = make_employee(self.org, self.region)
            self._order(sender, receiver, "finished")

        self.assert_flat(reverse("order_agrement"), row)


class EmployeePageQueryBudget(QueryBudgetMixin, TestCase):
    def test_employee_table(self):
        org = make_org("worker")
        region = make_region()
        dep = make_department(org, region)
        user, _ = make_employee(
            org, region, dep,
            perms=["main.view_employee", "main.change_employee", "main.delete_employee", "main.permission_employee"],
        )
        self.client.force_login(user)
        self.assert_flat(
            reverse("employee"), lambda: make_employee(org, region, dep), {"organization": org.id},
        )


class ChatAndMeetingQueryBudget(QueryBudgetMixin, TestCase):
    def test_notifications_page(self):
        user, emp = make_employee(make_org("client"), make_region())
        self.client.force_login(user)
        counter = iter(range(10000))
        self.assert_flat(
            reverse("notifications_page"),
            lambda: Notification.objects.create(employee=emp, title=f"X{next(counter)}", tag=f"order-new-{next(counter)}"),
        )

    def test_meetings_page(self):
        from datetime import timedelta
        from django.utils import timezone

        org = make_org("client")
        user, _ = make_employee(org, perms=["chat.add_meeting", "chat.view_meeting"])
        self.client.force_login(user)
        counter = iter(range(10000))

        def row():
            _, organizer = make_employee(org)
            n = next(counter)
            Meeting.objects.create(
                organizer=organizer, title=f"M{n}", start_at=timezone.now() + timedelta(days=1, hours=n),
                zoom_id=str(n), join_url="https://zoom.us/j/1", start_url="https://zoom.us/s/1",
            )

        self.assert_flat(reverse("meetings_page"), row)
