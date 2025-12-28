import re
from django.db import transaction
from main.models import Employee
from main.services.fio_split import split_fio


APOSTROPHES = [
    "‘", "’", "ʼ", "`", "ʹ", "ʽ", "ˈ", "´", "ʾ", "ʿ",
    "′", "‵", "Ꞌ", "ꞌ", "꞊", "ʻ", "ˊ", "ˋ", "’"
]


def normalize_fio(text: str) -> str:
    """
    FIO ni yagona formatga keltiramiz:
    - apostroflarni standart `'` ga almashtiramiz
    - ketma-ket probellarni bitta qilamiz
    - Har bir so‘z bosh harf bilan yoziladi
    """

    if not text:
        return ""

    text = text.strip().lower()

    # Apostroflarni bir xil ko‘rinishga keltiramiz
    for a in APOSTROPHES:
        text = text.replace(a, "'")

    # Ikkitalab probel → bitta probel
    text = re.sub(r"\s+", " ", text)

    # Har bir so‘zni bosh harf qilamiz
    text = " ".join(w.capitalize() for w in text.split(" "))

    return text


@transaction.atomic
def attach_pinfl_if_employee_exists(api_emp):
    """
    API dan kelgan FIO + PINFL → bazadagi xodimga biriktiriladi
    """

    full_name = api_emp.get("full_name", "").strip()
    pinfl = api_emp.get("pinfl", "").strip()

    if not full_name or not pinfl:
        return "⚠️ FIO yoki PINFL yo‘q — tashlab ketildi"

    # 1️⃣ Normalizatsiya qilamiz
    fio_normalized = normalize_fio(full_name)

    # 2️⃣ FIO ni last / first / father ga ajratamiz
    last, first, father = split_fio(fio_normalized)

    fio_display = f"{last} {first} {father}".strip()

    # 3️⃣ Bazada aynan mos xodimni qidiramiz
    qs = Employee.objects.filter(
        last_name__iexact=last,
        first_name__iexact=first,
        father_name__iexact=father,
    )

    count = qs.count()

    if count == 0:
        return f"❌ {fio_display} — bazada topilmadi"

    if count > 1:
        return f"⚠️ {fio_display} — bazada {count} ta! PINFL yozilmadi"

    emp = qs.first()

    # 4️⃣ Agar PINFL oldin bor bo‘lsa — o‘zgartirmaymiz
    if emp.pinfl:
        if emp.pinfl == pinfl:
            return f"✔️ {fio_display} — PINFL allaqachon mavjud → {emp.pinfl}"
        else:
            return f"⚠️ {fio_display} — PINFL bor, lekin boshqa! ({emp.pinfl})"

    # 5️⃣ PINFL ni yozamiz
    emp.pinfl = pinfl
    emp.save(update_fields=["pinfl"])

    return f"✅ {fio_display} — PINFL biriktirildi → {pinfl}"
