"""api/spa/warehouse.py — "Ombor": texnikalar ro'yxati/statistikasi/kartasi, Texnikalarim, qurilmalar, savat."""
import shutil
import tempfile
from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from main.models import (Category, Group, Liable, Material, MaterialCategory, MaterialMovement, Structure, StructureCategory, Technics,
                         Unit)
from main.testing import grant, make_department, make_employee, make_org, make_region

BASE = "/api/v1/spa/warehouse"
MEDIA = tempfile.mkdtemp(prefix="warehouse-tests-")


@override_settings(MEDIA_ROOT=MEDIA, CONTEXT_CACHE_SECONDS=0)
class WarehouseSpaTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.org = make_org("client")
        self.other_org = make_org("client")
        self.region = make_region()
        self.dep = make_department(self.org, self.region)
        group = Group.objects.create(name="Kompyuter")
        self.cat = Category.objects.create(name="Noutbuk", group=group)
        self.cat2 = Category.objects.create(name="Printer", group=group)

        self.viewer_user, self.viewer = make_employee(
            self.org, self.region, perms=["main.view_technics"], last="Ko'ruvchi")
        Liable.objects.create(employee=self.viewer).categorys.add(self.cat)
        self.owner_user, self.owner = make_employee(self.org, self.region, department=self.dep, last="Egasi", first="Sardor")
        self.plain_user, self.plain = make_employee(self.org, self.region, last="Oddiy")

        def tex(name, cat, org=None, **kw):
            return Technics.objects.create(name=name, category=cat, group=group, organization=org or self.org,
                                           region=self.region, **kw)

        self.t1 = tex("Lenovo T14", self.cat, employee=self.owner, status="active", serial="SN-1")
        self.t2 = tex("Dell 5420", self.cat, status="free")
        self.t3 = tex("HP M404", self.cat2, status="repair")                     # Liable da yo'q kategoriya
        self.t4 = tex("Begona", self.cat, org=self.other_org, status="active")   # boshqa tashkilot
        self.t5 = tex("O'chirilgan", self.cat, status="free", is_active=False)

        scat = StructureCategory.objects.create(name="Monitor")
        self.s1 = Structure.objects.create(name="Dell P2422H", category=scat, organization=self.org, region=self.region,
                                           technics=self.t1)

    def api(self, user):
        c = APIClient()
        c.force_login(user)
        return c

    # ── texnikalar ──

    def test_list_scope_and_devices(self):
        r = self.api(self.viewer_user).get(f"{BASE}/technics/")
        self.assertEqual(r.status_code, 200)
        names = [x["name"] for x in r.data["results"]]
        self.assertCountEqual(names, ["Lenovo T14", "Dell 5420"])  # Liable kategoriyasi, o'z tashkiloti, faol
        row = next(x for x in r.data["results"] if x["id"] == self.t1.id)
        self.assertEqual(row["extra_devices"][0]["category_name"], "Monitor")
        self.assertEqual(row["employee_name"], self.owner.full_name)

    def test_search_by_employee_name(self):
        r = self.api(self.viewer_user).get(f"{BASE}/technics/", {"search": "egasi sardor"})
        self.assertEqual([x["id"] for x in r.data["results"]], [self.t1.id])
        r = self.api(self.viewer_user).get(f"{BASE}/technics/", {"search": "SN-1"})
        self.assertEqual([x["id"] for x in r.data["results"]], [self.t1.id])

    def test_stats(self):
        r = self.api(self.viewer_user).get(f"{BASE}/technics/stats/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, {"total": 2, "active": 1, "free": 1, "repair": 0, "defect": 0})
        r = self.api(self.viewer_user).get(f"{BASE}/technics/stats/", {"status": "free"})
        self.assertEqual(r.data["total"], 1)

    def test_list_requires_view_technics(self):
        self.assertEqual(self.api(self.plain_user).get(f"{BASE}/technics/").status_code, 403)
        self.assertEqual(self.api(self.plain_user).get(f"{BASE}/technics/stats/").status_code, 403)

    def test_card_for_any_user(self):
        r = self.api(self.plain_user).get(f"{BASE}/technics/{self.t3.id}/card/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["name"], "HP M404")
        self.assertEqual(self.api(self.plain_user).get(f"{BASE}/technics/{self.t5.id}/card/").status_code, 404)

    def test_mine(self):
        r = self.api(self.owner_user).get(f"{BASE}/technics/mine/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual([x["id"] for x in r.data["results"]], [self.t1.id])
        self.assertFalse(r.data["is_boss"])

    def test_mine_boss_sees_department(self):
        boss_user, boss = make_employee(self.org, self.region, department=self.dep, perms=["main.boss_employee"], last="Boss")
        self.t2.department = self.dep
        self.t2.save()
        r = self.api(boss_user).get(f"{BASE}/technics/mine/")
        self.assertTrue(r.data["is_boss"])
        # t1 egasining bo'limi orqali (Technics.save) shu bo'limga tushadi
        self.assertCountEqual([x["id"] for x in r.data["results"]], [self.t1.id, self.t2.id])
        without = [e["id"] for e in r.data["employees_without_technics"]]
        self.assertIn(boss.id, without)
        self.assertNotIn(self.owner.id, without)

    # ── qo'shimcha qurilmalar ──

    def test_structures_list(self):
        self.assertEqual(self.api(self.viewer_user).get(f"{BASE}/structures/").status_code, 403)
        user = grant(self.viewer_user, "main.change_technics")
        r = self.api(user).get(f"{BASE}/structures/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["results"][0]["technics_employee_name"], self.owner.full_name)
        self.assertEqual(r.data["results"][0]["technics_serial"], "SN-1")

    def test_structures_stats_counts_by_status(self):
        self.assertEqual(self.api(self.viewer_user).get(f"{BASE}/structures/stats/").status_code, 403)
        user = grant(self.viewer_user, "main.change_technics")
        r = self.api(user).get(f"{BASE}/structures/stats/")
        self.assertEqual(r.status_code, 200, r.data)
        listed = self.api(user).get(f"{BASE}/structures/").data["count"]
        self.assertEqual(r.data["total"], listed)
        self.assertEqual(r.data["total"], r.data["active"] + r.data["free"] + r.data["repair"] + r.data["defect"])
        only_free = self.api(user).get(f"{BASE}/structures/stats/", {"status": "free"}).data
        self.assertEqual(only_free["total"], only_free["free"])

    def test_org_employees(self):
        r = self.api(self.viewer_user).get(f"{BASE}/employees/", {"organization": self.org.id})
        ids = [e["id"] for e in r.json()["results"]]
        self.assertIn(self.owner.id, ids)

    def test_pinfl_bridge(self):
        self.assertEqual(self.api(self.viewer_user).post(f"{BASE}/employees/pinfl/", {"pinfl": "1"}).status_code, 403)
        user = grant(self.viewer_user, "main.add_employee")
        self.owner.pinfl = "12345678901234"
        self.owner.save()
        r = self.api(user).post(f"{BASE}/employees/pinfl/", {"pinfl": "12345678901234"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("allaqachon", r.data["detail"])

    # ── materiallar ──

    def _materials(self):
        unit = Unit.objects.create(name="dona")
        shop_user, shop = make_employee(self.org, self.region, perms=[
            "main.view_material", "main.shop_employee", "main.all_material_employee"], last="Omborchi")
        recv_user, recv = make_employee(self.org, self.region, perms=["main.shop_employee"], last="Oluvchi")
        mat = Material.objects.create(organization=self.org, employee=shop, unit=unit, name="Kabel", code="100",
                                      number=10, price=Decimal("1500"))
        Material.objects.create(organization=self.org, employee=recv, unit=unit, name="Toner", code="200",
                                number=2, price=Decimal("100"))
        return shop_user, shop, recv, mat

    def test_material_employees_and_summary(self):
        shop_user, shop, recv, mat = self._materials()
        r = self.api(shop_user).get(f"{BASE}/materials/employees/")
        self.assertCountEqual([e["id"] for e in r.data], [shop.id, recv.id])
        r = self.api(shop_user).get(f"{BASE}/materials/summary/", {"employee": shop.id})
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(Decimal(r.data["total_sum"]), Decimal("15000"))
        self.assertEqual(self.api(self.plain_user).get(f"{BASE}/materials/summary/").status_code, 403)

    def test_basket_flow(self):
        shop_user, shop, recv, mat = self._materials()
        c = self.api(shop_user)
        r = c.post(f"{BASE}/materials/basket/", {"material_id": mat.id, "number": 3}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        r = c.get(f"{BASE}/materials/basket/")
        self.assertEqual(r.data["count"], 1)
        row = r.data["results"][0]
        self.assertEqual((row["number"], Decimal(row["total_sum"])), (3, Decimal("4500")))

        r = c.post(f"{BASE}/materials/basket/assign/", {"employee": recv.id, "body": "Test"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        mat.refresh_from_db()
        self.assertEqual(mat.number, 7)
        self.assertEqual(Material.objects.get(employee=recv, code="100").number, 3)
        self.assertEqual(c.get(f"{BASE}/materials/basket/").data["count"], 0)

        # bo'sh savatni biriktirish — xato
        r = c.post(f"{BASE}/materials/basket/assign/", {"employee": recv.id}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_basket_assign_copies_category_to_receiver(self):
        shop_user, shop, recv, mat = self._materials()
        cat = MaterialCategory.objects.create(organization=self.org, name="Kabellar")
        mat.category = cat
        mat.save()
        c = self.api(shop_user)
        c.post(f"{BASE}/materials/basket/", {"material_id": mat.id, "number": 3}, format="json")
        self.assertEqual(c.post(f"{BASE}/materials/basket/assign/", {"employee": recv.id}, format="json").status_code, 200)
        # oluvchida material yo'q edi — yangi yaratiladi, kategoriya bilan
        self.assertEqual(Material.objects.get(employee=recv, code="100").category_id, cat.id)

        # oluvchida kategoriyasiz material bor bo'lsa — kategoriya to'ldiriladi, bor bo'lsa o'zgarmaydi
        other = MaterialCategory.objects.create(organization=self.org, name="Boshqa")
        existing = Material.objects.get(employee=recv, code="100")
        existing.category = None
        existing.save()
        c.post(f"{BASE}/materials/basket/", {"material_id": mat.id, "number": 1}, format="json")
        c.post(f"{BASE}/materials/basket/assign/", {"employee": recv.id}, format="json")
        existing.refresh_from_db()
        self.assertEqual((existing.number, existing.category_id), (4, cat.id))
        existing.category = other
        existing.save()
        c.post(f"{BASE}/materials/basket/", {"material_id": mat.id, "number": 1}, format="json")
        c.post(f"{BASE}/materials/basket/assign/", {"employee": recv.id}, format="json")
        existing.refresh_from_db()
        self.assertEqual((existing.number, existing.category_id), (5, other.id))

    def test_material_code_is_unique_per_employee(self):
        shop_user, shop, recv, mat = self._materials()
        unit = mat.unit
        grant(shop_user, "main.add_material", "main.change_material")
        grant(recv.user, "main.add_material")
        c = self.api(shop_user)
        url = "/api/v1/materials/"
        # shu xodimda "100" kodi bor (mat) — yana yaratib bo'lmaydi
        r = c.post(url, {"name": "Boshqa kabel", "code": "100", "number": 1, "unit": unit.id}, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn("code", r.data)
        # boshqa kod yoki kodsiz — mumkin (kodsiz materiallar bir nechta bo'la oladi)
        for body in ({"name": "A", "code": "101"}, {"name": "B"}, {"name": "C"}):
            r = c.post(url, {**body, "number": 1, "unit": unit.id}, format="json")
            self.assertEqual(r.status_code, 201, r.data)
        # boshqa xodimda xuddi shu kod bo'la oladi
        r = self.api(recv.user).post(url, {"name": "Kabel", "code": "100", "number": 1, "unit": unit.id}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        # tahrirlash: o'zining kodini saqlash mumkin, boshqa materialning kodiga o'zgartirib bo'lmaydi
        other = Material.objects.get(employee=shop, code="101")
        self.assertEqual(c.patch(f"{url}{other.id}/", {"code": "101", "name": "A2"}, format="json").status_code, 200)
        self.assertEqual(c.patch(f"{url}{other.id}/", {"code": "100"}, format="json").status_code, 400)
        # o'chirilgan (faol emas) materialning kodi bloklamaydi
        Material.objects.filter(pk=mat.pk).update(is_active=False)
        self.assertEqual(c.patch(f"{url}{other.id}/", {"code": "100"}, format="json").status_code, 200)

    def test_material_list_is_ordered_by_1c_code(self):
        shop_user, shop, recv, mat = self._materials()
        unit = mat.unit
        for code in ("20", "3", "100", "", None):
            Material.objects.create(organization=self.org, employee=shop, unit=unit, name=f"M-{code}", code=code,
                                    number=1, price=Decimal("1"))
        r = self.api(shop_user).get("/api/v1/materials/", {"employee": shop.id, "page_size": 50})
        self.assertEqual(r.status_code, 200, r.data)
        codes = [m["code"] or "" for m in r.data["results"]]
        # katta kod tepada (100 > 20 > 3, son bo'yicha), kodsizlar oxirida
        numeric = [c for c in codes if c]
        self.assertEqual(numeric, sorted(numeric, key=lambda c: (len(c), c), reverse=True))
        self.assertEqual(codes[len(numeric):], [""] * (len(codes) - len(numeric)))
        self.assertLess(numeric.index("100"), numeric.index("20"))
        self.assertLess(numeric.index("20"), numeric.index("3"))

    def test_basket_delete_and_permissions(self):
        shop_user, shop, recv, mat = self._materials()
        mv = MaterialMovement.objects.create(material=mat, user=shop, employee=None, status="assigned", outcome=1)
        self.assertEqual(self.api(self.viewer_user).get(f"{BASE}/materials/basket/").status_code, 403)
        self.assertEqual(self.api(self.viewer_user).post(f"{BASE}/materials/basket/{mv.id}/delete/").status_code, 403)
        r = self.api(shop_user).post(f"{BASE}/materials/basket/{mv.id}/delete/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(MaterialMovement.objects.filter(pk=mv.pk).exists())
