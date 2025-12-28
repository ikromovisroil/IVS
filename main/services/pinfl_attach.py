from django.db import transaction
from django.db.models.functions import Lower
from main.models import Employee
from main.services.fio_split import split_fio


def normalize(s: str) -> str:
    return (s or "").strip().casefold()


def attach_pinfl_if_employee_exists(api_emp):

    full_name = normalize(api_emp.get("full_name"))
    pinfl = normalize(api_emp.get("pinfl"))

    if not full_name or not pinfl:
        return "⚠️ FIO yoki PINFL yo‘q — tashlab ketildi"

    last, first, father = map(normalize, split_fio(full_name))

    fio = f"{last} {first} {father}".strip()

    qs = (
        Employee.objects
        .annotate(
            last_l=Lower("last_name"),
            first_l=Lower("first_name"),
            father_l=Lower("father_name"),
        )
        .filter(
            last_l=last,
            first_l=first,
            father_l=father,
        )
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
