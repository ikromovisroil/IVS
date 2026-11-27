"""Mobil push (FCM): Android va iOS xabar tarkibi, sozlanmagan holat. Tashqi so'rov yuborilmaydi."""
import os
import tempfile
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from core.models import MobileDevice, Notification
from main.fcm import fcm_enabled, send_to_employee
from main.testing import make_employee, make_org, make_region


class EnabledTests(SimpleTestCase):
    def _enabled(self, path):
        with override_settings(FIREBASE_CREDENTIALS_FILE=path):
            return fcm_enabled()

    def test_missing_empty_or_directory_means_disabled(self):
        with tempfile.TemporaryDirectory() as folder:
            empty = os.path.join(folder, "empty.json")
            open(empty, "w").close()
            for path in ("", os.path.join(folder, "none.json"), folder, empty, os.devnull):
                self.assertFalse(self._enabled(path), path)

    def test_real_file_means_enabled(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "firebase.json")
            with open(path, "w") as f:
                f.write("{}")
            self.assertTrue(self._enabled(path))


@mock.patch("main.fcm._access_token", return_value=("token", "project"))
@mock.patch("main.fcm.fcm_enabled", return_value=True)
class MessageTests(TestCase):
    def setUp(self):
        _, self.emp = make_employee(make_org("worker"), make_region())
        for platform in ("android", "ios"):
            MobileDevice.objects.create(employee=self.emp, token=f"{platform}-" + "x" * 30, platform=platform)
        for i in range(2):
            Notification.objects.create(employee=self.emp, title="T", tag=f"order-new-{i}")

    def test_each_platform_gets_its_own_block(self, *_):
        with mock.patch("main.fcm.requests.post", return_value=mock.Mock(status_code=200)) as post:
            result = send_to_employee(self.emp.id, "Sarlavha", "Matn", "/", tag="chat-" + "1" * 80)
        self.assertEqual(result["sent"], 2)
        messages = {c.kwargs["json"]["message"]["token"].split("-")[0]: c.kwargs["json"]["message"] for c in post.call_args_list}

        android = messages["android"]
        self.assertNotIn("apns", android)
        self.assertEqual(android["android"]["notification"]["channel_id"], "ivs_default")

        ios = messages["ios"]
        self.assertNotIn("android", ios)
        self.assertEqual(ios["apns"]["payload"]["aps"], {"sound": "default", "badge": 2})
        self.assertEqual(ios["apns"]["headers"]["apns-priority"], "10")
        self.assertEqual(len(ios["apns"]["headers"]["apns-collapse-id"]), 64)
        self.assertEqual(ios["notification"], {"title": "Sarlavha", "body": "Matn"})
