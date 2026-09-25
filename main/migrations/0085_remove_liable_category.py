from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0084_liable_by_contract"),
    ]

    operations = [
        migrations.RemoveField(model_name="liable", name="category"),
    ]
