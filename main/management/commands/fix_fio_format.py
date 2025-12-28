from django.core.management.base import BaseCommand
from django.db import transaction
from main.models import Employee


APOSTROPHES = [
    "‘","’","ʼ","`","ʻ","´","ʾ","ʿ","′","'","’"
]


def smart_capitalize(word: str) -> str:
    """
    Familiya / ism / otasining ismini to‘g‘ri formatlaydi:
    - birinchi harf katta
    - qolganlari kichik
    - apostrofli so‘zlar buzilmaydi
    """

    if not word:
        return ""

    word = word.strip()

    # birinchi harfni katta, qolganini kichik qilamiz
    word = word[0].upper() + word[1:].lower()

    # apostrofdan keyin ham bosh harflarni to‘g‘rilaymiz
    for a in APOSTROPHES:
        if a in word:
            parts = word.split(a)
            word = a.join(
                p[0].upper() + p[1:].lower() if p else ""
                for p in parts
            )

    return word


def format_fio(text: str) -> str:
    """
    FIO ni so‘zma-so‘z tartiblaydi
    """
    if not text:
        return ""

    parts = text.split()

    return " ".join(
        smart_capitalize(p)
        for p in parts
    )


class Command(BaseCommand):
    help = "Bazada FIO formatini to‘g‘rilaydi (Bo'Ronov → Bo'ronov)"

    @transaction.atomic
    def handle(self, *args, **options):

        fixed = 0

        employees = Employee.objects.all().only(
            "id", "last_name", "first_name", "father_name"
        )

        for emp in employees:

            new_last = format_fio(emp.last_name)
            new_first = format_fio(emp.first_name)
            new_father = format_fio(emp.father_name or "")

            if (
                new_last != emp.last_name
                or new_first != emp.first_name
                or new_father != (emp.father_name or "")
            ):
                Employee.objects.filter(id=emp.id).update(
                    last_name=new_last,
                    first_name=new_first,
                    father_name=new_father
                )

                fixed += 1

        self.stdout.write(self.style.SUCCESS(
            f"✔ {fixed} ta xodimning FIO si to‘g‘rilandi"
        ))
