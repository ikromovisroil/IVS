from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0090_merge_goal_receiver_matcategory_rows"),
    ]

    operations = [
        migrations.RemoveField(model_name="ordergoal", name="old_goal"),
        migrations.RemoveField(model_name="materialemployee", name="old_category"),
        migrations.RemoveField(model_name="materialuser", name="old_receiver"),
    ]
