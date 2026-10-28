"""Zoom uchrashuvlari: ruxsatlar, vaqt to'qnashuvi, bekor qilish/tugatish, sahifalash, eslatma."""
import json
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from chat import meetings
from chat.models import Meeting
from main.testing import make_employee, make_org, make_region

VIEW, ADD, DELETE = "chat.view_meeting", "chat.add_meeting", "chat.delete_meeting"


class FakeResponse:
    def __init__(self, status=200, data=None):
        self.status_code = status
        self._data = data or {}
        self.text = json.dumps(self._data)

    def json(self):
        return self._data


class FakeZoom:
    """Zoom API ning soxta varianti: yaratilgan/o'chirilgan/tugatilgan chaqiruvlarni sanaydi."""

    def __init__(self):
        self.created = 0
        self.deleted = []
        self.ended = []
        self.fail_create = False
        self.invitation = "TAKLIF MATNI"      # None bo'lsa ruxsat yo'q (400)

    def post(self, url, **kwargs):             # OAuth token
        return FakeResponse(200, {"access_token": "T", "expires_in": 3600})

    def request(self, method, url, **kwargs):
        if method == "POST":
            if self.fail_create:
                return FakeResponse(500, {"message": "boom"})
            self.created += 1
            n = 700000 + self.created
            return FakeResponse(201, {
                "id": n, "join_url": f"https://zoom.us/j/{n}", "start_url": f"https://zoom.us/s/{n}?zak=SECRET{n}",
                "password": "p4ss",
            })
        if method == "GET" and url.endswith("/invitation"):
            if self.invitation is None:
                return FakeResponse(400, {"message": "no scope"})
            return FakeResponse(200, {"invitation": self.invitation})
        if method == "DELETE":
            self.deleted.append(url)
        if method == "PUT":
            self.ended.append(url)
        return FakeResponse(204)


@override_settings(ZOOM_ACCOUNT_ID="a", ZOOM_CLIENT_ID="c", ZOOM_CLIENT_SECRET="s", ZOOM_HOST="me",
                   MEETING_BUFFER_MINUTES=0)
class ZoomTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.zoom = FakeZoom()
        for target, side_effect in (("chat.zoom.requests.post", self.zoom.post),
                                    ("chat.zoom.requests.request", self.zoom.request)):
            patcher = mock.patch(target, side_effect=side_effect)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.org = make_org("client")
        self.base = (timezone.now() + timedelta(days=30)).replace(hour=10, minute=0, second=0, microsecond=0)

    def api(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def at(self, hours=0, minutes=0):
        return (self.base + timedelta(hours=hours, minutes=minutes)).isoformat()

    def create(self, user, hours=0, title="Majlis", duration=60, minutes=0):
        return self.api(user).post("/api/v1/meetings/", {
            "title": title, "start_at": self.at(hours, minutes), "duration_minutes": duration,
        }, format="json")


class MeetingPermissionTests(ZoomTestCase):
    def setUp(self):
        super().setUp()
        self.none_user, _ = make_employee(self.org)
        self.add_user, self.add_emp = make_employee(self.org, perms=[ADD])
        self.adddel_user, self.adddel_emp = make_employee(self.org, perms=[ADD, DELETE])
        self.view_user, self.view_emp = make_employee(self.org, perms=[VIEW])

    def test_no_permission_blocks_api(self):
        self.assertEqual(self.api(self.none_user).get("/api/v1/meetings/").status_code, 403)
        self.assertEqual(self.create(self.none_user).status_code, 403)

    def test_view_only_cannot_create(self):
        self.assertEqual(self.create(self.view_user).status_code, 403)
        self.assertEqual(self.zoom.created, 0)

    def test_creator_sees_own_with_start_url(self):
        response = self.create(self.add_user)
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertIn("zak=SECRET", body["start_url"])
        self.assertTrue(body["is_organizer"])
        self.assertNotIn("participants", body)

    def test_creator_without_view_sees_only_own(self):
        self.create(self.add_user, hours=0, title="Meniki")
        self.create(self.adddel_user, hours=3, title="Boshqaniki")
        titles = {m["title"] for m in self.api(self.add_user).get("/api/v1/meetings/").json()["results"]}
        self.assertEqual(titles, {"Meniki"})

    def test_viewer_sees_all_but_without_start_url_or_actions(self):
        mine = self.create(self.add_user, title="Birov").json()
        results = self.api(self.view_user).get("/api/v1/meetings/").json()["results"]
        item = next(m for m in results if m["id"] == mine["id"])
        self.assertNotIn("start_url", item)
        self.assertFalse(item["can_manage"])
        self.assertNotIn("SECRET", str(results))

    def test_viewer_cannot_cancel_or_finish_others(self):
        created = self.create(self.add_user).json()
        viewer = self.api(self.view_user)
        self.assertEqual(viewer.post(f"/api/v1/meetings/{created['id']}/cancel/").status_code, 403)
        self.assertIn(viewer.post(f"/api/v1/meetings/{created['id']}/finish/").status_code, (400, 403))
        self.assertEqual(Meeting.objects.get(pk=created["id"]).status, "scheduled")

    def test_delete_needs_delete_permission(self):
        created = self.create(self.add_user).json()
        self.assertEqual(self.api(self.add_user).post(f"/api/v1/meetings/{created['id']}/cancel/").status_code, 403)
        self.assertEqual(self.zoom.deleted, [])
        other = self.create(self.adddel_user, hours=3).json()
        response = self.api(self.adddel_user).post(f"/api/v1/meetings/{other['id']}/cancel/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "cancelled")
        self.assertEqual(len(self.zoom.deleted), 1)

    def test_other_users_cannot_cancel_even_with_delete_permission(self):
        created = self.create(self.add_user).json()
        response = self.api(self.adddel_user).post(f"/api/v1/meetings/{created['id']}/cancel/")
        self.assertIn(response.status_code, (403, 404))
        self.assertEqual(Meeting.objects.get(pk=created["id"]).status, "scheduled")


class MeetingValidationTests(ZoomTestCase):
    def setUp(self):
        super().setUp()
        self.user, self.emp = make_employee(self.org, perms=[ADD, DELETE])

    def test_overlap_rejected_and_adjacent_allowed(self):
        self.assertEqual(self.create(self.user, hours=0, duration=60).status_code, 201)       # 10:00-11:00
        self.assertEqual(self.create(self.user, hours=0, duration=60).status_code, 400)       # aynan o'sha vaqt
        self.assertEqual(self.create(self.user, hours=0, minutes=30, duration=30).status_code, 400)   # ichiga kiradi
        self.assertEqual(self.create(self.user, hours=-1, minutes=30, duration=60).status_code, 400)  # boshiga kiradi
        self.assertEqual(self.create(self.user, hours=1, duration=60).status_code, 201)       # 11:00 aynan tugagan payt
        self.assertEqual(self.zoom.created, 2)                                                # rad etilganlar Zoom'ga bormagan

    def test_other_user_cannot_take_same_slot(self):
        other_user, _ = make_employee(self.org, perms=[ADD])
        self.create(self.user)
        self.assertEqual(self.create(other_user).status_code, 400)

    def test_cancelled_meeting_frees_the_slot(self):
        first = self.create(self.user).json()
        self.assertEqual(self.create(self.user).status_code, 400)
        self.api(self.user).post(f"/api/v1/meetings/{first['id']}/cancel/")
        self.assertEqual(self.create(self.user).status_code, 201)

    def test_early_finish_frees_the_slot(self):
        past_start = timezone.now() - timedelta(minutes=30)
        running = Meeting.objects.create(
            organizer=self.emp, title="Ketyapti", start_at=past_start, duration_minutes=120,
            zoom_id="55", join_url="https://zoom.us/j/55", start_url="https://zoom.us/s/55",
        )
        soon = (timezone.now() + timedelta(minutes=20)).isoformat()
        body = {"title": "Keyingisi", "start_at": soon, "duration_minutes": 30}
        self.assertEqual(self.api(self.user).post("/api/v1/meetings/", body, format="json").status_code, 400)
        response = self.api(self.user).post(f"/api/v1/meetings/{running.id}/finish/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.zoom.ended), 1)
        self.assertEqual(self.api(self.user).post("/api/v1/meetings/", body, format="json").status_code, 201)

    def test_cannot_finish_not_started_meeting(self):
        created = self.create(self.user).json()
        response = self.api(self.user).post(f"/api/v1/meetings/{created['id']}/finish/")
        self.assertEqual(response.status_code, 400)

    def test_past_time_title_and_duration_validated(self):
        api = self.api(self.user)
        past = (timezone.now() - timedelta(hours=1)).isoformat()
        cases = [
            {"title": "X", "start_at": past, "duration_minutes": 30},
            {"title": " ", "start_at": self.at(), "duration_minutes": 30},
            {"title": "X", "start_at": self.at(), "duration_minutes": 5},
            {"title": "X", "start_at": self.at(), "duration_minutes": 9999},
            {"title": "X", "start_at": "ertaga", "duration_minutes": 30},
        ]
        for body in cases:
            self.assertEqual(api.post("/api/v1/meetings/", body, format="json").status_code, 400, body)
        self.assertEqual(Meeting.objects.count(), 0)

    def test_zoom_failure_creates_nothing(self):
        self.zoom.fail_create = True
        response = self.create(self.user)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Meeting.objects.count(), 0)

    @override_settings(ZOOM_ACCOUNT_ID="")
    def test_zoom_not_configured_gives_clear_error(self):
        response = self.create(self.user)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Zoom", str(response.json()))

    def test_invitation_saved_and_fallback_when_unavailable(self):
        first = self.create(self.user, hours=0).json()
        self.assertEqual(first["invitation"], "TAKLIF MATNI")
        self.zoom.invitation = None
        second = self.create(self.user, hours=3).json()
        self.assertEqual(second["invitation"], "")
        self.assertTrue(second["join_url"])           # taklif matni bo'lmasa havola qoladi


class MeetingReminderTests(ZoomTestCase):
    def test_reminder_goes_only_to_organizer_once(self):
        _, organizer = make_employee(self.org, perms=[ADD])
        soon = Meeting.objects.create(
            organizer=organizer, title="Tez", start_at=timezone.now() + timedelta(minutes=5),
            zoom_id="1", join_url="https://zoom.us/j/1",
        )
        Meeting.objects.create(
            organizer=organizer, title="Uzoq", start_at=timezone.now() + timedelta(minutes=45),
            zoom_id="2", join_url="https://zoom.us/j/2",
        )
        with mock.patch("main.push_views.send_push_notification") as push:
            first = meetings.send_due_reminders()
            second = meetings.send_due_reminders()
        self.assertEqual((first, second), (1, 0))
        self.assertEqual(push.call_count, 1)
        self.assertEqual(push.call_args.args[0].id, organizer.id)
        soon.refresh_from_db()
        self.assertTrue(soon.reminder_sent)


@override_settings(ZOOM_HOSTS="one@x.uz,two@x.uz,three@x.uz")
class MultiHostTests(ZoomTestCase):
    """Bir nechta Zoom (Zoom 1, 2, 3): har host o'z vaqtida alohida uchrashuv o'tkazadi."""

    def setUp(self):
        super().setUp()
        self.user, self.emp = make_employee(self.org, perms=[ADD, DELETE, VIEW])
        self.posted_urls = []
        original = self.zoom.request

        def spy(method, url, **kwargs):
            if method == "POST":
                self.posted_urls.append(url)
            return original(method, url, **kwargs)

        patcher = mock.patch("chat.zoom.requests.request", side_effect=spy)
        patcher.start()
        self.addCleanup(patcher.stop)

    def make(self, host, hours=0, **extra):
        data = {"title": f"Zoom {host}", "start_at": self.at(hours), "duration_minutes": 60, "host": host, **extra}
        return self.api(self.user).post("/api/v1/meetings/", data, format="json")

    def test_same_time_on_different_hosts_is_allowed(self):
        self.assertEqual(self.make(1).status_code, 201)
        self.assertEqual(self.make(2).status_code, 201)
        self.assertEqual(self.make(3).status_code, 201)
        self.assertEqual(sorted(Meeting.objects.values_list("host", flat=True)), [1, 2, 3])
        # har host uchun Zoom'ga o'z email'i bilan so'rov ketdi
        hosts_used = [u.split("/users/")[1].split("/")[0] for u in self.posted_urls]
        self.assertEqual(hosts_used, ["one@x.uz", "two@x.uz", "three@x.uz"])

    def test_same_time_on_same_host_is_rejected(self):
        self.assertEqual(self.make(2).status_code, 201)
        response = self.make(2)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Meeting.objects.filter(host=2).count(), 1)

    def test_host_defaults_to_first_and_validates_range(self):
        response = self.api(self.user).post("/api/v1/meetings/", {
            "title": "Standart", "start_at": self.at(5), "duration_minutes": 60}, format="json")
        self.assertEqual((response.status_code, response.json()["host"]), (201, 1))
        self.assertEqual(self.make(4, hours=8).status_code, 400)       # 4-Zoom yo'q
        self.assertEqual(self.make("x", hours=9).status_code, 400)

    def test_list_filtered_by_host(self):
        self.make(1, hours=0, title="A")
        self.make(2, hours=0, title="B")
        api = self.api(self.user)
        titles = lambda host: [m["title"] for m in api.get("/api/v1/meetings/", {"host": host}).json()["results"]]
        self.assertEqual(titles(1), ["A"])
        self.assertEqual(titles(2), ["B"])
        self.assertEqual(len(api.get("/api/v1/meetings/").json()["results"]), 2)

    def test_spa_config_lists_hosts(self):
        data = self.api(self.user).get("/api/v1/spa/comms/meetings/config/").json()
        self.assertEqual(data["hosts"], [{"id": 1, "name": "Zoom 1"}, {"id": 2, "name": "Zoom 2"}, {"id": 3, "name": "Zoom 3"}])

    @override_settings(ZOOM_HOSTS="")
    def test_single_host_when_not_configured(self):
        data = self.api(self.user).get("/api/v1/spa/comms/meetings/config/").json()
        self.assertEqual(data["hosts"], [{"id": 1, "name": "Zoom 1"}])
