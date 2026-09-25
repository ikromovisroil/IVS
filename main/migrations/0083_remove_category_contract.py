from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0082_copy_category_links"),
    ]

    operations = [
        migrations.RemoveField(model_name="category", name="contract"),
    ]
