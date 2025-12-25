from django.core.management.base import BaseCommand
from main.services.hr_api import fetch_all_employees
from main.services.employee_importer import create_user_and_employee_from_api


class Command(BaseCommand):
    help = "API dan xodimlarni User + Employee qilib import qilish (Organization ishlatilmaydi)"

    def add_arguments(self, parser):
        parser.add_argument(
            "tin",
            nargs="+",
            type=str,
            help="Tashkilot STIR / TIN (faqat API uchun)"
        )

    def handle(self, *args, **options):
        tins = options["tin"]

        for tin in tins:
            self.stdout.write(
                self.style.WARNING(
                    f"\n===== IMPORT: {tin} =====\n"
                )
            )

            employees_data = fetch_all_employees(tin)

            if not employees_data:
                self.stdout.write(self.style.ERROR("❌ Xodim topilmadi"))
                continue

            created = 0
            updated = 0

            for emp in employees_data:
                employee, is_new = create_user_and_employee_from_api(emp)

                if not employee:
                    continue

                if is_new:
                    created += 1
                else:
                    updated += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"✔ Yaratildi: {created} ta | Yangilandi: {updated} ta\n"
                )
            )
