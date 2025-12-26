import openpyxl
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils.text import slugify

from main.models import (
    Employee,
    Organization,
    Department,
    Directorate,
    Division,
    Rank,
    Region,
)


def make_slug(last_name, first_name, father_name):
    parts = [last_name, first_name, father_name]
    slug_text = "_".join([p for p in parts if p]).strip("_")
    return slugify(slug_text).replace("-", "_")


class Command(BaseCommand):
    help = "Excel fayldan xodimlarni import qilish"

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str)

    def handle(self, *args, **options):

        wb = openpyxl.load_workbook(options["file_path"])
        ws = wb.active

        created = 0
        updated = 0
        skipped = 0

        # ⚙️ Default region = Toshkent
        region, _ = Region.objects.get_or_create(name="Toshkent")

        for row in ws.iter_rows(min_row=2, values_only=True):

            position = row[0]     # Lavozim
            full_name = row[1]    # F.I.Sh
            dep_name = row[2]     # Tuzilma nomi

            if not full_name:
                skipped += 1
                continue

            # 1️⃣ FIO ajratamiz
            parts = (full_name or "").split()

            last_name = parts[0].lower() if len(parts) > 0 else ""
            first_name = parts[1].lower() if len(parts) > 1 else ""
            father_name = " ".join(parts[2:]) if len(parts) > 2 else ""

            full_name_print = f"{last_name.title()} {first_name.title()} {father_name}".strip()

            # 2️⃣ Tuzilmani aniqlaymiz
            division = None
            directorate = None
            department = None
            organization = None

            if dep_name:

                # 1 — Division bo‘yicha
                division = Division.objects.filter(name__iexact=dep_name).first()

                if division:
                    directorate = division.directorate
                    department = directorate.department if directorate else None
                    organization = department.organization if department else None

                else:
                    # 2 — Directorate
                    directorate = Directorate.objects.filter(name__iexact=dep_name).first()

                    if directorate:
                        department = directorate.department
                        organization = department.organization if department else None

                    else:
                        # 3 — Department
                        department = Department.objects.filter(name__iexact=dep_name).first()

                        if department:
                            organization = department.organization

            if not (division or directorate or department):
                self.stdout.write(self.style.ERROR(
                    f"❗ {full_name_print} — Tuzilma topilmadi | Dep: {dep_name}"
                ))
                skipped += 1
                continue

            # 3️⃣ Lavozim mavjud bo‘lsa — bog‘laymiz
            rank = None
            if position:
                rank = Rank.objects.filter(name__iexact=position).first()

            # 4️⃣ Avval mavjud xodimni FIO bo‘yicha tekshiramiz
            employee = Employee.objects.filter(
                last_name__iexact=last_name,
                first_name__iexact=first_name,
                father_name__iexact=father_name,
            ).first()

            # =========================
            # 5️⃣ XODIM BOR — TAHRIRLAYMIZ
            # =========================
            if employee:

                old_dep = employee.department.name if employee.department else "-"

                employee.organization = organization
                employee.department = department
                employee.directorate = directorate
                employee.division = division
                employee.region = region
                employee.rank = rank
                employee.status = "worker"

                employee.slug = make_slug(last_name, first_name, father_name)

                employee.save()

                self.stdout.write(self.style.SUCCESS(
                    f"♻ Yangilandi: {full_name_print} | {old_dep} → {dep_name}"
                ))

                updated += 1
                continue

            # =========================
            # 6️⃣ XODIM YO‘Q — USER YARATAMIZ
            # =========================

            base_username = f"{last_name}.{first_name}".lower().replace(" ", "")
            username = base_username

            i = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{i}"
                i += 1

            user = User.objects.create_user(
                username=username,
                password="Password100"
            )

            # =========================
            # 7️⃣ YANGI EMPLOYEE YARATAMIZ
            # =========================
            employee = Employee.objects.create(
                user=user,
                last_name=last_name.title(),
                first_name=first_name.title(),
                father_name=father_name,

                organization=organization,
                department=department,
                directorate=directorate,
                division=division,

                region=region,
                rank=rank,
                status="worker",

                slug=make_slug(last_name, first_name, father_name),
            )

            self.stdout.write(self.style.SUCCESS(
                f"➕ Yaratildi: {full_name_print} | Dep: {dep_name}"
            ))

            created += 1

        # =========================
        # 8️⃣ Yakuniy natija
        # =========================
        self.stdout.write(self.style.SUCCESS(
            f"\nYaratildi: {created} | Yangilandi: {updated} | SKIP: {skipped}"
        ))
