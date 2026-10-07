from datetime import datetime, time
from io import BytesIO
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.http import require_GET
from django.utils.dateparse import parse_date
from django.utils.timezone import make_aware
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Side
from openpyxl.utils import get_column_letter
from .models import *
from django.views.decorators.cache import never_cache


@never_cache
@require_GET
@login_required
@permission_required("main.view_technics", raise_exception=True)
def export_technics_xlsx(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    org_id = (request.GET.get("organization") or "").strip()
    dep_id = (request.GET.get("department") or "").strip()
    dir_id = (request.GET.get("directorate") or "").strip()
    div_id = (request.GET.get("division") or "").strip()
    reg_id = (request.GET.get("region") or "").strip()
    group_id = (request.GET.get("group") or "").strip()
    category_id = (request.GET.get("category") or "").strip()
    status = (request.GET.get("status") or "").strip()
    name = (request.GET.get("name") or "").strip()

    qs = (
        Technics.objects
        .filter(is_active=True)
        .select_related("organization", "category", "group", "employee",
                         "employee__department", "employee__directorate", "employee__division")
        .prefetch_related("structure_set")
        .order_by("-id")
    )

    # Ro'yxat (barn_tex) bilan bir xil ko'rish doirasi: biriktirilgan kategoriyalar + tashkilot/hudud huquqlari
    liable_ids = Liable.categorys.through.objects.filter(
        liable__employee=employee
    ).values_list("category_id", flat=True)
    qs = qs.filter(category_id__in=liable_ids)
    if not request.user.has_perm("main.all_organization"):
        qs = qs.filter(organization_id=employee.organization_id)
    if not request.user.has_perm("main.all_region"):
        qs = qs.filter(region_id=employee.region_id)

    if org_id.isdigit():
        qs = qs.filter(organization_id=int(org_id))
    if dep_id.isdigit():
        qs = qs.filter(department_id=int(dep_id))
    if reg_id.isdigit():
        qs = qs.filter(region_id=int(reg_id))
    if dir_id.isdigit():
        qs = qs.filter(directorate_id=int(dir_id))
    if div_id.isdigit():
        qs = qs.filter(division_id=int(div_id))
    if group_id.isdigit():
        qs = qs.filter(group_id=int(group_id))
    if category_id.isdigit():
        qs = qs.filter(category_id=int(category_id))
    if status:
        qs = qs.filter(status=status)
    if name:
        qs = qs.filter(name__icontains=name)

    wb = Workbook()
    ws = wb.active
    ws.title = "Technics"

    headers = [
        "Tashkilot", "Departament", "Boshqarma", "Bo'lim", "F.I.O",
        "Group", "Category", "Name", "Parametr", "I/N", "S/N", "Mac",
        "Status", "Manitor Name", "Manitor S/N",
    ]
    ws.append(headers)

    for t in qs:
        emp = getattr(t, "employee", None)
        structures = list(t.structure_set.all())
        monitor = structures[0] if structures else None

        ws.append([
            (emp.organization.name if emp and emp.organization_id else ""),
            (emp.department.name if emp and emp.department_id else ""),
            (emp.directorate.name if emp and emp.directorate_id else ""),
            (emp.division.name if emp and emp.division_id else ""),
            (emp.full_name if emp else ""),
            (t.group.name if getattr(t, "group", None) else ""),
            (t.category.name if getattr(t, "category", None) else ""),
            (getattr(t, "name", "") or ""),
            (getattr(t, "parametr", "") or ""),
            (getattr(t, "inventory", "") or ""),
            (getattr(t, "serial", "") or ""),
            (getattr(t, "mac", "") or ""),
            (getattr(t, "status", "") or ""),
            (monitor.name if monitor else ""),
            (monitor.serial if monitor else ""),
        ])

    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 20

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)

    filename = "technics.xlsx"
    resp = HttpResponse(
        bio.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@never_cache
@require_GET
@login_required
@permission_required("main.view_material", raise_exception=True)
def export_material_xlsx(request):
    employee = getattr(request.user, "employee", None)
    if not employee or not employee.organization_id:
        raise PermissionDenied("Employee yo'q")

    employee_id = (request.GET.get("employee") or "").strip()
    name = (request.GET.get("name") or "").strip()

    # Ro'yxat (barn_mat) bilan bir xil ko'rish doirasi
    if request.user.has_perm("main.all_material_employee"):
        perm = Permission.objects.filter(codename="shop_employee", content_type__app_label="main").first()
        allowed_ids = set(
            Employee.objects.filter(
                Q(user__groups__permissions=perm) | Q(user__user_permissions=perm),
                organization=employee.organization,
            ).values_list("id", flat=True)
        ) if perm else set()
    else:
        allowed_ids = set(MaterialUser.objects.filter(receiver=employee).values_list("sender_id", flat=True))
        if Material.objects.filter(employee=employee, organization_id=employee.organization_id).exists():
            allowed_ids.add(employee.id)
    allowed_ids.discard(None)

    qs = (
        Material.objects
        .filter(organization_id=employee.organization_id, is_active=True, employee_id__in=allowed_ids)
        .select_related("employee", "unit")
        .order_by("-id")
    )

    if employee_id.isdigit():
        qs = qs.filter(employee_id=int(employee_id))
    if name:
        qs = qs.filter(Q(name__icontains=name) | Q(code__icontains=name))

    wb = Workbook()
    ws = wb.active
    ws.title = "Material"

    headers = ["Xodim", "Material Nomi", "Soni", "Narxi", "Summa", "Birligi", "1C code"]
    ws.append(headers)

    for m in qs:
        price = m.price or 0
        ws.append([
            m.employee.full_name if m.employee_id else "",
            m.name or "",
            m.number,
            price,
            (m.number or 0) * price,
            m.unit.name if m.unit_id else "",
            m.code or "",
        ])

    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 22

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)

    resp = HttpResponse(
        bio.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = 'attachment; filename="material.xlsx"'
    return resp


@never_cache
@require_GET
@login_required
@permission_required("main.view_material", raise_exception=True)
def export_mat_info_xlsx(request):
    """Material kirim-chiqim statistikasi (mat_info) - ekrandagi bilan bir xil
    filtr (xodim + sana oralig'i). "Umumiy" varag'i mat_info jadvaliga,
    "Harakatlar" varag'i har bir materialning tarixiga mos keladi."""
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    date1_raw = (request.GET.get("date1") or "").strip()
    date2_raw = (request.GET.get("date2") or "").strip()
    employee_id_raw = (request.GET.get("employee") or "").strip()
    name = (request.GET.get("name") or "").strip()

    date1 = parse_date(date1_raw) if date1_raw else None
    date2 = parse_date(date2_raw) if date2_raw else None

    if not (date1 and date2 and employee_id_raw.isdigit()):
        return HttpResponse("Xodim va sana oralig'i tanlanmagan", status=400)

    employee_id = int(employee_id_raw)

    # Ekrandagi bilan bir xil ruxsat doirasi: o'ziniki yoki
    # "all_material_employee" bo'lsa o'z tashkilotidagi shop_employee'lar.
    perm = Permission.objects.get(codename="shop_employee", content_type__app_label="main")
    if request.user.has_perm("main.all_material_employee"):
        allowed_ids = set(
            Employee.objects.filter(
                Q(user__groups__permissions=perm) | Q(user__user_permissions=perm),
                organization=employee.organization,
            ).values_list("id", flat=True)
        )
    else:
        allowed_ids = {employee.id}

    if employee_id not in allowed_ids:
        raise PermissionDenied("Bu xodim bo'yicha ruxsat yo'q")

    start_dt = make_aware(datetime.combine(date1, time.min))
    end_dt = make_aware(datetime.combine(date2, time.max))

    movements_qs = (
        MaterialMovement.objects
        .exclude(status='deleted')
        .exclude(status='assigned', employee__isnull=True)
        .filter(material__employee_id=employee_id)
        .filter(date_creat__gte=start_dt, date_creat__lte=end_dt)
    )
    if name:
        movements_qs = movements_qs.filter(
            Q(material__name__icontains=name) | Q(material__code__icontains=name)
        )

    period_map = {
        row["material"]: row
        for row in movements_qs.values("material").annotate(
            period_income=Sum("income"),
            period_outcome=Sum("outcome"),
        )
    }

    movements_detail_qs = movements_qs.select_related("employee", "user", "material").order_by(
        "material__name", "date_creat"
    )

    materials = Material.objects.filter(
        organization=employee.organization,
        is_active=True, employee_id=employee_id,
    ).select_related("unit", "category").order_by("name")
    if name:
        materials = materials.filter(Q(name__icontains=name) | Q(code__icontains=name))

    table_rows = []
    for m in materials:
        period = period_map.get(m.id, {})
        income = period.get("period_income") or 0
        total_outcome = period.get("period_outcome") or 0
        current_count = m.number
        initial_balance = current_count - income + total_outcome

        if initial_balance == 0 and income == 0 and total_outcome == 0 and current_count == 0:
            continue

        table_rows.append({
            "material": m,
            "initial_balance": initial_balance,
            "income": income,
            "outcome": total_outcome,
            "current_balance": current_count,
        })

    table_rows.sort(key=lambda row: (row["income"] == 0 and row["outcome"] == 0, row["material"].name))

    target_employee = Employee.objects.filter(id=employee_id).first()
    emp_name = target_employee.full_name if target_employee else ""

    wb = Workbook()

    ws = wb.active
    ws.title = "Umumiy"
    ws.append([f"Xodim: {emp_name}", f"Davr: {date1_raw} - {date2_raw}"])
    headers = ["T/r", "Nomi", "Kodi", "Narxi", "Birligi", "Kirim", "Chiqim", "Qoldiq"]
    ws.append(headers)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    # Standart, qalin/qora bo'lmagan ochiq kulrang chiziq (odatiy Excel katak
    # chizig'iga o'xshash).
    divider = Border(bottom=Side(style="thin", color="BFBFBF"))
    for col in range(1, len(headers) + 1):
        ws.cell(row=ws.max_row, column=col).alignment = center

    # Har bir material 2 qatorga yoziladi: yuqorisida soni, pastida summasi -
    # orasiga chiziq (border) tortiladi, xuddi kasr chizig'idek. Nomi/Kodi/
    # Narxi/Birligi/T-r ustunlari ikkala qatorga vertikal birlashtiriladi.
    for i, row in enumerate(table_rows, start=1):
        m = row["material"]
        price = m.price or 0
        income = row["income"]
        outcome = row["outcome"]
        balance = row["current_balance"]

        top = ws.max_row + 1
        bottom = top + 1
        ws.append([i, m.name, m.code or "", price, (m.unit.name if m.unit_id else ""), income, outcome, balance])
        ws.append([None, None, None, None, None, income * price, outcome * price, balance * price])

        for col in range(1, 6):
            ws.merge_cells(start_row=top, start_column=col, end_row=bottom, end_column=col)
            ws.cell(row=top, column=col).alignment = center
        for col in range(6, 9):
            ws.cell(row=top, column=col).alignment = center
            ws.cell(row=top, column=col).border = divider
            ws.cell(row=bottom, column=col).alignment = center
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 16

    ws2 = wb.create_sheet("Harakatlar")
    headers2 = ["T/r", "Material", "Sana", "Kimdan", "Kimga", "Kirim", "Chiqim", "Holati"]
    ws2.append(headers2)
    for i, mv in enumerate(movements_detail_qs, start=1):
        ws2.append([
            i,
            mv.material.name if mv.material else "",
            mv.date_creat.strftime("%d.%m.%Y %H:%M") if mv.date_creat else "",
            mv.user.full_name if mv.user else "-",
            mv.employee.full_name if mv.employee else "-",
            mv.income or 0,
            mv.outcome or 0,
            mv.get_status_display(),
        ])
    for col in range(1, len(headers2) + 1):
        ws2.column_dimensions[get_column_letter(col)].width = 22

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)

    filename = f"material_kirim_chiqim_{date1_raw}_{date2_raw}.xlsx"
    resp = HttpResponse(
        bio.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@never_cache
@require_GET
@login_required
@permission_required("main.view_employee", raise_exception=True)
def export_employee_xlsx(request):
    """Xodimlar jadvali (employee) - ekrandagi bilan bir xil filtrlar
    (tashkilot, hudud, departament, boshqarma, bo'lim, F.I.O/PINFL qidiruv)."""
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    organization_id = (request.GET.get("organization") or "").strip()
    region_id = (request.GET.get("region") or "").strip()
    department_id = (request.GET.get("department") or "").strip()
    directorate_id = (request.GET.get("directorate") or "").strip()
    division_id = (request.GET.get("division") or "").strip()
    name = (request.GET.get("name") or "").strip()

    if not organization_id:
        return HttpResponse("Tashkilot tanlanmagan", status=400)

    # Ekrandagi bilan bir xil ko'rish doirasi: "all_organization"/"all_region"
    # bo'lmasa faqat o'z tashkiloti/hududi.
    if not request.user.has_perm("main.all_organization") and organization_id != str(employee.organization_id):
        raise PermissionDenied("Bu tashkilot bo'yicha ruxsat yo'q")
    if region_id and not request.user.has_perm("main.all_region") and region_id != str(employee.region_id):
        raise PermissionDenied("Bu hudud bo'yicha ruxsat yo'q")

    qs = (
        Employee.objects
        .select_related("organization", "department", "directorate", "division", "region", "rank", "user")
        .filter(organization_id=organization_id)
    )
    if region_id:
        qs = qs.filter(region_id=region_id)
    if department_id:
        qs = qs.filter(department_id=department_id)
    if directorate_id:
        qs = qs.filter(directorate_id=directorate_id)
    if division_id:
        qs = qs.filter(division_id=division_id)
    if name:
        terms = name.split()
        query = Q()
        for term in terms:
            query &= (
                Q(last_name__icontains=term) |
                Q(first_name__icontains=term) |
                Q(father_name__icontains=term) |
                Q(pinfl__icontains=term)
            )
        qs = qs.filter(query)

    qs = qs.order_by("-id")

    wb = Workbook()
    ws = wb.active
    ws.title = "Xodimlar"

    headers = [
        "T/r", "Tashkilot", "Hudud", "Departament", "Boshqarma", "Bo'lim",
        "Lavozimi", "F.I.O", "PINFL", "Telefon", "Holati",
    ]
    ws.append(headers)

    for i, e in enumerate(qs, start=1):
        ws.append([
            i,
            e.organization.name if e.organization_id else "",
            e.region.name if e.region_id else "",
            e.department.name if e.department_id else "",
            e.directorate.name if e.directorate_id else "",
            e.division.name if e.division_id else "",
            e.rank.name if e.rank_id else "",
            e.full_name,
            e.pinfl or "",
            e.phone or "",
            "Faol" if e.user.is_active else "Nofaol",
        ])

    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 22

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)

    filename = "xodimlar.xlsx"
    resp = HttpResponse(
        bio.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp
