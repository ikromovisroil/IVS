from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0080_alter_deed_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="contract",
            name="categories",
            field=models.ManyToManyField(
                blank=True, related_name="contracts", to="main.category", verbose_name="Kategoriyalar"
            ),
        ),
    ]
