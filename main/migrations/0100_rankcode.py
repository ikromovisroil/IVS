from django.db import migrations, models
import django.db.models.deletion


def fill_codes(apps, schema_editor):
    """Mavjud lavozimlarning kodlarini RankCode jadvaliga ko'chiradi (kod bo'yicha qidirish avvalgidek ishlaydi)."""
    Rank = apps.get_model("main", "Rank")
    RankCode = apps.get_model("main", "RankCode")
    seen = set()
    for rank in Rank.objects.exclude(code__isnull=True).order_by("id").iterator():
        code = (rank.code or "").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        RankCode.objects.create(code=code, rank_id=rank.id)


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0099_backfill_deed_region"),
    ]

    operations = [
        migrations.CreateModel(
            name="RankCode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=20, unique=True)),
                ("rank", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="codes", to="main.rank")),
            ],
            options={
                "verbose_name": "Lavozim kodi",
                "verbose_name_plural": "Lavozim kodlari",
                "db_table": "rank_code",
            },
        ),
        migrations.RunPython(fill_codes, migrations.RunPython.noop),
    ]
