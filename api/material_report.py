"""
Material kirim-chiqim hisoboti (saytdagi mat_info) — JSON uchun.
Hisob-kitob main/views.py:mat_info bilan bir xil; farqi: xodim tanlovi saytdagi ro'yxat doirasi bilan
(o'zi yoki all_material_employee bo'lsa tashkilotdagi shop_employee xodimlar) serverda ham tekshiriladi.
"""
from datetime import datetime, time

from django.contrib.auth.models import Permission
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.timezone import make_aware
from rest_framework.exceptions import PermissionDenied, ValidationError

from main.models import Employee, Material, MaterialMovement


def allowed_report_employees(user, employee):
    """Hisobotda tanlash mumkin bo'lgan xodimlar (saytdagi mat_info dropdown'i)."""
    if user.has_perm("main.all_material_employee"):
        perm = Permission.objects.filter(codename="shop_employee", content_type__app_label="main").first()
        if not perm:
            return Employee.objects.none()
        return Employee.objects.filter(
            Q(user__groups__permissions=perm) | Q(user__user_permissions=perm),
            organization=employee.organization,
        ).distinct()
    return Employee.objects.filter(id=employee.id)


def parse_period(params):
    """date1/date2 (YYYY-MM-DD); berilmasa joriy oy (saytdagidek). (date1, date2) qaytaradi."""
    today = timezone.localdate()
    raw1 = (params.get("date1") or "").strip() or today.replace(day=1).isoformat()
    raw2 = (params.get("date2") or "").strip() or today.isoformat()
    d1, d2 = parse_date(raw1), parse_date(raw2)
    if not d1:
        raise ValidationError({"date1": "Boshlanish sanasi noto'g'ri formatda (YYYY-MM-DD)"})
    if not d2:
        raise ValidationError({"date2": "Tugash sanasi noto'g'ri formatda (YYYY-MM-DD)"})
    if d1 > d2:
        raise ValidationError({"date1": "Boshlanish sanasi tugash sanasidan katta bo'lishi mumkin emas"})
    return d1, d2


def build_report(user, employee, employee_id, date1, date2, name=""):
    if employee_id not in set(allowed_report_employees(user, employee).values_list("id", flat=True)):
        raise PermissionDenied("Bu xodimning hisobotini ko'rishga ruxsatingiz yo'q")

    start_dt = make_aware(datetime.combine(date1, time.min))
    end_dt = make_aware(datetime.combine(date2, time.max))

    # Biriktirilmagan "savat" qatorlari (assigned, employee=None) haqiqiy harakat emas
    movements_qs = (
        MaterialMovement.objects
        .exclude(status="deleted")
        .exclude(status="assigned", employee__isnull=True)
        .filter(material__employee_id=employee_id, date_creat__gte=start_dt, date_creat__lte=end_dt)
    )
    period_map = {
        row["material"]: row
        for row in movements_qs.values("material").annotate(
            period_income=Sum("income"), period_outcome=Sum("outcome"),
        )
    }
    movements_by_material = {}
    for mv in movements_qs.select_related("employee", "user").order_by("date_creat"):
        movements_by_material.setdefault(mv.material_id, []).append({
            "date": mv.date_creat,
            "user": mv.user.full_name if mv.user_id else None,
            "employee": mv.employee.full_name if mv.employee_id else None,
            "income": mv.income,
            "outcome": mv.outcome,
            "status": mv.status,
            "status_display": mv.get_status_display(),
            "body": mv.body,
        })

    materials = (
        Material.objects
        .filter(organization=employee.organization, is_active=True, employee_id=employee_id)
        .select_related("unit", "category").order_by("name")
    )
    if name:
        materials = materials.filter(Q(name__icontains=name) | Q(code__icontains=name))

    rows = []
    for m in materials:
        period = period_map.get(m.id, {})
        income = period.get("period_income") or 0
        outcome = period.get("period_outcome") or 0
        current = m.number
        initial = current - income + outcome
        if initial == 0 and income == 0 and outcome == 0 and current == 0:
            continue
        price = m.price or 0
        rows.append({
            "id": m.id,
            "name": m.name,
            "code": m.code,
            "unit": m.unit.name if m.unit_id else "",
            "category": m.category.name if m.category_id else "",
            "price": m.price,
            "initial_balance": initial,
            "income": income, "income_sum": income * price,
            "outcome": outcome, "outcome_sum": outcome * price,
            "current_balance": current, "current_sum": current * price,
            "movements": movements_by_material.get(m.id, []),
        })

    # Harakati borlar tepada, keyin nomi bo'yicha (saytdagidek)
    rows.sort(key=lambda r: (r["income"] == 0 and r["outcome"] == 0, r["name"]))
    return rows
