from django.core.management.base import BaseCommand
from django.db import transaction
from main.models import Employee


# Apostrofning barcha unicode ko‘rinishlarini birlashtiramiz
APOSTROPHES = [
    "‘","’","ʼ","`","ʻ","´","ʾ","ʿ","′","Ꞌ","ꞌ",
    "᾽","ʽ","ˈ","ʹ","’","ʼ","’","'", "ʼ"
]


def normalize_apostrophes(text: str) -> str:
    """
    Barcha turdagi apostroflarni yagona `‘` formatiga keltiramiz
    va ortiqcha probellarni normallashtiramiz
    """
    if not text:
        return ""

    for a in APOSTROPHES:
        text = text.replace(a, "‘")

    return " ".join(text.split())


# patronimik so‘zlar
PATRONYMS = [
    "o‘g‘li", "o'g'li",
    "o‘gli", "ogli",
    "qizi"
]


def normalize_patronym(word: str) -> str:
    """
    Patronimiklarni TitleCase formatda qaytaramiz
    (sizning talabangiz bo‘yicha)
    """
    w = normalize_apostrophes(word).lower()

    for p in PATRONYMS:
        if w == normalize_apostrophes(p).lower():
            # TitleCase ko‘rinishga keltiramiz
            return "Qizi" if "q" in w else "O‘g‘li"

    return None


def title_word_apostrophe(word: str) -> str:
    """
    .title() dan keyin:
    — birinchi segment TitleCase
    — ‘ belgisidan keyingi barcha segmentlar doimo kichik
    """

    if not word:
        return ""

    word = normalize_apostrophes(word)

    # bazaviy title format
    t = word.title()

    # apostrof bo‘yicha bo‘lamiz
    parts = t.split("‘")

    fixed = []
    for i, p in enumerate(parts):
        if i == 0:
            fixed.append(p)          # birinchi bo‘lak TitleCase qoladi
        else:
            fixed.append(p.lower())  # keyingi bo‘laklar lower

    return "‘".join(fixed)


def title_word(word: str) -> str:
    """
    — agar patronimik bo‘lsa → TitleCase + apostrof qoidasida
    — aks holda oddiy so‘zga qoida qo‘llanadi
    """

    pat = normalize_patronym(word)
    if pat:
        return title_word_apostrophe(pat)

    return title_word_apostrophe(word)


def format_fio(text: str) -> str:
    """
    FIO tarkibi:
    Familiya  — TitleCase
    Ism       — TitleCase
    Otasining ismi — TitleCase
    Patronimik — TitleCase (lekin ‘ dan keyin lower)
    """

    text = normalize_apostrophes(text)
    parts = text.split()

    return " ".join(
        title_word(p)
        for p in parts
    )


class Command(BaseCommand):
    help = "FIO ni .title() + ‘ belgidan keyin lower qoidasida formatlaydi"

    @transaction.atomic
    def handle(self, *args, **options):

        fixed = 0

        employees = Employee.objects.all().only(
            "id", "last_name", "first_name", "father_name"
        )

        for emp in employees:

            new_last   = format_fio(emp.last_name)
            new_first  = format_fio(emp.first_name)
            new_father = format_fio(emp.father_name or "")

            if (
                new_last   != emp.last_name
                or new_first  != emp.first_name
                or new_father != (emp.father_name or "")
            ):
                Employee.objects.filter(id=emp.id).update(
                    last_name=new_last,
                    first_name=new_first,
                    father_name=new_father
                )
                fixed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✔ {fixed} ta FIO tuzatildi (.title() + apostrof-qoida)"
            )
        )
