from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from main.sso_utils import sync_employee_from_claims
from main.testing import grant, make_employee, make_org, make_region

CLAIMS = {
    "pinfl": "12345678901234",
    "birth_date": "1990-05-15",
    "doc_serial_number": "ab1234567",
    "phone_number": "+998901112233",
}


class SyncEmployeeFromClaimsTests(TestCase):
    def setUp(self):
        _, self.emp = make_employee(make_org("worker"), make_region())

    def test_writes_birth_date_passport_and_phone(self):
        sync_employee_from_claims(self.emp, CLAIMS)
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.birth_date, date(1990, 5, 15))
        self.assertEqual(self.emp.passport, "AB1234567")           # katta harfga keltiriladi
        self.assertEqual(self.emp.sso_phone, "+998901112233")
        self.assertIsNone(self.emp.phone)                           # qo'lda kiritiladigan raqamga tegmaydi

    def test_does_not_touch_manual_phone(self):
        self.emp.phone = "1234"
        self.emp.save()
        sync_employee_from_claims(self.emp, CLAIMS)
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.phone, "1234")

    def test_empty_or_invalid_values_do_not_erase_existing(self):
        sync_employee_from_claims(self.emp, CLAIMS)
        sync_employee_from_claims(self.emp, {"birth_date": "", "doc_serial_number": "xx", "phone_number": ""})
        sync_employee_from_claims(self.emp, {"birth_date": "31-02-1990", "doc_serial_number": "AB12"})
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.birth_date, date(1990, 5, 15))
        self.assertEqual(self.emp.passport, "AB1234567")
        self.assertEqual(self.emp.sso_phone, "+998901112233")

    def test_fills_only_empty_fields(self):
        self.emp.passport = "CD7654321"
        self.emp.save()
        sync_employee_from_claims(self.emp, CLAIMS)
        sync_employee_from_claims(self.emp, {**CLAIMS, "phone_number": "+998909998877", "birth_date": "2000-01-01"})
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.passport, "CD7654321")            # mavjud qiymat o'zgarmaydi
        self.assertEqual(self.emp.sso_phone, "+998901112233")       # birinchi to'ldirilgani qoladi
        self.assertEqual(self.emp.birth_date, date(1990, 5, 15))

    def test_missing_claims_are_ok(self):
        sync_employee_from_claims(self.emp, {})
        self.emp.refresh_from_db()
        self.assertIsNone(self.emp.birth_date)
        self.assertIsNone(self.emp.passport)


class PersonalDataNotExposedTests(TestCase):
    def test_not_in_employee_api(self):
        org, region = make_org("worker"), make_region()
        viewer_user, _ = make_employee(org, region)
        grant(viewer_user, "main.view_employee")
        _, target = make_employee(org, region)
        sync_employee_from_claims(target, CLAIMS)

        client = APIClient()
        client.force_authenticate(viewer_user)
        body = client.get(f"/api/v1/employees/{target.id}/").content.decode()
        for secret in ("AB1234567", "+998901112233", "1990-05-15", "birth_date", "passport", "sso_phone"):
            self.assertNotIn(secret, body)
