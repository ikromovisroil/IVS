"""o' va g' -> o‘ va g‘: funksiya, saqlashdagi avtomatik tuzatish va qidiruv."""
from django.apps import apps
from django.test import TestCase
from rest_framework.test import APIClient

from main.models import Employee, Organization, Rank, Region
from main.testing import make_employee, make_org, make_region
from main.uz_text import NORMALIZED_FIELDS, normalize_og


class NormalizeFunctionTests(TestCase):
    def test_o_and_g_variants(self):
        self.assertEqual(normalize_og("Po'latov Bahodir o'g'li"), "Po‘latov Bahodir o‘g‘li")
        self.assertEqual(normalize_og("G'aznachilik xizmati"), "G‘aznachilik xizmati")
        self.assertEqual(normalize_og("O`zbekiston oʻrta o’zi"), "O‘zbekiston o‘rta o‘zi")

    def test_other_text_is_untouched(self):
        self.assertEqual(normalize_og("Ma'lumot, sa'y, 'Tirnoq'"), "Ma'lumot, sa'y, 'Tirnoq'")       # a'/e'/tirnoq tegilmaydi
        self.assertEqual(normalize_og("go' "), "go' ")                                              # keyin harf yo'q
        self.assertEqual(normalize_og("o‘g‘li"), "o‘g‘li")                                          # takror ishlatsa o'zgarmaydi
        self.assertIsNone(normalize_og(None))
        self.assertEqual(normalize_og(""), "")

    def test_registry_matches_real_fields(self):
        for model_name, fields in NORMALIZED_FIELDS.items():
            model = apps.get_model("main", model_name)
            for field in fields:
                model._meta.get_field(field)       # mavjud bo'lmasa FieldDoesNotExist


class SaveNormalizationTests(TestCase):
    def test_names_are_normalized_on_save(self):
        org = Organization.objects.create(name="O'zbekiston Respublikasi G'aznachilik", type="worker")
        self.assertEqual(org.name, "O‘zbekiston Respublikasi G‘aznachilik")
        self.assertEqual(Organization.objects.get(pk=org.pk).name, "O‘zbekiston Respublikasi G‘aznachilik")
        rank = Rank.objects.create(name="Bo'lim boshlig'i")
        self.assertEqual(Rank.objects.get(pk=rank.pk).name, "Bo‘lim boshlig‘i")

    def test_employee_name_and_patronymic_suffix(self):
        _, emp = make_employee(make_org("worker"), make_region(), last="Po'latov")
        emp.first_name, emp.father_name = "xojiakbar", "Bahodir O'G'LI"
        emp.save()
        emp = Employee.objects.get(pk=emp.pk)
        self.assertEqual((emp.last_name, emp.first_name, emp.father_name), ("Po‘latov", "Xojiakbar", "Bahodir o‘g‘li"))


class SearchTests(TestCase):
    def test_search_with_plain_apostrophe_finds_normalized_name(self):
        region = Region.objects.create(name="Qo'qon viloyati")        # saqlashda Qo‘qon bo'ladi
        user, _ = make_employee(make_org("worker"), region, superuser=True)
        api = APIClient()
        api.force_authenticate(user)
        res = api.get("/api/v1/regions/", {"search": "Qo'qon"})
        self.assertEqual([r["name"] for r in res.data["results"]], ["Qo‘qon viloyati"])
