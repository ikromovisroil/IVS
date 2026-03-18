from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('main', '0086_merge_20260313_1150'),
    ]

    operations = [
        migrations.AddField(
            model_name='technics',
            name='qr_code',
            field=models.ImageField(blank=True, null=True, upload_to='qk/'),
        ),
        migrations.AlterField(
            model_name='deed',
            name='code',
            field=models.CharField(blank=True, max_length=100, null=True, unique=True),
        ),
    ]