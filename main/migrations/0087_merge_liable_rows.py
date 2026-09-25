from django.db import migrations


def forwards(apps, schema_editor):
    """Har bir xodim uchun bitta Liable qatori: eski qatorlardagi shartnomalar
    `contracts` ga, 0084 da saqlangan kategoriyalar `categorys` ga yig'iladi."""
    Liable = apps.get_model("main", "Liable")
    Category = apps.get_model("main", "Category")

    keep = {}
    for lb in Liable.objects.order_by("id"):
        main_row = keep.setdefault(lb.employee_id, lb)
        if lb.old_contract_id:
            main_row.contracts.add(lb.old_contract_id)
        if main_row.pk != lb.pk:
            lb.delete()

    connection = schema_editor.connection
    if "liable_category_stash" in connection.introspection.table_names():
        with connection.cursor() as cursor:
            cursor.execute("SELECT employee_id, category_id FROM liable_category_stash")
            pairs = cursor.fetchall()
        valid_categories = set(Category.objects.values_list("id", flat=True))
        for employee_id, category_id in pairs:
            if category_id not in valid_categories:
                continue
            row = keep.get(employee_id)
            if row is None:
                row = Liable.objects.create(employee_id=employee_id)
                keep[employee_id] = row
            row.categorys.add(category_id)
        schema_editor.execute("DROP TABLE liable_category_stash")


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0086_liable_contract_m2m"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
