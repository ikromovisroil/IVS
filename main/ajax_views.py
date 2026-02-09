from django.shortcuts import get_object_or_404
from .models import *
from django.http import JsonResponse
from django.db.models import Q
from django.template.loader import render_to_string


def deed_mark_seen(request):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'unauth'})

    Deed.objects.filter(
        sender__user=request.user,
        status_sender__in=['approved', 'rejected'],
        sender_seen=False
    ).update(sender_seen=True)

    return JsonResponse({'status': 'ok'})


def order_mark_seen(request):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'unauth'})

    Order.objects.filter(
        receiver__user=request.user,
        status_receiver__in=['approved', 'rejected'],
        receiver_seen=False
    ).update(receiver_seen=True)

    return JsonResponse({'status': 'ok'})

def get_department_employees(request):
    emp_id = request.GET.get("employee_id")

    try:
        receiver = Employee.objects.get(id=emp_id)
    except Employee.DoesNotExist:
        return JsonResponse({"employees": []})

    # 🔥 Qaysi bo‘limga tegishli bo‘lsa — o‘sha bo‘lim xodimlari
    qs = Employee.objects.filter(
        department=receiver.department
    ).exclude(id=receiver.id)  # Qabul qiluvchining o'zi chiqmasin

    data = [
        {"id": e.id, "name": f"{e.rank} - {e.full_name}"}
        for e in qs
    ]

    return JsonResponse({"employees": data})


def ajax_load_departments(request):
    org_id = request.GET.get('organization')

    if not org_id or org_id == "None":
        return JsonResponse([], safe=False)

    departments = Department.objects.filter(
        organization_id=org_id,
    ).values('id', 'name')

    return JsonResponse(list(departments), safe=False)


def ajax_load_directorate(request):
    dep_id = request.GET.get('department')

    if not dep_id or dep_id == "None":
        return JsonResponse([], safe=False)

    directorate = Directorate.objects.filter(
        department_id=dep_id,
    ).values('id', 'name')

    return JsonResponse(list(directorate), safe=False)


def ajax_load_division(request):
    dir_id = request.GET.get('directorate')

    if not dir_id or dir_id == "None":
        return JsonResponse([], safe=False)

    division = Division.objects.filter(
        directorate_id=dir_id,
    ).values('id', 'name')

    return JsonResponse(list(division), safe=False)


def get_technics_count(request):
    division_id = request.GET.get('division')

    komp_count = Technics.objects.filter(
        category__name__in=['Kompyuter', 'Planshet', 'Noutbook', 'Doska'],
        employee__division_id=division_id
    ).count()

    prin_count = Technics.objects.filter(
        category__name__in=['A4 Printer', 'A3 Printer', 'scaner'],
        employee__division_id=division_id
    ).count()

    return JsonResponse({
        "komp": komp_count,
        "printer": prin_count
    })

def get_goals(request, topic_id):
    goals = Goal.objects.filter(topic_id=topic_id).values("id", "name")

    return JsonResponse({"goals": list(goals)})


def order_finish(request, pk):
    order = get_object_or_404(Order, id=pk)
    order.status = "finished"
    order.save()
    return JsonResponse({"status": "ok"})


def order_rejected(request, pk):
    order = get_object_or_404(Order, id=pk)
    order.status = "rejected"
    order.save()
    return JsonResponse({"status": "ok"})


from django.http import JsonResponse
def ajax_load_employees(request):
    dep_id = request.GET.get("department")

    if not dep_id:
        return JsonResponse([], safe=False)

    qs = (
        Employee.objects
        .filter(department_id=dep_id)
        .select_related("rank")
        .order_by("last_name", "first_name", "father_name")
    )

    data = [{"id": e.id, "full_name": e.full_name} for e in qs]
    return JsonResponse(data, safe=False)


def ajax_employees_org(request):
    org_id = (request.GET.get("organization") or "").strip()
    if not org_id:
        return JsonResponse({"results": []})

    qs = (
        Employee.objects
        .select_related("user")
        .filter(organization_id=org_id)
        .select_related("rank")
        .order_by("last_name", "first_name", "father_name")
    )

    data = [{"id": e.id, "text": e.full_name} for e in qs]
    return JsonResponse({"results": data})


def ajax_org_employees(request):
    org_id = (request.GET.get("org_id") or "").strip()
    if not org_id:
        return JsonResponse({"results": []})

    qs = (
        Employee.objects
        .filter(organization_id=org_id)
        .select_related("rank")
        .annotate(
            full_name=Concat(
                Coalesce(F("last_name"), Value("")),
                Value(" "),
                Coalesce(F("first_name"), Value("")),
                Value(" "),
                Coalesce(F("father_name"), Value("")),
                output_field=CharField(),
            )
        )
        .values("id", "full_name")
        .order_by("full_name")
    )

    return JsonResponse({"results": list(qs)})

def ajax_agreements_employees(request):
    org_id = (request.GET.get("org_id") or "").strip()

    qs = Employee.objects.filter(
        organization__org_type="IVS",
        # rol__boss=True,
    )

    if org_id and org_id.isdigit():
        qs = Employee.objects.filter(
            Q(organization_id=org_id) | Q(organization__org_type="IVS"),
            # rol__boss=True,
        )

    qs = qs.select_related("rank", "organization").distinct().order_by("last_name", "first_name")

    data = [{
        "id": e.id,
        "text": f"{e.full_name}",
    } for e in qs]

    return JsonResponse({"results": data})


from django.core.exceptions import PermissionDenied
def deedconsent_delete(request, pk):
    emp = getattr(request.user, "employee", None)
    if not emp:
        raise PermissionDenied

    obj = get_object_or_404(DeedConsent, pk=pk)

    if obj.deed.user_id != emp.id:
        raise PermissionDenied

    obj.delete()
    return JsonResponse({"ok": True})

def ajax_deedconsent_delete(request):
    dc_id = request.POST.get("dc_id")
    if not dc_id:
        return JsonResponse({"ok": False, "error": "dc_id required"}, status=400)

    dc = get_object_or_404(DeedConsent, id=dc_id)

    # ✅ RUXSAT: faqat deed egasi (jo‘natuvchi) o‘chira olsin
    # sizda request.user.employee bor
    if not hasattr(request.user, "employee") or dc.deed.user_id != request.user.employee.id:
        return JsonResponse({"ok": False, "error": "permission denied"}, status=403)

    dc.delete()
    return JsonResponse({"ok": True, "deleted_id": int(dc_id)})

from datetime import datetime, timedelta
from django.db.models import F, Value, CharField
from django.db.models.functions import Concat
def ajax_akt_materials(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    dep_id = request.GET.get("department")
    d1 = request.GET.get("date1")
    d2 = request.GET.get("date2")

    if not dep_id or not d1 or not d2:
        return JsonResponse([], safe=False)

    date1 = timezone.make_aware(datetime.strptime(d1, "%Y-%m-%d"))
    date2 = timezone.make_aware(datetime.strptime(d2, "%Y-%m-%d") + timedelta(days=1))

    qs = (
        OrderMaterial.objects.filter(
            order__date_finished__gte=date1,
            order__date_finished__lt=date2,
            order__sender__department_id=dep_id,
            order__receiver__region=employee.region,
        )
        .annotate(
            full_name=Concat(
                F('order__sender__first_name'),
                Value(' '),
                F('order__sender__last_name'),
                Value(' '),
                F('order__sender__father_name'),
                output_field=CharField()
            ),
            rank_name=F('order__sender__rank__name'),  # rank nomini olish
        )
        .values(
            "order__technics__name",
            "order__technics__serial",
            "material__name",
            "number",
            "material__unit__name",
            "full_name",  # endi bu mavjud
            "rank_name",  # rank nomi
            "material__price",
            "id",
            "order__date_finished",
        )
    )

    return JsonResponse(list(qs), safe=False)

from datetime import datetime, timedelta
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.utils import timezone

from django.db.models import Sum, F, DecimalField, ExpressionWrapper, Value
from django.db.models.functions import Coalesce, Cast
from django.contrib.postgres.aggregates import StringAgg


def ajax_svod_materials(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    org_id = request.GET.get("organization")
    d1 = request.GET.get("date1")
    d2 = request.GET.get("date2")

    if not org_id or not d1 or not d2:
        return JsonResponse([], safe=False)

    try:
        date1 = timezone.make_aware(datetime.strptime(d1, "%Y-%m-%d"))
        date2 = timezone.make_aware(datetime.strptime(d2, "%Y-%m-%d") + timedelta(days=1))
    except ValueError:
        return JsonResponse({"error": "Noto'g'ri sana formati"}, status=400)

    # umumiy filter (2 marta yozmaslik uchun)
    base_filter = dict(
        order__date_finished__gte=date1,
        order__date_finished__lt=date2,
        order__sender__organization_id=org_id,
        order__receiver__region=employee.region,
    )
    # Decimal/Integer aralashmasligi uchun
    dec = DecimalField(max_digits=18, decimal_places=2)
    zero_dec = Value(0, output_field=dec)

    # 1) Material bo‘yicha svod: qty + sum
    qs = (
        OrderMaterial.objects.filter(**base_filter)
        .values(
            "material_id",                 # ✅ shart
            "material__code",
            "material__name",
            "material__unit__name",
            "material__price",
        )
        .annotate(
            total_number=Coalesce(Sum("number"), 0),
        )
        .annotate(
            total_sum=ExpressionWrapper(
                Coalesce(F("material__price"), zero_dec) *
                Cast(Coalesce(F("total_number"), 0), output_field=dec),
                output_field=dec,
            )
        )
        .order_by("material__code", "material__name")
    )

    # 2) Har bir material uchun order_id + date_finished yig‘amiz (SQLite friendly)
    rel = (
        OrderMaterial.objects.filter(**base_filter)
        .values("material_id", "order_id", "order__date_finished")
        .distinct()
    )
    material_orders = {}
    for r in rel:
        mid = r["material_id"]
        dt = r["order__date_finished"]
        dt_str = dt.date().isoformat() if dt else ""
        txt = f'Akt №{r["order_id"]} ga {dt_str}y'
        material_orders.setdefault(mid, []).append(txt)

    # 3) JSON tayyorlash
    data = []
    for item in qs:
        mid = item["material_id"]
        order_info = ", ".join(material_orders.get(mid, []))

        data.append({
            "material__name": item.get("material__name", ""),
            "material__unit__name": item.get("material__unit__name", ""),
            "total_number": float(item.get("total_number") or 0),
            "material__price": float(item.get("material__price") or 0),
            "total_sum": float(item.get("total_sum") or 0),
            "order_info": order_info,  # ✅ probelsiz key
            "material__code": item.get("material__code", ""),
        })
    return JsonResponse(data, safe=False)


def ajax_reestr_materials(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    org_id = request.GET.get("organization")
    d1 = request.GET.get("date1")
    d2 = request.GET.get("date2")

    if not org_id or not d1 or not d2:
        return JsonResponse([], safe=False)

    try:
        date1 = timezone.make_aware(datetime.strptime(d1, "%Y-%m-%d"))
        date2 = timezone.make_aware(datetime.strptime(d2, "%Y-%m-%d") + timedelta(days=1))
    except ValueError:
        return JsonResponse({"error": "Noto'g'ri sana formati"}, status=400)

    dec = DecimalField(max_digits=18, decimal_places=2)
    zero_dec = Value(0, output_field=dec)

    qs = (
        OrderMaterial.objects.filter(
            order__date_finished__gte=date1,
            order__date_finished__lt=date2,
            order__sender__organization_id=org_id,
            order__receiver__region=employee.region,
        )
        .annotate(
            total_sum=ExpressionWrapper(
                Coalesce(F("material__price"), zero_dec) *
                Cast(Coalesce(F("number"), 0), output_field=dec),
                output_field=dec,
            ),

            # ✅ Sender FIO
            sender_full_name=Concat(
                Coalesce(F("order__sender__last_name"), Value("")),
                Value(" "),
                Coalesce(F("order__sender__first_name"), Value("")),
                Value(" "),
                Coalesce(F("order__sender__father_name"), Value("")),
                output_field=CharField(),
            ),

            # ✅ Receiver FIO
            receiver_full_name=Concat(
                Coalesce(F("order__receiver__last_name"), Value("")),
                Value(" "),
                Coalesce(F("order__receiver__first_name"), Value("")),
                Value(" "),
                Coalesce(F("order__receiver__father_name"), Value("")),
                output_field=CharField(),
            ),
        )
        .values(
            "order__id",
            "order__date_finished",
            "order__date_creat",
            "order__technics__name",
            "order__technics__serial",

            "material__code",
            "material__name",
            "material__price",
            "number",

            "sender_full_name",
            "order__sender__rank__name",
            "order__sender__department__name",

            "receiver_full_name",
            "order__receiver__rank__name",

            "total_sum",
        )
        .order_by("material__code", "material__name", "order__id")
    )

    data = []
    for item in qs:
        data.append({
            "order_id": item.get("order__id"),

            "date_finished": item["order__date_finished"].strftime("%d.%m.%Y")
                if item.get("order__date_finished") else "",
            "date_creat": item["order__date_creat"].strftime("%d.%m.%Y")
                if item.get("order__date_creat") else "",

            "technics_name": item.get("order__technics__name", ""),
            "technics_serial": item.get("order__technics__serial", ""),

            "material_code": item.get("material__code", ""),
            "material_name": item.get("material__name", ""),
            "number": float(item.get("number") or 0),
            "material_price": float(item.get("material__price") or 0),
            "total_sum": float(item.get("total_sum") or 0),

            "sender": (item.get("sender_full_name") or "").strip(),
            "sender_rank": item.get("order__sender__rank__name", ""),
            "department": item.get("order__sender__department__name", ""),

            "receiver": (item.get("receiver_full_name") or "").strip(),
            "receiver_rank": item.get("order__receiver__rank__name", ""),
        })

    return JsonResponse(data, safe=False)

from datetime import date
from django.db.models import Count
def ajax_document_preview(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    org_id = (request.GET.get("organization") or "").strip()
    dep_id = (request.GET.get("department") or "").strip()
    rim_id = (request.GET.get("rim_id") or "").strip()  # I / II / III / IV

    if not dep_id or not rim_id:
        return JsonResponse({"error": "department va chorak majburiy"}, status=400)

    dep = Department.objects.filter(id=dep_id).first()
    if not dep:
        return JsonResponse({"error": "Department topilmadi"}, status=404)

    # Sizga kerak bo'lsa org ham tekshiring
    org = Organization.objects.filter(id=org_id).first() if org_id else None

    komp_names = ["Kompyuter", "Planshet", "Noutbook", "Doska"]
    prin_names = ["A4 Printer", "Printer", "scaner"]

    base_qs = (
        Technics.objects.filter(order__sender__department_id=dep_id)
        .select_related("category")
        .distinct()
    )

    counts = (
        base_qs.filter(category__name__in=komp_names + prin_names)
        .values("category__name")
        .annotate(c=Count("id"))
    )
    komp_count = sum(x["c"] for x in counts if x["category__name"] in komp_names)
    prin_count = sum(x["c"] for x in counts if x["category__name"] in prin_names)

    kompyuterlar = list(
        base_qs.filter(category__name__in=komp_names)
        .values("name", "serial", "inventory")
    )
    printerlar = list(
        base_qs.filter(category__name__in=prin_names)
        .values("name", "serial")
    )

    data = {
        "department_name": dep.name or "",
        "rim_id": rim_id,
        "today": date.today().strftime("%d.%m.%Y"),
        "fio": employee.full_name or "",
        "komp_count": komp_count,
        "prin_count": prin_count,
        "kompyuterlar": kompyuterlar,
        "printerlar": printerlar,
    }
    return JsonResponse(data, safe=False)