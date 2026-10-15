"""Lavozimlar: nomni normallashtirish, kod bo'yicha qidirish, takrorlarni birlashtirish."""
import io

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from main.models import Employee, Rank, RankCode
from main.ranks import get_or_create_rank, normalize_rank_name, rank_for_code
from main.testing import make_employee, make_org


class NormalizeTests(SimpleTestCase):
    def test_apostrophe_case_and_spaces_are_ignored(self):
        variants = ["bo'lim boshlig'i", "Boʼlim boshligʼi", "bo‘lim boshlig‘i", "BO`LIM  BOSHLIG´I ", "boʼʼlim boshligʼʼi"]
        self.assertEqual({normalize_rank_name(v) for v in variants}, {"bo'lim boshlig'i"})

    def test_different_names_stay_different(self):
        self.assertNotEqual(normalize_rank_name("bosh mutaxassis"), normalize_rank_name("bosh mutaxassisi"))
        self.assertNotEqual(normalize_rank_name("yetakchi mutaxassis"), normalize_rank_name("etakchi mutaxassis"))


class RankLookupTests(TestCase):
    def test_lookup_via_rankcode_and_legacy_code(self):
        main = Rank.objects.create(code="100", name="Bosh mutaxassis")
        RankCode.objects.create(code="100", rank=main)
        RankCode.objects.create(code="200", rank=main)           # birlashtirilgan eski kod
        legacy = Rank.objects.create(code="300", name="Boshqa")  # RankCode'da yo'q (eski yozuv)
        self.assertEqual(rank_for_code("200"), main)
        self.assertEqual(rank_for_code(" 100 "), main)
        self.assertEqual(rank_for_code("300"), legacy)
        self.assertIsNone(rank_for_code("999"))
        self.assertIsNone(rank_for_code(""))
        self.assertIsNone(rank_for_code(None))

    def test_new_code_with_existing_name_reuses_rank(self):
        existing = Rank.objects.create(code="100", name="Bo'lim boshlig'i")
        RankCode.objects.create(code="100", rank=existing)
        rank, created = get_or_create_rank("777", "boʼlim boshligʼi")     # boshqa apostrof
        self.assertFalse(created)
        self.assertEqual(rank, existing)
        self.assertEqual(Rank.objects.count(), 1)
        self.assertEqual(rank_for_code("777"), existing)

    def test_new_name_creates_rank_and_code(self):
        rank, created = get_or_create_rank("555", "Yangi lavozim")
        self.assertTrue(created)
        self.assertEqual(rank.name, "Yangi lavozim")
        self.assertEqual(rank_for_code("555"), rank)
        again, created_again = get_or_create_rank("555", "Yangi lavozim")
        self.assertFalse(created_again)
        self.assertEqual(again, rank)

    def test_missing_name_falls_back_to_code_label(self):
        rank, _ = get_or_create_rank("42", "")
        self.assertEqual(rank.name, "Lavozim-42")


class MergeCommandTests(TestCase):
    def setUp(self):
        self.org = make_org("worker")

    def _rank(self, code, name, employees=0):
        rank = Rank.objects.create(code=code, name=name)
        if code:
            RankCode.objects.create(code=code, rank=rank)
        for _ in range(employees):
            _, emp = make_employee(self.org)
            emp.rank = rank
            emp.save()
        return rank

    def _run(self, *args):
        out = io.StringIO()
        call_command("merge_duplicate_ranks", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_changes_nothing(self):
        self._rank("1", "Bosh mutaxassis", 2)
        self._rank("2", "bosh mutaxassis", 1)
        output = self._run()
        self.assertIn("ortiqcha yozuv: 1", output)
        self.assertEqual(Rank.objects.count(), 2)
        self.assertEqual(RankCode.objects.count(), 2)

    def test_apply_merges_and_keeps_every_code_working(self):
        big = self._rank("1", "Bosh mutaxassis", 3)
        small = self._rank("2", "bosh mutaxassis", 1)
        variant = self._rank("3", "BOSH  MUTAXASSIS", 2)
        other = self._rank("9", "Qorovul", 1)
        self._run("--apply")

        self.assertEqual(Rank.objects.filter(pk__in=[big.pk, small.pk, variant.pk]).count(), 1)
        self.assertTrue(Rank.objects.filter(pk=big.pk).exists())      # xodimi eng ko'p bo'lgani qoladi
        self.assertEqual(Employee.objects.filter(rank=big).count(), 6)
        for code in ("1", "2", "3"):
            self.assertEqual(rank_for_code(code), big, code)           # eski kodlar ishlashda davom etadi
        self.assertEqual(Employee.objects.filter(rank=other).count(), 1)
        self.assertEqual(rank_for_code("9"), other)

    def test_different_names_are_not_merged(self):
        self._rank("1", "Bosh mutaxassis", 1)
        self._rank("2", "Bosh mutaxassisi", 1)
        self._rank("3", "Yetakchi mutaxassis", 1)
        self._rank("4", "Etakchi mutaxassis", 1)
        self._run("--apply")
        self.assertEqual(Rank.objects.count(), 4)

    def test_ranks_without_code_are_merged_by_name(self):
        coded = self._rank("5", "Yetakchi mutaxassis", 1)
        nocode = self._rank(None, "yetakchi mutaxassis", 4)       # xodimi ko'p, kodi yo'q
        self._run("--apply")
        self.assertEqual(Rank.objects.count(), 1)
        keeper = Rank.objects.get()
        self.assertEqual(keeper.pk, nocode.pk)
        self.assertEqual(Employee.objects.filter(rank=keeper).count(), 5)
        self.assertEqual(rank_for_code("5"), keeper)
        self.assertFalse(Rank.objects.filter(pk=coded.pk).exists())

    def test_nothing_to_merge(self):
        self._rank("1", "Qorovul", 1)
        output = self._run("--apply")
        self.assertIn("yo'q", output)
        self.assertEqual(Rank.objects.count(), 1)
