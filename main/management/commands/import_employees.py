import openpyxl
from django.core.management.base import BaseCommand

from main.models import Employee, Department, Directorate, Division


# ==========================
# 🔧 NOM NORMALIZATOR
# ==========================
def normalize_name(v: str):
    return (
        str(v)
        .strip()
        .lower()
        .replace("’", "'")
        .replace("`", "'")
        .replace("ʻ", "'")
        .replace("‘", "'")
        .replace("o'", "o‘")
        .replace("g'", "g‘")
        .replace("ў", "o‘")
        .replace("ғ", "g‘")
    )


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

            position = row[0]   # foydali bo‘lishi mumkin
            full_name = row[1]  # xodim
            structure_name = row[2]  # bo‘lim

            if not full_name or not structure_name:
                continue

            # ==========================
            # 👤 FIO → last / first / father
            # ==========================
            fio = str(full_name).split()

            last = fio[0].title() if len(fio) > 0 else ""
            first = fio[1].title() if len(fio) > 1 else ""
            father = fio[2].title() if len(fio) > 2 else ""

            norm_struct = normalize_name(structure_name)

            # ==========================
            # 🔎 Xodimni topamiz
            # ==========================
            employee = Employee.objects.filter(
                last_name__iexact=last,
                first_name__iexact=first,
            ).first()

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

            # ==========================
            # 🟡 MOSLASHUVCHAN BO‘LIM QIDIRUV
            # ==========================
            dept = direc = div = None

            # 1️⃣ Department — aniq moslik
            for d in Department.objects.all():
                if normalize_name(d.name) == norm_struct:
                    dept = d
                    break

            # 2️⃣ Directorate
            if not dept:
                for d in Directorate.objects.all():
                    if normalize_name(d.name) == norm_struct:
                        direc = d
                        break

            # 3️⃣ Division
            if not dept and not direc:
                for d in Division.objects.all():
                    if normalize_name(d.name) == norm_struct:
                        div = d
                        break

            # 4️⃣ Qisman moslik (fallback)
            if not dept and not direc and not div:
                dept = Department.objects.filter(name__icontains=structure_name[:6]).first()

            if not dept and not direc and not div:
                self.stdout.write(self.style.WARNING(
                    f"⚠ Bo‘lim topilmadi → '{structure_name}'"
                ))
                not_matched += 1
                continue

            # ==========================
            # 🔗 ZANJIR BILAN BIRIKTIRAMIZ
            # ==========================
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

        # ==========================
        # 📊 NATIJA
        # ==========================
        self.stdout.write("\n=========== NATIJA ===========")
        self.stdout.write(self.style.SUCCESS(f"✔ Yangilandi: {updated}"))
        self.stdout.write(self.style.WARNING(f"🟥 Xodim topilmadi: {not_found}"))
        self.stdout.write(self.style.WARNING(f"⚠ Bo‘lim mos kelmadi: {not_matched}"))
