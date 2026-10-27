"""delete_unused_materials: faqat arizaga biriktirilmagan materiallar (va ularning kirim-chiqimi) o'chadi."""
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase

from main.models import Material, MaterialMovement, Order, OrderMaterial
from main.testing import make_employee, make_goal, make_org, make_region


class DeleteUnusedMaterialsTests(TestCase):
    def setUp(self):
        self.org, self.other = make_org("worker"), make_org("worker")
        region = make_region()
        _, self.emp = make_employee(self.org, region)
        _, self.other_emp = make_employee(self.other, region)
        goal = make_goal(self.org)
        self.used = Material.objects.create(name="Arizada", organization=self.org, employee=self.emp, number=1)
        self.free = Material.objects.create(name="Bo'sh", organization=self.org, employee=self.emp, number=5)
        self.alien = Material.objects.create(name="Boshqa tashkilot", organization=self.other, employee=self.other_emp, number=2)
        order = Order.objects.create(goal=goal, sender=self.emp, status="viewed")
        OrderMaterial.objects.create(order=order, material=self.used, number=1)
        for m in (self.used, self.free, self.alien):
            MaterialMovement.objects.create(material=m, employee=m.employee, income=m.number, status="created")

    def run_cmd(self, *args):
        out = StringIO()
        call_command("delete_unused_materials", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_deletes_nothing(self):
        text = self.run_cmd("--organization", str(self.org.pk))
        self.assertIn("o'chiriladi: 1", text)
        self.assertEqual(Material.objects.count(), 3)
        self.assertEqual(MaterialMovement.objects.count(), 3)

    def test_apply_deletes_only_unused_materials_of_that_organization(self):
        self.run_cmd("--organization", str(self.org.pk), "--apply")
        self.assertEqual(set(Material.objects.values_list("name", flat=True)), {"Arizada", "Boshqa tashkilot"})
        self.assertFalse(MaterialMovement.objects.filter(material_id=self.free.pk).exists())
        self.assertEqual(MaterialMovement.objects.count(), 2)       # boshqalarniki saqlanadi
        self.assertTrue(OrderMaterial.objects.filter(material=self.used).exists())

    def test_unknown_organization(self):
        with self.assertRaises(CommandError):
            self.run_cmd("--organization", "999999")
