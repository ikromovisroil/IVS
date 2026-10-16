"""Sarf (Service) hisoboti: javobgar shaxsning bo'limi hujjat matni uchun serverdan keladi."""
from datetime import date

from django.test import TestCase
from django.urls import reverse

from main.models import Department, Directorate, Division, Material, MaterialMovement, Rank
from main.testing import make_employee, make_org, make_region


class ServiceMaterialsUnitTests(TestCase):
    def setUp(self):
        self.org = make_org("worker")
        self.region = make_region()
        self.dept = Department.objects.create(name="Axborot bo'limi", organization=self.org, region=self.region)
        self.directorate = Directorate.objects.create(name="Texnik va tarmoq xizmatlarini ko'rsatish boshqarmasi", department=self.dept)
        self.division = Division.objects.create(name="Qurilmalarga texnik xizmat ko'rsatish bo'limi", directorate=self.directorate)
        self.rank = Rank.objects.create(code="1", name="Boshlig'i")
        self.user, self.viewer = make_employee(self.org, self.region, perms=["main.material_service"])
        self.material = Material.objects.create(name="Kabel", organization=self.org, employee=self.viewer, number=100, price=1000)

    def _spend(self, employee):
        movement = MaterialMovement.objects.create(
            material=self.material, user=employee, outcome=2, status="service", body="sarf",
        )
        return movement

    def _unit_of(self, employee):
        self.client.force_login(self.user)
        response = self.client.get(reverse("ajax_service_materials"), {
            "date1": date.today().isoformat(), "date2": date.today().isoformat(),
            "organizations[]": [self.org.id],
        })
        self.assertEqual(response.status_code, 200)
        rows = [r for r in response.json() if r["full_name"].strip() == employee.full_name.strip()]
        self.assertTrue(rows, "sarf qatori topilmadi")
        return rows[0]

    def test_department_name_is_returned_even_for_division_staff(self):
        _, in_division = make_employee(self.org, self.region, first="Ulugbek", last="Ismoilov")
        in_division.division = self.division
        in_division.rank = self.rank
        in_division.save()                              # Employee.save: boshqarma va bo'lim ham o'rnatiladi
        self._spend(in_division)
        row = self._unit_of(in_division)
        self.assertEqual(row["owner_unit"], self.dept.name)          # doim departament (dep) nomi
        self.assertEqual(row["rank_name"], "Boshlig'i")

    def test_department_is_returned_for_directorate_and_department_staff(self):
        _, in_directorate = make_employee(self.org, self.region, first="Anvar", last="Narzullayev")
        in_directorate.directorate = self.directorate
        in_directorate.save()
        _, in_department = make_employee(self.org, self.region, first="Oybek", last="Aliyev")
        in_department.department = self.dept
        in_department.save()
        self._spend(in_directorate)
        self._spend(in_department)
        self.assertEqual(self._unit_of(in_directorate)["owner_unit"], self.dept.name)
        self.assertEqual(self._unit_of(in_department)["owner_unit"], self.dept.name)

    def test_employee_without_unit_gets_empty_string(self):
        _, nobody = make_employee(self.org, self.region, first="Hech", last="Kim")
        self._spend(nobody)
        self.assertEqual(self._unit_of(nobody)["owner_unit"], "")


class ServicePeriodTests(TestCase):
    """Hisobot davri (yil va chorak) boshlang'ich qiymati bugungi sanadan olinadi."""

    def test_quarter_roman_by_month(self):
        from main.views import quarter_roman

        expected = {1: "I", 2: "I", 3: "I", 4: "II", 5: "II", 6: "II", 7: "III", 8: "III", 9: "III", 10: "IV", 11: "IV", 12: "IV"}
        for month, quarter in expected.items():
            self.assertEqual(quarter_roman(month), quarter, month)

    def test_page_uses_today_year_and_quarter(self):
        from unittest import mock

        org = make_org("worker")
        user, _ = make_employee(org, make_region(), perms=["main.material_service"])
        self.client.force_login(user)
        for day, year, quarter in ((date(2026, 10, 16), "2026", "IV"), (date(2027, 2, 3), "2027", "I"), (date(2026, 8, 1), "2026", "III")):
            with mock.patch("django.utils.timezone.localdate", return_value=day):
                html = self.client.get(reverse("service_get")).content.decode()
            self.assertIn(f'<span id="year">{year}</span>', html, day)
            self.assertIn(f'<span id="chorak">{quarter}</span>', html, day)
