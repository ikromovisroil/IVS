"""api/spa/comms.py — Zoom sozlamasi (sahifa ogohlantirishi va "Yaratish" tugmasi uchun)."""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from main.testing import make_employee, make_org

URL = "/api/v1/spa/comms/meetings/config/"


class CommsSpaTests(TestCase):
    def setUp(self):
        self.org = make_org("worker")

    def _api(self, perms=()):
        user, _ = make_employee(org=self.org, perms=perms)
        api = APIClient()
        api.force_authenticate(user)
        return api

    def test_requires_meeting_permission(self):
        self.assertEqual(self._api().get(URL).status_code, 403)
        self.assertIn(APIClient().get(URL).status_code, (401, 403))

    @override_settings(ZOOM_ACCOUNT_ID="", ZOOM_CLIENT_ID="", ZOOM_CLIENT_SECRET="")
    def test_zoom_disabled(self):
        r = self._api(["chat.view_meeting"]).get(URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, {"zoom_enabled": False, "hosts": [{"id": 1, "name": "Zoom 1"}]})

    @override_settings(ZOOM_ACCOUNT_ID="a", ZOOM_CLIENT_ID="b", ZOOM_CLIENT_SECRET="c")
    def test_zoom_enabled(self):
        self.assertEqual(self._api(["chat.add_meeting"]).get(URL).data, {"zoom_enabled": True, "hosts": [{"id": 1, "name": "Zoom 1"}]})
