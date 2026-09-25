from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0087_merge_liable_rows"),
    ]

    operations = [
        migrations.RemoveField(model_name="liable", name="old_contract"),
    ]
