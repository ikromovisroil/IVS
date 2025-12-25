from django.core.management.base import BaseCommand
from django.db import transaction
import openpyxl

from main.models import (
    Employee,
    Department,
    Directorate,
    Division,
    Rank
)


def split_fio(fio):
    fio = fio.strip()
    parts = fio.split()

    last_name  = parts[0] if len(parts) > 0 else ""
    first_name = parts[1] if len(parts) > 1 else ""
    father_name = " ".join(parts[2:]) if len(parts) > 2 else ""

    return last_name, first_name, father_name


def find_structure(name):

    if not name:
        return None, None, None

    name = name.strip()

    # Department
    department = Department.objects.filter(name__iexact=name).first()
    if department:
        return department, None, None

    # Directorate
    directorate = Directorate.objects.filter(name__iexact=name).first()
    if directorate:
        return directorate.department, directorate, None

    # Division
    division = Division.objects.filter(name__iexact=name).first()
    if division:
        return (
            division.directorate.department if division.directorate else None,
            division.directorate,
            division,
        )

    # topilmasa → yangi Department ochiladi
    department = Department.objects.create(name=name)
    return department, None, None



@transaction.atomic
def import_from_excel(path):

    wb = openpyxl.load_workbook(path)
    ws = wb.active

    created = 0

    """
    Excel ustunlari tartibi:

    1 — Lavozim (Rank)
    2 — F.I.Sh
    3 — Bo‘lim
    """

    for rank_name, fio, bolim_name in ws.iter_rows(min_row=2, values_only=True):

        if not fio:
            continue

        last_name, first_name, father_name = split_fio(fio)

        department, directorate, division = find_structure(bolim_name)

        # Rank (lavozim)
        rank = None
        if rank_name:
            rank_name = rank_name.strip()
            rank, _ = Rank.objects.get_or_create(
                name__iexact=rank_name,
                defaults={"name": rank_name},
            )

        # 🆕 Har doim yangi xodim yaratamiz
        Employee.objects.create(
            last_name=last_name,
            first_name=first_name,
            father_name=father_name,
            department=department,
            directorate=directorate,
            division=division,
            rank=rank,
        )

        created += 1

    return created



class Command(BaseCommand):
    help = "Excel fayldan xodimlarni yaratadi (faqat create, update yo‘q)"

    def add_arguments(self, parser):
        parser.add_argument("file", type=str)

    def handle(self, *args, **options):

        path = options["file"]

        self.stdout.write(self.style.NOTICE(f"📥 Import boshlandi: {path}"))

        created = import_from_excel(path)

        self.stdout.write(self.style.SUCCESS(f"🆕 Yaratildi: {created} ta xodim"))
        self.stdout.write(self.style.SUCCESS("✅ Import yakunlandi"))
