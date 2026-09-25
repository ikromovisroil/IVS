from django.db import migrations


def forwards(apps, schema_editor):
    Category = apps.get_model("main", "Category")
    for cat in Category.objects.filter(contract__isnull=False):
        cat.contracts.add(cat.contract_id)


def backwards(apps, schema_editor):
    Category = apps.get_model("main", "Category")
    for cat in Category.objects.all():
        cat.contract_id = cat.contracts.values_list("id", flat=True).first()
        cat.save(update_fields=["contract"])


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0081_contract_categories"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
