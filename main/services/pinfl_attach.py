import re
from django.db import transaction
from django.db.models import Q

from main.models import Employee
from main.services.fio_split import split_fio


# Apostroflarni yagona ko‘rinishga keltirish uchun belgi ro‘yxati
APOSTROPHES = [
    "‘","’","ʼ","`","ʹ","ʽ","ˈ","´","ʾ","ʿ",
    "′","‵","Ꞌ","ꞌ","꞊","ʻ","ˊ","ˋ"
]


@transaction.atomic
def attach_pinfl_if_employee_exists(api_emp):
    """
    API dan kelgan FIO + PINFL → bazadagi xodimga biriktiriladi

    Kutilgan API format:
        {
            "full_name": "Familiya Ism Otasining ismi",
            "pinfl": "12345678901234"
        }
    """

    full_name = (api_emp.get("full_name") or "").strip()
    pinfl = (api_emp.get("pinfl") or "").strip()

    if not full_name or not pinfl:
        return "⚠️ FIO yoki PINFL yo‘q — tashlab ketildi"


    # 2️⃣ FIO ni (last, first, father) ga ajratamiz
    last, first, father = split_fio(full_name)
    print(last, first, father)

    fio_display = f"{last} {first} {father}".strip()


    # 3️⃣ To‘liq mos FIO bo‘yicha qidiramiz
    qs = Employee.objects.filter(
        last_name__iexact=last,
        first_name__iexact=first,
        father_name__iexact=father
    )


    # 4️⃣ Agar father_name yo‘q bo‘lsa — shunchaki 2 qism bilan qidiramiz
    if qs.count() == 0 and not father:
        qs = Employee.objects.filter(
            last_name__iexact=last,
            first_name__iexact=first,
        )


    # 5️⃣ Bazada father_name bo‘sh bo‘lsa ham mos qilib qidiramiz
    if qs.count() == 0:
        qs = Employee.objects.filter(
            Q(last_name__iexact=last) &
            Q(first_name__iexact=first) &
            (
                Q(father_name__iexact=father) |
                Q(father_name__isnull=True) |
                Q(father_name__exact="")
            )
        )


    count = qs.count()


    # 6️⃣ Hech kim topilmadi
    if count == 0:
        return f"❌ {fio_display} — bazada topilmadi"


    # 7️⃣ Bir nechta xodim chiqsa — xavfsizlik uchun yozmaymiz
    if count > 1:
        return f"⚠️ {fio_display} — bazada {count} ta! PINFL yozilmadi"


    emp = qs.first()


    # 8️⃣ Agar PINFL oldindan mavjud bo‘lsa — o‘zgartirmaymiz
    if emp.pinfl:
        if emp.pinfl == pinfl:
            return f"✔️ {fio_display} — PINFL allaqachon mavjud → {emp.pinfl}"
        else:
            return f"⚠️ {fio_display} — PINFL bor, lekin boshqa! ({emp.pinfl})"


    # 9️⃣ PINFL ni yozamiz
    emp.pinfl = pinfl
    emp.save(update_fields=["pinfl"])

    return f"✅ {fio_display} — PINFL biriktirildi → {pinfl}"
