from decimal import Decimal

from django.db import migrations
from django.db.models import DecimalField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce


def backfill(apps, schema_editor):
    """
    Mavjud arizadagi materiallar va material harakatlari uchun "surat": o'sha paytdagi narx/nom/birlik/kod noma'lum,
    shuning uchun materialning HOZIRGI qiymatlari yoziladi. Bundan keyingi yozuvlar paytida to'g'ri yoziladi.
    Sarf harakatlari uchun javobgarning HOZIRGI tashkiloti va hududi yoziladi.
    """
    Material = apps.get_model("main", "Material")
    OrderMaterial = apps.get_model("main", "OrderMaterial")
    MaterialMovement = apps.get_model("main", "MaterialMovement")
    Employee = apps.get_model("main", "Employee")

    def mat(field, ref="material_id"):
        return Subquery(Material.objects.filter(pk=OuterRef(ref)).values(field)[:1])

    dec = DecimalField(max_digits=12, decimal_places=2)
    values = dict(
        price=Coalesce(mat("price"), Value(Decimal("0")), output_field=dec),
        unit_name=Coalesce(mat("unit__name"), Value("")),
        material_name=Coalesce(mat("name"), Value("")),
        material_code=Coalesce(mat("code"), Value("")),
    )

    OrderMaterial.objects.filter(material__isnull=False, price__isnull=True).update(**values)
    MaterialMovement.objects.filter(material__isnull=False, price__isnull=True).update(**values)

    emp = lambda field: Subquery(Employee.objects.filter(pk=OuterRef("user_id")).values(field)[:1])
    MaterialMovement.objects.filter(user__isnull=False, user_organization__isnull=True, user_region__isnull=True).update(
        user_organization_id=emp("organization_id"),
        user_region_id=emp("region_id"),
    )


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0095_price_unit_snapshots"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
