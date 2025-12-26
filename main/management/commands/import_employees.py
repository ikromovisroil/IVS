import openpyxl
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from main.models import Employee, Region, Rank


# ============================
# USERNAME NORMALIZATOR
# ============================
def normalize_username(value):
    value = value.lower()

    # Apostroflarni bir xil ko‘rinishga keltirish
    value = (
        value.replace("’", "'")
             .replace("‘", "'")
             .replace("`", "'")
             .replace("ʼ", "'")
    )

    # o‘ / g‘ belgilarini tozalaymiz
    value = value.replace("o'", "o").replace("o‘", "o")
    value = value.replace("g'", "g").replace("g‘", "g")

    # Bo‘sh joylarni olib tashlaymiz
    value = value.replace(" ", "")

    return value


class Command(BaseCommand):
    help = "Excel fayldan User + Employee yaratish"

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str)

    def handle(self, *args, **options):

        wb = openpyxl.load_workbook(options["file_path"])
        ws = wb.active

        created = 0
        skipped = 0

        # Default region
        region, _ = Region.objects.get_or_create(name="Toshkent")

        for row in ws.iter_rows(min_row=2, values_only=True):

            position = row[0]   # Lavozim
            full_name = row[1]  # FIO

            if not full_name:
                skipped += 1
                continue

            parts = (full_name or "").split()

            last_name = parts[0].title() if len(parts) > 0 else ""
            first_name = parts[1].title() if len(parts) > 1 else ""
            father_name = " ".join(parts[2:]) if len(parts) > 2 else ""

            # ============================
            # USERNAME GENERATOR
            # ============================
            raw_username = f"{last_name}.{first_name}"
            username = normalize_username(raw_username)

            # Dublikat username bo‘lsa — raqam qo‘shamiz
            base_username = username
            i = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{i}"
                i += 1

            # 👤 USER yaratamiz
            user = User.objects.create_user(
                username=username,
                password="Password100",
            )

            # 🎖 Lavozim bo‘lsa — Rank topamiz
            rank = None
            if position:
                rank = Rank.objects.filter(name__iexact=position).first()

            # ============================
            # EMPLOYEE (signal yaratganini yangilaymiz)
            # ============================
            employee, _ = Employee.objects.get_or_create(
                user=user,
                defaults={
                    "last_name": last_name,
                    "first_name": first_name,
                    "father_name": father_name,
                    "region": region,
                    "rank": rank,
                    "status": "worker",
                }
            )

            employee.last_name = last_name
            employee.first_name = first_name
            employee.father_name = father_name
            employee.region = region
            employee.rank = rank
            employee.status = "worker"
            employee.save()

            created += 1
            print(employee)

        self.stdout.write(self.style.SUCCESS(
            f"✔ Yaratildi / yangilandi: {created} | ⛔ O'tkazib yuborildi: {skipped}"
        ))
