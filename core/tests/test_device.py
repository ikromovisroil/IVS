"""Qurilma turi: sarlavhadan aniqlash, ariza/hujjat/login yozuvlarida saqlash, push platformasi, 5xx logi."""
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.test import APIClient

from core.device import current_device, detect_device, reset_current_device, set_current_device
from core.middlewares.device import DeviceMiddleware
from core.models import AuditLog, MobileDevice
from main.models import Deed, Order
from main.testing import make_employee, make_org, make_region


class DetectTests(TestCase):
    def _detect(self, cookies=None, **headers):
        request = RequestFactory().get("/api/v1/me/", **headers)
        request.COOKIES.update(cookies or {})
        return detect_device(request)

    def test_header_wins_and_is_case_insensitive(self):
        self.assertEqual(self._detect(HTTP_X_DEVICE_TYPE="iOS", HTTP_X_APP_VERSION="1.0.3"), ("ios", "1.0.3"))
        self.assertEqual(self._detect(HTTP_X_DEVICE_TYPE="android")[0], "android")

    def test_browser_is_web(self):
        self.assertEqual(self._detect(cookies={"csrftoken": "x"})[0], "web")
        self.assertEqual(self._detect(cookies={"sessionid": "x"})[0], "web")

    def test_unknown_stays_empty(self):
        self.assertEqual(self._detect()[0], "")                                    # eski ilova / tashqi xizmat
        self.assertEqual(self._detect(cookies={"sessionid": "x"}, HTTP_AUTHORIZATION="Bearer t")[0], "")
        self.assertEqual(self._detect(HTTP_X_DEVICE_TYPE="windows")[0], "")        # noma'lum qiymat

    def test_server_error_is_logged_with_device(self):
        middleware = DeviceMiddleware(lambda request: HttpResponse(status=500))
        request = RequestFactory().get("/api/v1/deeds/", HTTP_X_DEVICE_TYPE="ios", HTTP_X_APP_VERSION="2.0")
        with self.assertLogs("core.middlewares.device", "ERROR") as logs:
            middleware(request)
        self.assertIn("qurilma=ios versiya=2.0", logs.output[0])
        self.assertEqual(current_device(), ("", ""))                               # so'rovdan keyin tozalanadi


class SaveTests(TestCase):
    def setUp(self):
        org, region = make_org("worker"), make_region()
        self.user, self.emp = make_employee(org, region, perms=["main.add_order", "main.view_order"])

    def test_order_and_deed_take_current_device_only_on_create(self):
        token = set_current_device(("ios", "1.0"))
        try:
            order = Order.objects.create(sender=self.emp)
            deed = Deed.objects.create(sender=self.emp)
        finally:
            reset_current_device(token)
        token = set_current_device(("android", "1.0"))
        try:
            order.save()
            deed.save()
        finally:
            reset_current_device(token)
        order.refresh_from_db()
        deed.refresh_from_db()
        self.assertEqual((order.device_type, deed.device_type), ("ios", "ios"))

    def test_outside_request_is_empty(self):
        self.assertEqual(Order.objects.create(sender=self.emp).device_type, "")


class RequestTests(TestCase):
    def setUp(self):
        org, region = make_org("worker"), make_region()
        self.user, self.emp = make_employee(org, region)
        User.objects.filter(pk=self.user.pk).update(is_active=True)
        self.user.set_password("test-only-pass-123")
        self.user.save()

    def test_password_jwt_login_is_audited_with_device(self):
        r = APIClient().post("/api/v1/token/", {"username": self.user.username, "password": "test-only-pass-123"},
                             format="json", HTTP_X_DEVICE_TYPE="android", HTTP_X_APP_VERSION="1.0.5")
        self.assertEqual(r.status_code, 200, r.content)
        log = AuditLog.objects.get(action="login")
        self.assertEqual((log.device_type, log.app_version, log.employee_id), ("android", "1.0.5", self.emp.id))

    def test_push_device_platform_from_header(self):
        client = APIClient()
        client.force_authenticate(self.user)
        for header, expected in (("ios", "ios"), (None, "android"), ("web", "android")):
            extra = {"HTTP_X_DEVICE_TYPE": header} if header else {}
            r = client.post("/api/v1/devices/", {"token": f"token-{header}-" + "x" * 30}, format="json", **extra)
            self.assertEqual(r.status_code, 201, r.content)
            self.assertEqual(MobileDevice.objects.get(pk=r.json()["id"]).platform, expected, header)

    @override_settings(ANDROID_MIN_VERSION="3.0.0")
    def test_forced_update_does_not_apply_to_ios(self):
        client = APIClient()
        client.force_authenticate(self.user)
        old = {"HTTP_X_APP_VERSION": "1.0.0"}
        self.assertEqual(client.get("/api/v1/me/", **old).status_code, 426)
        self.assertEqual(client.get("/api/v1/me/", HTTP_X_DEVICE_TYPE="android", **old).status_code, 426)
        self.assertEqual(client.get("/api/v1/me/", HTTP_X_DEVICE_TYPE="ios", **old).status_code, 200)
