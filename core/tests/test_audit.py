"""Audit jurnali: Order/Deed signal yozuvlarida ham IP, usul va yo'l saqlanadi.

    venv/Scripts/python.exe manage.py test core.tests.test_audit
"""
from django.test import RequestFactory, TestCase

from core.middlewares.audit import AuditMiddleware
from core.models import AuditLog
from core.request_context import get_current_request_info
from main.models import Goal, Order, Organization, Region
from main.testing import make_employee


class SignalAuditRequestInfoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(name="Toshkent shahri")
        org = Organization.objects.create(name="ATM", type="worker")
        _, cls.worker = make_employee(org=org, region=region, last="Ishchi")
        cls.goal = Goal.objects.create(name="Nosozlik", organization=org)

    def _run(self, **meta):
        """Middleware orqali bitta POST so'rov: ichida ariza yaratiladi."""
        request = RequestFactory().post("/api/v1/orders/", **meta)
        request.user = self.worker.user

        def view(req):
            Order.objects.create(goal=self.goal, sender=self.worker, receiver=self.worker, status="viewed")
            return object()

        AuditMiddleware(view)(request)

    def test_order_create_logs_ip_method_path(self):
        self._run(HTTP_X_FORWARDED_FOR="213.230.87.43, 10.0.0.1", HTTP_USER_AGENT="Android")
        log = AuditLog.objects.get(model="Order")
        self.assertEqual((log.ip, log.method, log.path), ("213.230.87.43", "POST", "/api/v1/orders/"))
        self.assertEqual(log.user_agent, "Android")
        self.assertFalse(AuditLog.objects.filter(model="HTTP").exists())  # dublikat yozuv yo'q

    def test_invalid_forwarded_ip_is_dropped(self):
        self._run(HTTP_X_FORWARDED_FOR="unknown")
        log = AuditLog.objects.get(model="Order")
        self.assertIsNone(log.ip)
        self.assertEqual(log.method, "POST")

    def test_no_request_context_outside_request(self):
        """Management command / shell: so'rov yo'q — maydonlar bo'sh, xato yo'q."""
        Order.objects.create(goal=self.goal, sender=self.worker, receiver=self.worker, status="viewed")
        log = AuditLog.objects.get(model="Order")
        self.assertEqual((log.ip, log.method, log.path), (None, "", ""))
        self.assertEqual(get_current_request_info(), {})
