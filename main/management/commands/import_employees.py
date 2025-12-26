import openpyxl
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from main.models import (
    Employee,
    Department,
    Directorate,
    Division,
    Rank,
    Region,
)


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

        # ⚙️ Default Region (agar yo‘q bo‘lsa yaratiladi)
        region, _ = Region.objects.get_or_create(name="Toshkent")

        for row in ws.iter_rows(min_row=2, values_only=True):

            position = row[0]     # Lavozim
            full_name = row[1]    # F.I.Sh
            dep_name = row[2]     # Tuzilma nomi

            if not full_name:
                skipped += 1
                continue

            # 1️⃣ F.I.Sh ni ajratamiz
            parts = (full_name or "").split()

            last_name = parts[0].lower() if len(parts) > 0 else ""
            first_name = parts[1].lower() if len(parts) > 1 else ""
            father_name = " ".join(parts[2:]) if len(parts) > 2 else ""

            full_name_print = " ".join(p for p in [
                last_name.title(),
                first_name.title(),
                father_name
            ] if p)

            # 2️⃣ Tuzilmani aniqlaymiz
            division = None
            directorate = None
            department = None

            if dep_name:

                # — Division —
                division = Division.objects.filter(name__iexact=dep_name).first()

                if division:
                    directorate = division.directorate
                    department = directorate.department if directorate else None

                else:
                    # — Directorate —
                    directorate = Directorate.objects.filter(name__iexact=dep_name).first()

                    if directorate:
                        department = directorate.department

                    else:
                        # — Department —
                        department = Department.objects.filter(name__iexact=dep_name).first()

            if not (division or directorate or department):
                self.stdout.write(self.style.ERROR(
                    f"❗ {full_name_print} — Tuzilma topilmadi | Dep: {dep_name}"
                ))
                skipped += 1
                continue

            # 3️⃣ Lavozim (bor bo‘lsa ulaymiz)
            rank = None
            if position:
                rank = Rank.objects.filter(name__iexact=position).first()

            # 4️⃣ Username generatsiya
            base_username = f"{last_name}.{first_name}".replace(" ", "")
            username = base_username or last_name

            u = username
            i = 1
            while User.objects.filter(username=u).exists():
                u = f"{username}{i}"
                i += 1

            username = u

            # 5️⃣ USER mavjudligini tekshiramiz
            user = User.objects.filter(username=username).first()

            employee = None

            # 6️⃣ Agar user bor bo‘lsa — unga bog‘langan employee ni olamiz
            if user:
                employee = Employee.objects.filter(user=user).first()

            # 7️⃣ Agar employee topilmasa — FIO bo‘yicha qidiramiz
            if not employee:
                employee = Employee.objects.filter(
                    last_name__iexact=last_name,
                    first_name__iexact=first_name,
                    father_name__iexact=father_name,
                ).first()

            # =========================
            # 8️⃣ XODIM BOR → FAQAT YANGILAYMIZ
            # =========================
            if employee:

                old_dep = (
                    employee.department.name
                    if employee.department else
                    employee.directorate.name if employee.directorate else
                    employee.division.name if employee.division else "-"
                )

                employee.division = division
                employee.directorate = directorate
                employee.department = department

                employee.region = region
                employee.rank = rank
                employee.status = "worker"

                employee.save()   # ⬅️ organization avtomatik to‘ldiriladi

                self.stdout.write(self.style.SUCCESS(
                    f"♻ Yangilandi: {full_name_print} | {old_dep} → {dep_name}"
                ))

                updated += 1
                continue

            # =========================
            # 9️⃣ USER YO‘Q → YANGI USER YARATAMIZ
            # =========================
            if not user:
                user = User.objects.create_user(
                    username=username,
                    password="Password100"
                )

            # =========================
            # 🔟 YANGI EMPLOYEE YARATAMIZ
            # =========================
            employee = Employee.objects.create(
                user=user,
                last_name=last_name.title(),
                first_name=first_name.title(),
                father_name=father_name,

                division=division,
                directorate=directorate,
                department=department,

                region=region,
                rank=rank,
                status="worker",
            )

            employee.save()   # ⬅️ Employee.save() zanjiri ishlaydi

            self.stdout.write(self.style.SUCCESS(
                f"➕ Yaratildi: {full_name_print} | Dep: {dep_name}"
            ))

            created += 1

        # =========================
        # 🔚 Yakuniy hisobot
        # =========================
        self.stdout.write(self.style.SUCCESS(
            f"\nYaratildi: {created} | Yangilandi: {updated} | SKIP: {skipped}"
        ))
