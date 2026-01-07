import openpyxl
from django.core.management.base import BaseCommand
from django.db import IntegrityError

from main.models import Material


class Command(BaseCommand):
    help = "Excel fayldan Material bazaga import qilish (FAQAT YARATADI)"

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str)

    def handle(self, *args, **options):

        wb = openpyxl.load_workbook(options["file_path"])
        ws = wb.active

        created = 0
        skipped = 0
        errors = 0

        for row in ws.iter_rows(min_row=2, values_only=True):

            # Excel ustunlari:
            # A - nomi
            # B - o'lchov birligi
            # C - narx
            # D - kod
            # E - soni
            name = row[0]
            unit = row[1]
            price = row[2]
            code = row[3]
            number = row[4]

            # Nomi bo'sh bo'lsa tashlab ketamiz
            if not name:
                skipped += 1
                continue

            price = price or 0
            number = number or 0

            try:
                Material.objects.create(
                    name=str(name).strip(),
                    unit=unit,
                    price=price,
                    code=code,
                    number=number,
                )
                created += 1

            except IntegrityError:
                # Masalan, name yoki code unique bo'lsa va dublikat chiqsa
                errors += 1
                continue

        self.stdout.write(self.style.SUCCESS(
            f"Yaratildi: {created} | Bo'sh nom bilan tashlab ketildi: {skipped} | Xatolik (dublikat yoki boshqa): {errors}"
        ))
