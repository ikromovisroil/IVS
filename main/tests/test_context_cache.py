"""Har sahifadagi hisoblagichlar keshi: TTL, xodim bo'yicha ajratish, tozalash."""
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from main.context_processors import (
    contact_badge_counts, invalidate_counts, order_notifications, order_receiver_count,
)
from main.models import Order, OrderGoal
from main.testing import make_employee, make_goal, make_org, make_region


class ContextCacheTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.client_org = make_org("client")
        self.worker_org = make_org("worker")
        self.region = make_region()
        self.goal = make_goal(self.worker_org)
        self.worker_user, self.worker = make_employee(self.worker_org, self.region)
        OrderGoal.objects.create(employee=self.worker).goal.add(self.goal)
        _, self.sender = make_employee(self.client_org, self.region)

    def _new_order(self):
        return Order.objects.create(sender=self.sender, goal=self.goal, status="viewed")

    def _count(self, user=None):
        request = RequestFactory().get("/")
        request.user = user or self.worker_user
        return order_receiver_count(request)["order_receiver_badge_count"]

    def test_disabled_by_default_in_tests_counts_are_always_fresh(self):
        self._new_order()
        self.assertEqual(self._count(), 1)
        self._new_order()
        self.assertEqual(self._count(), 2)

    @override_settings(CONTEXT_CACHE_SECONDS=30)
    def test_cached_until_invalidated(self):
        self._new_order()
        self.assertEqual(self._count(), 1)
        self._new_order()
        self.assertEqual(self._count(), 1)            # keshdan
        invalidate_counts(self.worker.id)
        self.assertEqual(self._count(), 2)            # yangilandi

    @override_settings(CONTEXT_CACHE_SECONDS=30)
    def test_cache_is_per_employee(self):
        other_user, other = make_employee(self.worker_org, self.region)      # ariza turi biriktirilmagan
        self._new_order()
        self.assertEqual(self._count(), 1)
        self.assertEqual(self._count(other_user), 0)
        invalidate_counts(other.id)
        self.assertEqual(self._count(), 1)            # boshqaning tozalashi ta'sir qilmaydi

    @override_settings(CONTEXT_CACHE_SECONDS=30)
    def test_mark_seen_clears_cache(self):
        self._new_order()
        self.assertEqual(self._count(), 1)
        self._new_order()
        self.client.force_login(self.worker_user)
        self.client.get(reverse("order_mark_seen"))
        self.assertEqual(self._count(), 2)

    @override_settings(CONTEXT_CACHE_SECONDS=30)
    def test_anonymous_and_missing_employee_are_safe(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        self.assertEqual(order_notifications(request), {"order_notification_count": 0})
        self.assertEqual(order_receiver_count(request), {"order_receiver_badge_count": 0})
        self.assertEqual(contact_badge_counts(request), {"contact_badge_count": 0, "contact_agrement_badge_count": 0})

    @override_settings(CONTEXT_CACHE_SECONDS=30)
    def test_contact_badges_are_cached_too(self):
        request = RequestFactory().get("/")
        request.user = self.worker_user
        first = contact_badge_counts(request)
        self.assertEqual(first, {"contact_badge_count": 0, "contact_agrement_badge_count": 0})
        self.assertIsNotNone(cache.get(f"ctx:contact_badge_counts:{self.worker.id}"))
        invalidate_counts(self.worker.id)
        self.assertIsNone(cache.get(f"ctx:contact_badge_counts:{self.worker.id}"))
