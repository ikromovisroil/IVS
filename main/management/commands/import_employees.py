import openpyxl
from django.core.management.base import BaseCommand

from main.models import Employee, Department, Directorate, Division


class Command(BaseCommand):
    help = "Exceldan xodimlarni FIO bo‘yicha topib bo‘limga biriktirish"

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str)

    def handle(self, *args, **options):

        wb = openpyxl.load_workbook(options["file_path"])
        ws = wb.active

        updated = 0
        not_found = 0
        not_matched = 0

        for row in ws.iter_rows(min_row=2, values_only=True):

            position = row[0]
            full_name = row[1]
            structure_name = row[2]

            if not full_name or not structure_name:
                continue

            # Normalize FIO
            parts = full_name.split()

            last = parts[0].title() if len(parts) > 0 else ""
            first = parts[1].title() if len(parts) > 1 else ""
            father = parts[2].title() if len(parts) > 2 else ""

            structure_name = structure_name.strip()

            # 🔎 Xodimni topamiz
            employee = Employee.objects.filter(
                last_name__iexact=last,
                first_name__iexact=first,
            ).first()

            # Agar otasining ismi ham bo‘lsa → qo‘shimcha tekshiramiz
            if not employee and father:
                employee = Employee.objects.filter(
                    last_name__iexact=last,
                    first_name__iexact=first,
                    father_name__iexact=father,
                ).first()

            if not employee:
                self.stdout.write(self.style.WARNING(
                    f"🟥 Xodim topilmadi → {full_name}"
                ))
                not_found += 1
                continue

            dept = direc = div = None

            # 1️⃣ Department
            dept = Department.objects.filter(
                name__iexact=structure_name
            ).first()

            # 2️⃣ Directorate
            if not dept:
                direc = Directorate.objects.filter(
                    name__iexact=structure_name
                ).first()

            # 3️⃣ Division
            if not dept and not direc:
                div = Division.objects.filter(
                    name__iexact=structure_name
                ).first()

            if not dept and not direc and not div:
                self.stdout.write(self.style.WARNING(
                    f"⚠ Bo‘lim topilmadi → {structure_name}"
                ))
                not_matched += 1
                continue

            # 🔗 ZANJIR BILAN BIRIKTIRAMIZ
            if div:
                employee.division = div
                employee.directorate = div.directorate
                employee.department = div.directorate.department
                employee.organization = div.directorate.department.organization
                result = f"Division → {div.name}"

            elif direc:
                employee.directorate = direc
                employee.department = direc.department
                employee.organization = direc.department.organization
                result = f"Directorate → {direc.name}"

            elif dept:
                employee.department = dept
                employee.organization = dept.organization
                result = f"Department → {dept.name}"

            employee.save()

            updated += 1

            self.stdout.write(self.style.SUCCESS(
                f"🟢 {last} {first}  ⇒  {result}"
            ))

        self.stdout.write("\n=========== NATIJA ===========")
        self.stdout.write(self.style.SUCCESS(f"✔ Yangilandi: {updated}"))
        self.stdout.write(self.style.WARNING(f"🟥 Xodim topilmadi: {not_found}"))
        self.stdout.write(self.style.WARNING(f"⚠ Mos kelmagan bo‘lim: {not_matched}"))
