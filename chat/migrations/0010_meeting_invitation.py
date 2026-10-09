from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0009_meeting_finish'),
    ]

    operations = [
        migrations.AddField(
            model_name='meeting',
            name='invitation',
            field=models.TextField(blank=True, default=''),
        ),
    ]
