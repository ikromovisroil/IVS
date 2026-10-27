"""Nishon (order_notifications) va mark-seen bitta qoidalar ro'yxatidan ishlaydi: mark-seen dan keyin qolgan belgi bo'lmaydi."""
from django.test import RequestFactory, TestCase
from rest_framework.test import APIClient

from main.context_processors import ORDER_SEEN_RULES, order_notifications
from main.models import Order
from main.testing import make_employee, make_goal, make_org, make_region


class MarkSeenRulesTests(TestCase):
    def setUp(self):
        self.region = make_region()
        self.orgs = {"worker": make_org("worker"), "client": make_org("client")}
        self.goals = {t: make_goal(o) for t, o in self.orgs.items()}
        self.user, self.me = make_employee(self.orgs["worker"], self.region)
        _, self.other = make_employee(self.orgs["client"], self.region)

    def _count(self):
        request = RequestFactory().get("/")
        request.user = self.user
        return order_notifications(request)["order_notification_count"]

    def test_every_rule_is_cleared_by_mark_seen(self):
        for who, org_type, statuses, seen in ORDER_SEEN_RULES:
            for status in statuses:
                kwargs = {"sender": self.other, "goal": self.goals[org_type], "status": status}
                kwargs[who] = self.me
                order = Order.objects.create(**{**kwargs, seen: False})
                self.assertEqual(self._count(), 1, (who, org_type, status))
                api = APIClient()
                api.force_authenticate(self.user)
                self.assertEqual(api.post("/api/v1/orders/mark-seen/").status_code, 200)
                self.assertEqual(self._count(), 0, (who, org_type, status))
                order.delete()
