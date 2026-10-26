"""Brauzer push (Web Push): obuna API, eski → yangi manzil moslashtirish, yuborish vazifasi, service worker."""
import json
from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.models import PushSubscription
from core.spa_urls import spa_url
from main.testing import make_employee, make_org, make_region

URL = "/api/v1/push/"
ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc123"
KEYS = {"p256dh": "BP-key-value", "auth": "auth-secret"}


class SpaUrlTests(TestCase):
    def test_old_paths_map_to_new_interface(self):
        cases = {
            "/order/receiver/": "/app/orders/execute",
            "/order/sender/": "/app/orders",
            "/contact/user/": "/app/messages",
            "/contact/agrement/": "/app/messages/agree",
            "/chat/": "/app/chat",
            "/chat/meetings/": "/app/meetings",
            "/order/sender/?x=1#y": "/app/orders",
        }
        for old, new in cases.items():
            self.assertEqual(spa_url(old), new, old)

    def test_unknown_empty_or_foreign_goes_home(self):
        for url in ("/", "", None, "/nomalum/sahifa/", "//evil.example/x"):
            self.assertEqual(spa_url(url), "/app/", url)

    def test_new_paths_pass_through(self):
        self.assertEqual(spa_url("/app/orders/5"), "/app/orders/5")


class PushApiTests(TestCase):
    def setUp(self):
        org = make_org("client")
        self.user, self.emp = make_employee(org, make_region())
        self.other_user, self.other = make_employee(org, make_region())
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def _subscribe(self, api=None, **extra):
        data = {"endpoint": ENDPOINT, "keys": KEYS}
        data.update(extra)
        return (api or self.api).post(URL + "subscribe/", data, format="json")

    def test_requires_login(self):
        anon = APIClient()
        self.assertIn(anon.get(URL + "public-key/").status_code, (401, 403))
        self.assertIn(anon.post(URL + "subscribe/", {}, format="json").status_code, (401, 403))

    @override_settings(VAPID_PUBLIC_KEY="PUBLIC-KEY")
    def test_public_key(self):
        self.assertEqual(self.api.get(URL + "public-key/").json(), {"public_key": "PUBLIC-KEY"})

    def test_subscribe_creates_and_updates_without_duplicates(self):
        first = self._subscribe()
        self.assertEqual((first.status_code, first.json()), (201, {"subscribed": True}))
        again = self._subscribe(keys={"p256dh": "yangi", "auth": "yangi2"})
        self.assertEqual(again.status_code, 200)
        sub = PushSubscription.objects.get()
        self.assertEqual((sub.employee_id, sub.p256dh, sub.auth), (self.emp.id, "yangi", "yangi2"))

    def test_same_device_rebinds_to_new_employee(self):
        self._subscribe()
        other = APIClient()
        other.force_authenticate(self.other_user)
        self._subscribe(api=other)
        self.assertEqual(PushSubscription.objects.get().employee_id, self.other.id)

    def test_validation(self):
        self.assertEqual(self._subscribe(endpoint="http://insecure.example/x").status_code, 400)
        self.assertEqual(self._subscribe(endpoint="").status_code, 400)
        self.assertEqual(self._subscribe(keys={"p256dh": "x"}).status_code, 400)
        self.assertEqual(self._subscribe(keys="bad").status_code, 400)
        self.assertFalse(PushSubscription.objects.exists())

    def test_status_and_unsubscribe_only_touch_own(self):
        self._subscribe()
        self.assertEqual(self.api.get(URL + "status/", {"endpoint": ENDPOINT}).json(), {"subscribed": True})
        other = APIClient()
        other.force_authenticate(self.other_user)
        self.assertEqual(other.get(URL + "status/", {"endpoint": ENDPOINT}).json(), {"subscribed": False})
        other.post(URL + "unsubscribe/", {"endpoint": ENDPOINT}, format="json")      # boshqa xodim o'chira olmaydi
        self.assertTrue(PushSubscription.objects.exists())
        self.assertEqual(self.api.post(URL + "unsubscribe/", {"endpoint": ENDPOINT}, format="json").json(), {"subscribed": False})
        self.assertFalse(PushSubscription.objects.exists())


class PushDeliveryTests(TestCase):
    def setUp(self):
        _, self.emp = make_employee(make_org("client"), make_region())
        PushSubscription.objects.create(employee=self.emp, endpoint=ENDPOINT, p256dh="k", auth="a")

    def test_payload_uses_new_interface_path_and_tag(self):
        from main.tasks import send_push_notification_task

        with mock.patch("pywebpush.webpush") as webpush:
            webpush.return_value = mock.Mock(status_code=201)
            send_push_notification_task.apply(args=(self.emp.id, "Yangi ariza", "Matn", "/order/receiver/", "order-new-7"))
        payload = json.loads(webpush.call_args.kwargs["data"])
        self.assertEqual(payload["url"], "/app/orders/execute")
        self.assertEqual((payload["title"], payload["body"], payload["tag"]), ("Yangi ariza", "Matn", "order-new-7"))
        self.assertEqual(webpush.call_args.kwargs["subscription_info"]["endpoint"], ENDPOINT)

    def test_dead_subscription_is_removed(self):
        from pywebpush import WebPushException

        from main.tasks import send_push_notification_task

        gone = mock.Mock(status_code=410, text="gone")
        with mock.patch("pywebpush.webpush", side_effect=WebPushException("gone", response=gone)):
            send_push_notification_task.apply(args=(self.emp.id, "T", "B", "/", None))
        self.assertFalse(PushSubscription.objects.exists())

    def test_deactivated_employee_loses_subscriptions(self):
        from main.employee_lifecycle import deactivate_employee

        deactivate_employee(self.emp)
        self.assertFalse(PushSubscription.objects.exists())


class ServiceWorkerTests(TestCase):
    def test_served_under_app_scope(self):
        response = self.client.get("/app/sw.js")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Service-Worker-Allowed"], "/app/")
        self.assertIn("javascript", response["Content-Type"])
        body = response.content.decode()
        self.assertIn("addEventListener('push'", body)
        self.assertIn("notificationclick", body)
