from django.db import transaction
from main.models import Employee
from main.services.fio_split import split_fio


def attach_pinfl_if_employee_exists(api_emp):

    full_name = api_emp.get("full_name", "").strip()
    pinfl = api_emp.get("pinfl", "").strip()

    if not full_name or not pinfl:
        return "⚠️ FIO yoki PINFL yo‘q — tashlab ketildi"

    last, first, father = split_fio(full_name)

    fio = f"{last} {first} {father}".strip()

    qs = Employee.objects.filter(
        last_name__iexact=last,
        first_name__iexact=first,
        father_name__iexact=father,
    )

    count = qs.count()

    if count == 0:
        return f"❌ {fio} — bazada topilmadi"

    if count > 1:
        return f"⚠️ {fio} — bazada {count} ta! PINFL yozilmadi"

    emp = qs.first()

    if emp.pinfl:
        return f"✔️ {fio} — PINFL allaqachon bor"

    with transaction.atomic():
        emp.pinfl = pinfl
        emp.save(update_fields=["pinfl"])

    return f"✅ {fio} — PINFL biriktirildi → {pinfl}"
