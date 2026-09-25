from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0085_remove_liable_category"),
    ]

    operations = [
        migrations.RenameField(model_name="liable", old_name="contract", new_name="old_contract"),
        migrations.AlterField(
            model_name="liable",
            name="old_contract",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=models.deletion.SET_NULL,
                related_name="+", to="main.contract",
            ),
        ),
        migrations.AddField(
            model_name="liable",
            name="contracts",
            field=models.ManyToManyField(blank=True, to="main.contract"),
        ),
        migrations.AddField(
            model_name="liable",
            name="categorys",
            field=models.ManyToManyField(blank=True, to="main.category"),
        ),
    ]
