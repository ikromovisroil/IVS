"""Hududlar ro'yxati (selektlar uchun) ID bo'yicha tartiblanadi, nom bo'yicha emas."""
from django.test import TestCase
from rest_framework.test import APIClient

from main.models import Region
from main.testing import make_employee, make_org


class RegionsOrderTests(TestCase):
    def test_regions_are_listed_by_id(self):
        names = ["Toshkent", "Andijon", "Buxoro", "Surxondaryo"]       # nom bo'yicha tartib id bo'yicha tartibdan farq qiladi
        created = [Region.objects.create(name=n) for n in names]
        user, _ = make_employee(make_org("worker"), created[0], superuser=True)
        api = APIClient()
        api.force_authenticate(user)
        res = api.get("/api/v1/regions/", {"page_size": 100})
        ids = [r["id"] for r in res.data["results"]]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(ids, [r.id for r in created])
