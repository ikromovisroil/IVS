from django.db import migrations
from django.db.models import OuterRef, Subquery


def backfill(apps, schema_editor):
    """Mavjud hujjatlar uchun hudud surati: yaratuvchining (bo'lmasa imzolovchining) HOZIRGI hududi."""
    Deed = apps.get_model("main", "Deed")
    Employee = apps.get_model("main", "Employee")

    def region_of(ref):
        return Subquery(Employee.objects.filter(pk=OuterRef(ref)).values("region_id")[:1])

    Deed.objects.filter(user__isnull=False, user_region__isnull=True).update(user_region_id=region_of("user_id"))
    Deed.objects.filter(user__isnull=True, sender__isnull=False, user_region__isnull=True).update(
        user_region_id=region_of("sender_id"))


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0098_deed_region_snapshot"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
