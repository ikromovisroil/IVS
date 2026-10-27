"""Admin ro'yxatlari qatorlar soniga bog'liq bo'lmagan (N+1 yo'q) so'rovlar bilan ochiladi."""
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from main.models import Deed, Order
from main.testing import make_employee, make_goal, make_org, make_region


class AdminChangelistQueriesTests(TestCase):
    def setUp(self):
        self.region = make_region()
        self.worker = make_org("worker")
        self.client_org = make_org("client")
        self.goal = make_goal(self.worker)
        admin = get_user_model().objects.create_superuser("adm", "a@a.uz", "x")
        self.client.force_login(admin)

    def _queries(self, url):
        with CaptureQueriesContext(connection) as ctx:
            self.assertEqual(self.client.get(url).status_code, 200)
        return len(ctx)

    def _grow(self, make, url):
        make(2)
        few = self._queries(url)
        make(10)
        many = self._queries(url)
        self.assertLessEqual(many, few + 2, (url, few, many))

    def test_employee_list_has_no_n_plus_one(self):
        def make(n):
            for _ in range(n):
                make_employee(self.worker, self.region)
        self._grow(make, "/ivc_service_admin_panel/main/employee/")

    def test_order_and_deed_lists_have_no_n_plus_one(self):
        def make(n):
            for _ in range(n):
                _, s = make_employee(self.client_org, self.region)
                _, r = make_employee(self.worker, self.region)
                order = Order.objects.create(sender=s, receiver=r, goal=self.goal, status="viewed")
                deed = Deed.objects.create(sender=s, receiver=r, user=s, organization=self.client_org)
                deed.orders.add(order)
        self._grow(make, "/ivc_service_admin_panel/main/order/")
        self._grow(make, "/ivc_service_admin_panel/main/deed/")
