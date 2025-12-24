import os
import openpyxl
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.conf import settings

from main.models import (
    Organization, Department, Directorate, Division,
    Employee, Rank
)

from openpyxl.styles.colors import COLOR_INDEX

def get_color_type(self, cell):
    """
    Excel rangini aniqlaydi:
    RGB, THEME, va INDEXED ranglarni to‘g‘ri o‘qiydi.
    """

    fill = cell.fill

    # Hech qanday fill bo‘lmasa — oddiy xodim
    if fill is None or fill.start_color is None:
        return "employee"

    color_obj = fill.start_color
    color = None

    # 1️⃣ RGB rang
    if color_obj.type == "rgb":
        color = color_obj.rgb

    # 2️⃣ THEME rang → theme + tint asosida Excel palitrasidan hisoblaymiz
    elif color_obj.type == "theme":
        try:
            theme_color = cell.parent.parent.theme.theme_elements.clrScheme
            clr = theme_color[color_obj.theme]
            if clr.srgbClr is not None:
                color = clr.srgbClr.val
            elif clr.sysClr is not None:
                color = clr.sysClr.lastClr
        except:
            pass

    # 3️⃣ INDEXED rang
    elif color_obj.type == "indexed":
        idx = int(color_obj.indexed)
        if idx in COLOR_INDEX:
            color = COLOR_INDEX[idx]

    if not color:
        return "employee"

    color = color[-6:].upper()

    # Ranglarni solishtiramiz
    if color == "FFFF00":
        return "department"      # SARIQ
    if color == "E6F0DA":
        return "directorate"     # YASHIL
    if color == "D9E1F2":
        return "division"        # KO‘K

    return "employee"


class Command(BaseCommand):
    help = "IMV struktura va xodimlarni rang bo‘yicha import qiladi."

    # ======================================================
    #   RANGNI ANIQLASH
    # ======================================================
    def get_color_type(self, cell):
        """
        Rang kodi bo‘yicha turini qaytaradi.
        """
        color_obj = cell.fill.start_color

        color = None
        if getattr(color_obj, "type", None) == "rgb":
            color = color_obj.rgb
        if isinstance(color_obj, str):
            color = color_obj

        if not color:
            return "employee"

        if len(color) == 8:  # ARGB → RGB
            color = color[-6:]

        color = color.upper()

        if color == "FFFF00":
            return "department"      # SARIQ
        if color == "E6F0DA":
            return "directorate"     # YASHIL
        if color == "D9E1F2":
            return "division"        # KO‘K

        return "employee"

    # ======================================================
    #   ASOSIY IMPORT
    # ======================================================
    def handle(self, *args, **kwargs):

        file_path = os.path.join(settings.BASE_DIR, "import", "Книга1.xlsx")

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR("❌ Excel topilmadi."))
            return

        wb = openpyxl.load_workbook(file_path)
        sheet = wb.active

        DEFAULT_PASSWORD = "Password100"

        # IMV tashkilotini olamiz
        organization, _ = Organization.objects.get_or_create(
            name="IMV",
            defaults={"org_type": "IMV"}
        )

        current_department = None
        current_directorate = None
        current_division = None

        for row in sheet.iter_rows(values_only=False):

            cell = row[0]
            text = str(cell.value).strip() if cell.value else None
            if not text:
                continue

            kind = self.get_color_type(cell)

            # ============================================
            # 🟡 DEPARTMENT (IMV ga bog‘lanadi)
            # ============================================
            if kind == "department":
                current_department, created = Department.objects.get_or_create(
                    name=text,
                    defaults={"organization": organization}
                )

                # 1-o‘rinda IMV ga bog‘langan bo‘lishi kerak
                if current_department.organization != organization:
                    current_department.organization = organization
                    current_department.save()

                current_directorate = None
                current_division = None

                self.stdout.write(self.style.SUCCESS(
                    f"🟡 Department: {text} ({'yangi' if created else 'mavjud'})"
                ))
                continue

            # ============================================
            # 🟩 DIRECTORATE (faqat shu Departmentga tegishli)
            # ============================================
            if kind == "directorate":
                current_directorate, created = Directorate.objects.get_or_create(
                    name=text,
                    defaults={"department": current_department}
                )

                # To‘g‘ri parent departamentga bog‘liq bo‘lishi shart
                if current_directorate.department != current_department:
                    current_directorate.department = current_department
                    current_directorate.save()

                current_division = None

                self.stdout.write(self.style.SUCCESS(
                    f"🟩 Directorate: {text} ({'yangi' if created else 'mavjud'})"
                ))
                continue

            # ============================================
            # 🔵 DIVISION (faqat shu Directoratega tegishli)
            # ============================================
            if kind == "division":
                current_division, created = Division.objects.get_or_create(
                    name=text,
                    defaults={"directorate": current_directorate}
                )

                # To‘g‘ri directoratega bog‘lash
                if current_division.directorate != current_directorate:
                    current_division.directorate = current_directorate
                    current_division.save()

                self.stdout.write(self.style.SUCCESS(
                    f"🔵 Division: {text} ({'yangi' if created else 'mavjud'})"
                ))
                continue

            # ============================================
            # 👤 EMPLOYEE (lavozim | FIO)
            # ============================================
            position = text
            fio_cell = row[1] if len(row) > 1 else None
            fio = fio_cell.value.strip() if fio_cell and fio_cell.value else None

            if not fio:
                continue

            parts = fio.split()
            if len(parts) < 3:
                self.stdout.write(self.style.ERROR(f"❌ Noto‘g‘ri FIO: {fio}"))
                continue

            fam, ism = parts[0], parts[1]
            otasi = " ".join(parts[2:])

            lastname = f"{fam} {ism}"
            firstname = otasi

            username_base = f"{fam}.{ism}".lower()
            username = username_base

            rank, _ = Rank.objects.get_or_create(name=position)

            # ---------- Agar user allaqachon mavjud bo‘lsa → yangilanadi ----------
            user = User.objects.filter(first_name=firstname, last_name=lastname).first()

            if not user:
                # username kolliziyasini oldini olamiz
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{username_base}{counter}"
                    counter += 1

                user = User.objects.create_user(
                    username=username,
                    first_name=firstname,
                    last_name=lastname,
                    password=DEFAULT_PASSWORD
                )
                self.stdout.write(self.style.SUCCESS(f"🆕 Xodim yaratildi: {fio}"))
            else:
                self.stdout.write(self.style.WARNING(f"♻ Xodim yangilanmoqda: {fio}"))

            # ---------- Employee obyektini yangilaymiz ----------
            emp = user.employee

            emp.rank = rank
            emp.status = "worker"
            emp.organization = organization
            emp.department = current_department
            emp.directorate = current_directorate
            emp.division = current_division
            emp.save()

            self.stdout.write(self.style.SUCCESS(f"👤 Saqlandi: {fio}"))
