from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

CONFIG = "/api/v1/spa/auth/config/"
LOGIN = "/api/v1/spa/auth/login/"


class AuthConfigTests(TestCase):
    @override_settings(SSO_AUTH_URL=None, SSO_CLIENT_ID=None, SSO_REQUIRED=True)
    def test_sso_disabled_without_settings(self):
        r = APIClient().get(CONFIG)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"sso_enabled": False, "password_login": False})
        self.assertIn("csrftoken", r.cookies)

    @override_settings(SSO_AUTH_URL="https://sso.example/auth", SSO_CLIENT_ID="ivs", SSO_REQUIRED=False)
    def test_sso_enabled_and_password_login(self):
        self.assertEqual(APIClient().get(CONFIG).json(), {"sso_enabled": True, "password_login": True})

    @override_settings(SSO_AUTH_URL=None, SSO_CLIENT_ID=None)
    def test_sso_start_without_settings_is_503_not_none_redirect(self):
        r = self.client.get("/sso/start/")
        self.assertEqual(r.status_code, 503)


class PasswordLoginTests(TestCase):
    def setUp(self):
        User.objects.create_user("ali", password="Parol12345!")
        self.c = APIClient(enforce_csrf_checks=True)
        self.c.get(CONFIG)  # csrftoken cookie
        self.csrf = self.c.cookies["csrftoken"].value

    def post(self, data):
        return self.c.post(LOGIN, data, format="json", HTTP_X_CSRFTOKEN=self.csrf)

    @override_settings(SSO_REQUIRED=True)
    def test_forbidden_while_sso_required(self):
        self.assertEqual(self.post({"username": "ali", "password": "Parol12345!"}).status_code, 403)

    @override_settings(SSO_REQUIRED=False)
    def test_wrong_password(self):
        r = self.post({"username": "ali", "password": "xato"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.c.get("/api/v1/me/").status_code, 401)

    @override_settings(SSO_REQUIRED=False)
    def test_login_creates_session(self):
        r = self.post({"username": "ali", "password": "Parol12345!"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.c.get("/api/v1/me/").json()["username"], "ali")

    @override_settings(SSO_REQUIRED=False)
    def test_csrf_required(self):
        r = self.c.post(LOGIN, {"username": "ali", "password": "Parol12345!"}, format="json")
        self.assertEqual(r.status_code, 403)
