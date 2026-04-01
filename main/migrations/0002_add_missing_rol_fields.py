from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="rol",
            name="client",
            field=models.BooleanField(default=False, db_index=True),
        ),
    ]