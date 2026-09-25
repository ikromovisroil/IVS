from django.db import migrations


def forwards(apps, schema_editor):
    """Eski Liable qatorlaridagi (xodim, kategoriya) juftliklari vaqtincha
    `liable_category_stash` jadvaliga saqlanadi (0087 ularni Liable.categorys ga
    qaytaradi). Shartnomasiz qatorlar o'chiriladi."""
    Liable = apps.get_model("main", "Liable")

    schema_editor.execute(
        'CREATE TABLE liable_category_stash AS '
        'SELECT employee_id, category_id FROM "Liable" '
        'WHERE category_id IS NOT NULL AND employee_id IS NOT NULL'
    )
    Liable.objects.filter(contract__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0083_remove_category_contract"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
