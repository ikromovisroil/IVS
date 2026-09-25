from django.db import migrations


def _merge(model, group_field, old_field, m2m_name):
    """Har bir `group_field` (xodim/yuboruvchi) uchun bitta qator qoldiriladi;
    boshqa qatorlardagi eski FK qiymatlari M2M ga yig'iladi."""
    keep = {}
    for row in model.objects.order_by("id"):
        key = getattr(row, group_field + "_id")
        if key is None:
            row.delete()
            continue
        main_row = keep.setdefault(key, row)
        old_id = getattr(row, old_field + "_id")
        if old_id:
            getattr(main_row, m2m_name).add(old_id)
        if main_row.pk != row.pk:
            row.delete()


def forwards(apps, schema_editor):
    _merge(apps.get_model("main", "OrderGoal"), "employee", "old_goal", "goal")
    _merge(apps.get_model("main", "MaterialEmployee"), "employee", "old_category", "category")
    _merge(apps.get_model("main", "MaterialUser"), "sender", "old_receiver", "receiver")


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0089_m2m_goal_receiver_matcategory"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
