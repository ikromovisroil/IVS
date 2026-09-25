from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0088_remove_liable_old_contract"),
    ]

    operations = [
        # OrderGoal.goal
        migrations.RenameField(model_name="ordergoal", old_name="goal", new_name="old_goal"),
        migrations.AlterField(
            model_name="ordergoal",
            name="old_goal",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=models.deletion.SET_NULL,
                related_name="+", to="main.goal",
            ),
        ),
        migrations.AddField(
            model_name="ordergoal",
            name="goal",
            field=models.ManyToManyField(blank=True, to="main.goal"),
        ),
        # MaterialEmployee.category
        migrations.RenameField(model_name="materialemployee", old_name="category", new_name="old_category"),
        migrations.AlterField(
            model_name="materialemployee",
            name="old_category",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=models.deletion.SET_NULL,
                related_name="+", to="main.materialcategory",
            ),
        ),
        migrations.AddField(
            model_name="materialemployee",
            name="category",
            field=models.ManyToManyField(blank=True, to="main.materialcategory"),
        ),
        # MaterialUser.receiver
        migrations.RenameField(model_name="materialuser", old_name="receiver", new_name="old_receiver"),
        migrations.AlterField(
            model_name="materialuser",
            name="old_receiver",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=models.deletion.SET_NULL,
                related_name="+", to="main.employee",
            ),
        ),
        migrations.AddField(
            model_name="materialuser",
            name="receiver",
            field=models.ManyToManyField(blank=True, to="main.employee"),
        ),
    ]
