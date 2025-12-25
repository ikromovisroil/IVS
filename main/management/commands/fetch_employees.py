from django.core.management.base import BaseCommand
from main.services.hr_api import fetch_all_employees


class Command(BaseCommand):
    help = "Bir yoki bir nechta STIR bo‘yicha xodimlarni lotincha chiqarish"

    def add_arguments(self, parser):
        parser.add_argument(
            "tin",
            nargs="+",
            type=str,
            help="Tashkilot STIR / TIN (bir nechta kiritish mumkin)"
        )

    def handle(self, *args, **options):
        tins = options["tin"]

        for tin in tins:
            self.stdout.write(
                self.style.WARNING(
                    f"\n==============================\n"
                    f"  TASHKILOT STIR / TIN : {tin}\n"
                    f"==============================\n"
                )
            )

            employees = fetch_all_employees(tin)

            if not employees:
                self.stdout.write(
                    self.style.ERROR("❌ Xodimlar topilmadi yoki API javob bermadi")
                )
                continue

            self.stdout.write(
                self.style.SUCCESS(
                    f"🔥 Jami yuklandi: {len(employees)} ta xodim\n"
                )
            )

            for i, emp in enumerate(employees, start=1):
                print(employees)
                print(
                    f"{i}) "
                    f"{emp.get('full_name','-')} | "
                    f"{emp.get('position','-')} | "
                    f"{emp.get('department','-')} | "
                    f"PINFL: {emp.get('pinfl','-')}"
                )
