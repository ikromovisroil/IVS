from django.db import migrations
from django.db.models import OuterRef, Subquery


def backfill(apps, schema_editor):
    """
    Mavjud arizalar uchun "surat": o'sha paytdagi joyni bilib bo'lmaydi, shuning uchun yuboruvchi/bajaruvchining
    HOZIRGI tashkiloti, hududi va bo'limi yoziladi. Yuboruvchisi allaqachon o'chirilgan arizalar bo'sh qoladi.
    Bundan keyingi arizalar to'g'ri paytda yoziladi (Order.save).
    """
    Order = apps.get_model("main", "Order")
    Employee = apps.get_model("main", "Employee")

    def emp_value(field, ref):
        return Subquery(Employee.objects.filter(pk=OuterRef(ref)).values(field)[:1])

    Order.objects.filter(sender__isnull=False, sender_organization__isnull=True, sender_region__isnull=True,
                         sender_department__isnull=True).update(
        sender_organization_id=emp_value("organization_id", "sender_id"),
        sender_region_id=emp_value("region_id", "sender_id"),
        sender_department_id=emp_value("department_id", "sender_id"),
    )
    Order.objects.filter(receiver__isnull=False, receiver_region__isnull=True).update(
        receiver_region_id=emp_value("region_id", "receiver_id"),
    )


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0093_order_snapshot_fields"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
