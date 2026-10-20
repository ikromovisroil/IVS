from django.db import migrations


def add_client_if_missing(apps, schema_editor):
    # 0001_initial hozir rol.client ni o'zi yaratadi; bu migratsiya faqat ustunsiz yaratilgan eski bazalar uchun.
    # Toza bazada (test, yangi server) ustun allaqachon bor — qayta qo'shilmaydi.
    Rol = apps.get_model("main", "Rol")
    table = Rol._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        columns = [c.name for c in schema_editor.connection.introspection.get_table_description(cursor, table)]
    if "client" not in columns:
        schema_editor.add_field(Rol, Rol._meta.get_field("client"))


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_client_if_missing, migrations.RunPython.noop),
    ]
