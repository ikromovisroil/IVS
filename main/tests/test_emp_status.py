"""Statistika -> Xodimlar (emp_status): hudud ro'yxati va natijalar foydalanuvchi ruxsatiga qarab."""
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from main.models import Order
from main.testing import make_employee, make_goal, make_org, make_region


class EmpStatusRegionScopeTests(TestCase):
    def setUp(self):
        self.client_org = make_org("client")
        self.worker = make_org("worker")
        self.region_a = make_region("Hudud A")
        self.region_b = make_region("Hudud B")
        self.goal = make_goal(self.worker)
        _, self.sender = make_employee(self.client_org, self.region_a, first="Yuboruvchi", last="Mijoz")
        _, self.in_a = make_employee(self.worker, self.region_a, first="Birinchi", last="HududA")
        _, self.in_b = make_employee(self.worker, self.region_b, first="Ikkinchi", last="HududB")
        self._order(self.in_a)
        self._order(self.in_b)
        self._order(self.in_b)

    def _order(self, receiver):
        return Order.objects.create(sender=self.sender, receiver=receiver, goal=self.goal, status="process")

    def _login(self, *, all_regions, region):
        perms = ["main.status_employee"] + (["main.all_region"] if all_regions else [])
        user, _ = make_employee(self.worker, region, perms=perms)
        self.client.force_login(user)

    def _get(self, **params):
        return self.client.get(reverse("emp_status"), params)

    @staticmethod
    def _totals(response):
        return {row["receiver_id"]: row["total_count"] for row in response.context["employee"]}

    def test_restricted_user_sees_only_own_region_in_list(self):
        self._login(all_regions=False, region=self.region_a)
        response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r.id for r in response.context["region"]], [self.region_a.id])

    def test_all_region_user_sees_every_region_in_list(self):
        self._login(all_regions=True, region=self.region_a)
        response = self._get()
        self.assertEqual({r.id for r in response.context["region"]}, {self.region_a.id, self.region_b.id})

    def test_restricted_user_requesting_other_region_is_forbidden(self):
        self._login(all_regions=False, region=self.region_a)
        self.assertEqual(self._get(region=self.region_b.id).status_code, 403)

    def test_without_region_choice_nothing_is_shown(self):
        for all_regions in (False, True):
            self._login(all_regions=all_regions, region=self.region_a)
            response = self._get()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self._totals(response), {})
            self.assertEqual(list(response.context["goal"]), [])
            self.assertContains(response, "topilmadi", count=2)
            self.assertContains(response, "required")            # hudud tanlash majburiy

    def test_dates_only_search_without_region_shows_nothing(self):
        self._login(all_regions=True, region=self.region_a)
        response = self._get(date1="2020-01-01", date2="2099-01-01")
        self.assertEqual(self._totals(response), {})

    def test_restricted_user_own_region_explicit(self):
        self._login(all_regions=False, region=self.region_a)
        response = self._get(region=self.region_a.id)
        self.assertEqual(self._totals(response), {self.in_a.id: 1})
        self.assertEqual(response.context["selected_region"], str(self.region_a.id))

    def test_restricted_user_goal_totals_follow_region(self):
        self._login(all_regions=False, region=self.region_b)
        response = self._get(region=self.region_b.id)
        self.assertEqual(self._totals(response), {self.in_b.id: 2})
        self.assertEqual({g.id: g.total for g in response.context["goal"]}, {self.goal.id: 2})

    def test_user_without_region_has_empty_list_and_sees_nothing(self):
        self._login(all_regions=False, region=None)
        response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._totals(response), {})
        self.assertEqual(list(response.context["region"]), [])
        self.assertEqual(self._get(region=self.region_a.id).status_code, 403)

    def test_all_region_user_can_pick_any_region(self):
        self._login(all_regions=True, region=self.region_a)
        response = self._get(region=self.region_b.id)
        self.assertEqual(self._totals(response), {self.in_b.id: 2})

    def test_default_dates_are_current_month(self):
        self._login(all_regions=False, region=self.region_a)
        response = self._get()
        today = timezone.localdate()
        self.assertEqual(response.context["date1"], today.replace(day=1).isoformat())
