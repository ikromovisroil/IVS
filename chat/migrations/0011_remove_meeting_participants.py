from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0010_meeting_invitation'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='meeting',
            name='participants',
        ),
    ]
