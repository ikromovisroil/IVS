from django.contrib.auth.models import User
from main.models import (
    Employee,
    Department,
    Directorate,
    Division,
)
from main.services.translit import cyr_to_lat


def split_name(full_name: str):
    parts = (full_name or "").split()

    last = parts[0] if len(parts) > 0 else ""
    first = parts[1] if len(parts) > 1 else ""
    father = " ".join(parts[2:]) if len(parts) > 2 else ""

    return last, first, father


def match_structure_by_department_text(dept_text: str):
    """
    Strukturani faqat mavjudlariga bog‘laymiz.
    Yangi department / directorate / division yaratmaymiz.
    """
    if not dept_text:
        return None, None, None

    # 1️⃣ Division bo‘yicha qidirish
    division = (
        Division.objects
        .filter(name__iexact=dept_text)
        .select_related("directorate__department")
        .first()
    )
    if division:
        return (
            division.directorate.department,
            division.directorate,
            division,
        )

    # 2️⃣ Directorate bo‘yicha qidirish
    directorate = (
        Directorate.objects
        .filter(name__iexact=dept_text)
        .select_related("department")
        .first()
    )
    if directorate:
        return (directorate.department, directorate, None)

    # 3️⃣ Department bo‘yicha qidirish
    department = Department.objects.filter(name__iexact=dept_text).first()
    if department:
        return (department, None, None)

    # ❌ Topilmadi → hech narsa bog‘lamaymiz
    return None, None, None


from django.contrib.auth.models import User
from main.models import Employee, Department, Directorate, Division
from main.services.translit import cyr_to_lat


def create_user_and_employee_from_api(emp: dict):
    full_name = cyr_to_lat(emp.get("full_name", ""))
    dept_text = cyr_to_lat(emp.get("department", ""))
    pinfl = emp.get("pinfl")

    if not pinfl:
        return None, False

    # -------- ism familiya ajratish --------
    parts = full_name.split()
    last_name = parts[0] if len(parts) > 0 else ""
    first_name = parts[1] if len(parts) > 1 else ""
    father_name = " ".join(parts[2:]) if len(parts) > 2 else ""

    username = f"{first_name}.{last_name}".lower().replace(" ", "")

    # -------- USER --------
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "is_active": True,
        }
    )

    # parol faqat yangi yaratilganda
    if not user.has_usable_password():
        user.set_password("Password100")
        user.save()

    # -------- AVVAL PINFL BO‘YICHA QIDIRAMIZ --------
    employee = Employee.objects.filter(pinfl=pinfl).first()

    # -------- AKS HOLDA USER BO‘YICHA QIDIRAMIZ --------
    if not employee:
        employee = Employee.objects.filter(user=user).first()

    # -------- TUZILMANI TOPISH (agar mos bo‘lsa) --------
    department = Department.objects.filter(name__iexact=dept_text).first()
    directorate = Directorate.objects.filter(name__iexact=dept_text).first()
    division = Division.objects.filter(name__iexact=dept_text).first()

    # -------- AGAR BOR BO‘LSA — YANGILAYMIZ --------
    if employee:
        employee.user = user
        employee.first_name = first_name
        employee.last_name = last_name
        employee.father_name = father_name
        employee.status = "worker"

        if department:
            employee.department = department
        if directorate:
            employee.directorate = directorate
        if division:
            employee.division = division

        employee.save()
        return employee, False

    # -------- YO‘Q BO‘LSA — YANGI YARATAMIZ --------
    employee = Employee.objects.create(
        user=user,
        pinfl=pinfl,
        first_name=first_name,
        last_name=last_name,
        father_name=father_name,
        status="worker",
        department=department,
        directorate=directorate,
        division=division,
    )

    return employee, True

