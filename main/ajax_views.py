from .models import *
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from datetime import datetime, timedelta
from collections import defaultdict
from django.utils import timezone
from django.db.models import Sum, F, DecimalField, ExpressionWrapper, Value,CharField
from django.db.models.functions import Coalesce, Cast,Concat
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import permission_required
from .sanitizers import sanitize_deed_body
from .html_pdf import html_to_pdf_bytes, HtmlPdfError
import io
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, JsonResponse

@never_cache
@require_GET
@login_required
def ajax_load_categories(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    group_id = request.GET.get("group")
    qs = Category.objects.none()

    liable_ids = Liable.objects.filter(
        employee=employee
    ).values_list("category_id", flat=True)

    if group_id:
        qs = (
            Category.objects
            .filter(id__in=liable_ids, group_id=group_id)
            .only("id", "name")
            .order_by("name")
        )

    return JsonResponse({
        "results": [{"id": c.id, "name": c.name} for c in qs]
    })


@never_cache
@require_GET
@login_required
def ajax_sender_technics(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    sender_id = (request.GET.get("sender_id") or "").strip()
    if not sender_id.isdigit():
        return JsonResponse({"results": []})

    sender = Employee.objects.filter(id=sender_id).first()

    if not sender:
        return JsonResponse({"results": []})

    technics = (
        Technics.objects
        .filter(
            Q(employee_id=sender.id) |
            Q(employee__isnull=True, department=sender.department),
            is_active=True,
        )
        .order_by("name")
        .values("id", "name", "inventory", "serial", "mac")
    )

    results = []
    for t in technics:
        results.append({
            "id": t["id"],
            "text": f'{t["name"] or ""} | {t["inventory"] or ""} | {t["serial"] or ""} | {t["mac"] or ""}'
        })

    return JsonResponse({"results": results})


@never_cache
@require_GET
@login_required
def order_mark_seen(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        return JsonResponse({"status": "no_employee"}, status=400)

    Order.objects.filter(
        receiver=employee,
        goal__organization__type="worker",
        status__in=["approved", "canceled"],
        receiver_seen=False,
    ).update(receiver_seen=True)

    Order.objects.filter(
        receiver=employee,
        goal__organization__type="client",
        status__in=["accepted", "canceled", "rejected"],
        receiver_seen=False,
    ).update(receiver_seen=True)

    # Yuboruvchi (sender) — worker
    Order.objects.filter(
        sender=employee,
        goal__organization__type="worker",
        status__in=["finished", "rejected"],
        sender_seen=False,
    ).update(sender_seen=True)

    # Yuboruvchi (sender) — client
    Order.objects.filter(
        sender=employee,
        goal__organization__type="client",
        status__in=["approved", "rejected"],
        sender_seen=False,
    ).update(sender_seen=True)

    # Tasdiqlovchi (user)
    Order.objects.filter(
        user=employee,
        goal__organization__type="client",
        status="accepted",
        user_seen=False,
    ).update(user_seen=True)

    return JsonResponse({"status": "ok"})


@never_cache
@require_GET
@login_required
def order_check_new(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        return JsonResponse({"error": "Employee yo‘q"}, status=400)

    order_goal_ids = OrderGoal.objects.filter(
        employee=employee
    ).values_list("goal_id", flat=True)

    orders_qs = Order.objects.filter(
        sender__region=employee.region,
        goal_id__in=order_goal_ids,
        goal__organization__type="worker",
        status="viewed",
    )

    latest_order = orders_qs.order_by("-id").values("id").first()

    return JsonResponse({
        "latest_id": latest_order["id"] if latest_order else 0,
        "count": orders_qs.count(),
    })


@never_cache
@require_GET
@login_required
def order_check_all(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        return JsonResponse({"error": "Employee yo‘q"}, status=400)

    latest_order = (
        Order.objects
        .filter(sender__region=employee.region,goal__organization=employee.organization, status="viewed")
        .order_by("-id")
        .values("id")
        .first()
    )

    return JsonResponse({
        "latest_id": latest_order["id"] if latest_order else 0,
    })


@never_cache
@require_GET
@login_required
def get_department_employees(request):
    emp_id = (request.GET.get("employee_id") or "").strip()
    if not emp_id.isdigit():
        return JsonResponse({"employees": []})

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


@never_cache
@require_GET
@login_required
def ajax_load_departments(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    org_id = (request.GET.get("organization") or "").strip()
    reg_id = (request.GET.get("region") or "").strip()

    if not org_id or not org_id.isdigit():
        return JsonResponse({"results": []})

    # region kelmasa — joriy foydalanuvchining regionini ishlatamiz
    if not reg_id or not reg_id.isdigit():
        reg_id = str(employee.region_id) if employee.region_id else ""

    filters = {"organization_id": org_id}

    if reg_id and reg_id.isdigit():
        filters["region_id"] = reg_id

    qs = Department.objects.filter(**filters).values("id", "name").order_by("id")

    return JsonResponse({"results": list(qs)})


@never_cache
@require_GET
@login_required
def ajax_load_directorate(request):
    dep_id = (request.GET.get("department") or "").strip()
    if not dep_id or dep_id == "None":
        return JsonResponse({"results": []})

    qs = Directorate.objects.filter(department_id=dep_id).values("id", "name")
    return JsonResponse({"results": list(qs)})


@never_cache
@require_GET
@login_required
def ajax_load_division(request):
    dir_id = (request.GET.get("directorate") or "").strip()
    if not dir_id or dir_id == "None":
        return JsonResponse({"results": []})

    qs = Division.objects.filter(directorate_id=dir_id).values("id", "name")
    return JsonResponse({"results": list(qs)})


@never_cache
@require_GET
@login_required
def ajax_dep_signatory(request):
    org_id = (request.GET.get("organization") or "").strip()
    dep_id = (request.GET.get("department") or "").strip()

    employee = getattr(request.user, "employee", None)
    if not employee:
        return JsonResponse([], safe=False)

    # ikkalasi ham bo'lmasa bo'sh
    if not org_id and not dep_id:
        return JsonResponse([], safe=False)

    qs = Employee.objects.select_related("rank")

    if dep_id:
        qs = qs.filter(department_id=dep_id)
    elif org_id:
        qs = qs.filter(organization_id=org_id, region=employee.region)
    else:
        return JsonResponse([], safe=False)

    qs = qs.order_by("last_name", "first_name", "father_name")

    data = [{
        "id": e.id,
        "full_name": getattr(e, "full_name", "") or f"{e.last_name} {e.first_name} {e.father_name}".strip(),
        "rank": (e.rank.name if getattr(e, "rank", None) else ""),
    } for e in qs]

    return JsonResponse(data, safe=False)


@never_cache
@require_GET
@login_required
def ajax_dep_negotiator(request):
    org_id = (request.GET.get("organization") or "").strip()
    dep_id = (request.GET.get("department") or "").strip()

    employee = getattr(request.user, "employee", None)
    my_dep_id = getattr(employee, "department_id", None)
    my_org_id = getattr(employee, "organization_id", None)

    if not org_id and not dep_id:
        return JsonResponse([], safe=False)

    qs = Employee.objects.select_related("rank")

    if dep_id:
        qs = qs.filter(Q(department_id=dep_id) | Q(department_id=my_dep_id))
    elif org_id:
        # Bug tuzatildi: avval "organization_id=my_dep_id" edi — department
        # ID organization ustunida qidirilardi (ikki ID fazosi mos
        # kelmaydi, deyarli hech qachon to'g'ri natija bermas edi).
        qs = qs.filter(Q(organization_id=org_id) | Q(organization_id=my_org_id))
    else:
        return JsonResponse([], safe=False)

    qs = qs.order_by("last_name", "first_name", "father_name").distinct()

    data = [{
        "id": e.id,
        "full_name": getattr(e, "full_name", "") or f"{e.last_name} {e.first_name} {e.father_name}".strip(),
        "rank": (e.rank.name if getattr(e, "rank", None) else ""),
    } for e in qs]
    return JsonResponse(data, safe=False)


@never_cache
@require_GET
@login_required
def ajax_employees_org(request):
    org_id = (request.GET.get("organization") or "").strip()
    reg_id = (request.GET.get("region") or "").strip()

    if not org_id and not reg_id:
        return JsonResponse({"results": []})

    qs = Employee.objects.all()
    if org_id:
        qs = qs.filter(organization_id=org_id)
    if reg_id:
        qs = qs.filter(region_id=reg_id)

    data = [{"id": e.id, "text": e.full_name} for e in qs]
    return JsonResponse({"results": data})


@never_cache
@require_GET
@login_required
def ajax_employees_org_user_region(request):
    org_id = (request.GET.get("organization") or "").strip()

    if not org_id:
        return JsonResponse({"results": []})

    qs = Employee.objects.filter(organization_id=org_id)

    data = [{"id": e.id, "text": e.full_name} for e in qs]
    return JsonResponse({"results": data})


@never_cache
@require_GET
@login_required
def ajax_agreements_employees(request):
    employee = getattr(request.user, "employee", None)
    my_org_id = getattr(employee, "organization_id", None)
    my_region_id = getattr(employee, "region_id", None)
    org_id = request.GET.get("org_id")

    if not org_id or not str(org_id).isdigit():
        return JsonResponse([], safe=False)

    qs = Employee.objects.filter(
        Q(organization_id=org_id) |
        Q(organization_id=my_org_id)
    ).select_related("rank").order_by(
        "last_name", "first_name", "father_name"
    ).distinct()

    data = [{
        "id": e.id,
        "full_name": getattr(e, "full_name", "") or f"{e.last_name} {e.first_name} {e.father_name}".strip(),
        "rank": (e.rank.name if getattr(e, "rank", None) else ""),
    } for e in qs]
    return JsonResponse(data, safe=False)


@login_required
@require_POST
@transaction.atomic
def ordermaterial_delete(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        return JsonResponse({"status": "no_employee"}, status=403)

    om = get_object_or_404(
        OrderMaterial.objects.select_related("material", "order"),
        pk=pk
    )

    order = om.order
    if order is None:
        return JsonResponse({"status": "error", "message": "Ariza topilmadi"}, status=400)

    if order.receiver != employee:
        raise PermissionDenied("Sizda bu materialni o'chirish huquqi yo'q")

    material = om.material
    material.number = (material.number or 0) + (om.number or 0)
    material.save(update_fields=["number"])

    om.delete()
    return JsonResponse({"status": "ok"})


@never_cache
@require_GET
@login_required
def ajax_search_tex(request):
    query = request.GET.get("q", "").strip()

    if not query:
        return JsonResponse({"results": []})

    texs = Technics.objects.filter(
        Q(name__icontains=query) |
        Q(serial__icontains=query) |
        Q(inventory__icontains=query)
    )[:10]

    data = [
        {
            "id": t.id,
            "name": t.name,
            "serial": t.serial,
            "inventory": t.inventory,
        }
        for t in texs
    ]

    return JsonResponse({"results": data})


@never_cache
@require_GET
@login_required
def ajax_akt_materials(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    org_id = (request.GET.get("organization") or "").strip()
    dep_id = (request.GET.get("department") or "").strip()
    d1 = (request.GET.get("date1") or "").strip()
    d2 = (request.GET.get("date2") or "").strip()

    if not d1 or not d2:
        return JsonResponse([], safe=False)

    try:
        date1 = timezone.make_aware(datetime.strptime(d1, "%Y-%m-%d"))
        date2 = timezone.make_aware(datetime.strptime(d2, "%Y-%m-%d") + timedelta(days=1))
    except ValueError:
        return JsonResponse([], safe=False)

    # Hozirgi userga bog'langan barcha senderlar
    sender_ids = MaterialUser.objects.filter(
        receiver=employee
    ).values_list("sender_id", flat=True)

    qs = (
        OrderMaterial.objects.filter(
            order__date_finished__gte=date1,
            order__date_finished__lt=date2,
            order__receiver__region=employee.region,
            material__employee_id__in=sender_ids,
        )
        .annotate(
            full_name=Concat(
                F("order__sender__first_name"),
                Value(" "),
                F("order__sender__last_name"),
                Value(" "),
                F("order__sender__father_name"),
                output_field=CharField(),
            ),
            rank_name=F("order__sender__rank__name"),
        )
    )

    if dep_id:
        qs = qs.filter(order__sender__department_id=dep_id)
    elif org_id:
        qs = qs.filter(order__sender__organization_id=org_id)
    else:
        return JsonResponse([], safe=False)

    qs = qs.values(
        "order__id",
        "order__date_finished",
        "order__technics__name",
        "order__technics__serial",
        "material__name",
        "number",
        "material__unit__name",
        "material__price",
        "full_name",
        "rank_name",
    ).order_by("-order__date_finished", "-id")

    return JsonResponse(list(qs), safe=False)


@never_cache
@require_GET
@login_required
def ajax_svod_materials(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    org_id = request.GET.get("organization")
    dep_id = request.GET.get("department")
    d1 = request.GET.get("date1")
    d2 = request.GET.get("date2")

    if not org_id or not d1 or not d2:
        return JsonResponse([], safe=False)

    try:
        date1 = timezone.make_aware(datetime.strptime(d1, "%Y-%m-%d"))
        date2 = timezone.make_aware(datetime.strptime(d2, "%Y-%m-%d") + timedelta(days=1))
    except ValueError:
        return JsonResponse({"error": "Noto'g'ri sana formati"}, status=400)

    # OR mantig'i: o'z materiali BO'LSA HAM, o'z hududiga yopilgan bo'lsa ham
    base_filter = (
        Q(material__employee=employee) |
        Q(order__sender__region=employee.region,order__goal__organization__type="worker")
    )

    common_filters = dict(
        order__date_finished__isnull=False,
        order__date_finished__gte=date1,
        order__date_finished__lt=date2,
        order__sender__organization_id=org_id,
    )

    if dep_id and dep_id.isdigit():
        common_filters["order__sender__department_id"] = dep_id

    dec = DecimalField(max_digits=18, decimal_places=2)
    zero_dec = Value(0, output_field=dec)

    qs = (
        OrderMaterial.objects.filter(base_filter, **common_filters)
        .values(
            "material_id",
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

    rel = (
        OrderMaterial.objects.filter(base_filter, **common_filters)
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
            "order_info": order_info,
            "material__code": item.get("material__code", ""),
        })
    return JsonResponse(data, safe=False)


from collections import OrderedDict
@never_cache
@require_GET
@login_required
def ajax_svod_all_materials(request):
    """
    Bir nechta tashkilot bo'yicha materiallarni:
    Tashkilot -> Hudud -> materiallar tartibida qaytaradi, shuningdek
    shu materiallarni bajargan (order.receiver) barcha xodimlarning
    ro'yxatini ham alohida qaytaradi (dublikatsiz, alifbo tartibida).

    HUDUD CHEKLOVI:
    - Agar foydalanuvchida "main.all_region" ruxsati bo'lsa VA
      "all_regions=1" so'rov parametri yuborilgan bo'lsa -> barcha hududlar.
    - Aks holda (ruxsat yo'q yoki checkbox belgilanmagan) -> faqat
      foydalanuvchining o'z hududi (employee.region).
    """
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    org_ids = [i for i in request.GET.getlist("organizations[]") if i.isdigit()]
    d1 = request.GET.get("date1")
    d2 = request.GET.get("date2")
    all_regions_requested = request.GET.get("all_regions") == "1"

    if not org_ids or not d1 or not d2:
        return JsonResponse({"organizations": [], "employees": []})

    try:
        date1 = timezone.make_aware(datetime.strptime(d1, "%Y-%m-%d"))
        date2 = timezone.make_aware(datetime.strptime(d2, "%Y-%m-%d") + timedelta(days=1))
    except ValueError:
        return JsonResponse({"error": "Noto'g'ri sana formati"}, status=400)

    # Ruxsatni serverda qayta tekshiramiz — clientga ishonmaymiz.
    can_view_all_regions = request.user.has_perm("main.all_region")
    use_all_regions = all_regions_requested and can_view_all_regions

    common_filters = dict(
        order__date_finished__isnull=False,
        order__date_finished__gte=date1,
        order__date_finished__lt=date2,
        order__sender__organization_id__in=org_ids,
        order__goal__organization__type="worker",
    )

    if not use_all_regions:
        if not employee.region_id:
            # Xodimning hududi yo'q bo'lsa, hech narsa qaytarmaymiz.
            return JsonResponse({"organizations": [], "employees": []})
        common_filters["order__sender__region_id"] = employee.region_id

    dec = DecimalField(max_digits=18, decimal_places=2)
    zero_dec = Value(0, output_field=dec)

    qs = (
        OrderMaterial.objects.filter(**common_filters)
        .values(
            "order__sender__organization_id",
            "order__sender__organization__name",
            "order__sender__region_id",
            "order__sender__region__name",
            "material_id",
            "material__code",
            "material__name",
            "material__unit__name",
            "material__price",
        )
        .annotate(total_number=Coalesce(Sum("number"), 0))
        .annotate(
            total_sum=ExpressionWrapper(
                Coalesce(F("material__price"), zero_dec) *
                Cast(Coalesce(F("total_number"), 0), output_field=dec),
                output_field=dec,
            )
        )
        .order_by(
            "order__sender__organization_id",
            "order__sender__region_id",
            "material__code",
            "material__name",
        )
    )

    rel = (
        OrderMaterial.objects.filter(**common_filters)
        .values(
            "material_id",
            "order__sender__organization_id",
            "order__sender__region_id",
            "order_id",
            "order__date_finished",
        )
        .distinct()
    )
    order_map = {}
    for r in rel:
        key = (r["material_id"], r["order__sender__organization_id"], r["order__sender__region_id"])
        dt = r["order__date_finished"]
        dt_str = dt.strftime("%d.%m.%Y") if dt else ""
        txt = f'Akt №{r["order_id"]} ga {dt_str} yil' if dt_str else f'Akt №{r["order_id"]}'
        order_map.setdefault(key, []).append(txt)

    grouped = OrderedDict()
    for item in qs:
        org_key = (item["order__sender__organization_id"], item["order__sender__organization__name"])
        region_key = (item["order__sender__region_id"], item["order__sender__region__name"] or "Noma'lum hudud")

        grouped.setdefault(org_key, OrderedDict())
        grouped[org_key].setdefault(region_key, [])

        key = (item["material_id"], item["order__sender__organization_id"], item["order__sender__region_id"])
        order_info_list = order_map.get(key, [])

        grouped[org_key][region_key].append({
            "material__name": item.get("material__name", ""),
            "material__unit__name": item.get("material__unit__name", ""),
            "total_number": float(item.get("total_number") or 0),
            "material__price": float(item.get("material__price") or 0),
            "total_sum": float(item.get("total_sum") or 0),
            "order_info": order_info_list,
            "material__code": item.get("material__code", ""),
        })

    result = []
    for (org_id, org_name), regions in grouped.items():
        org_block = {"organization_id": org_id, "organization_name": org_name, "regions": []}
        for (region_id, region_name), materials in regions.items():
            org_block["regions"].append({
                "region_id": region_id,
                "region_name": region_name,
                "materials": materials,
            })
        result.append(org_block)

    # ── Ariza bajargan (order.receiver) barcha xodimlar, dublikatsiz ──
    responsible_qs = (
        OrderMaterial.objects.filter(**common_filters)
        .values(
            "order__receiver_id",
            "order__receiver__last_name",
            "order__receiver__first_name",
            "order__receiver__father_name",
            "order__receiver__rank__name",
        )
        .distinct()
    )

    seen_ids = set()
    employees = []
    for r in responsible_qs:
        rid = r.get("order__receiver_id")
        if not rid or rid in seen_ids:
            continue
        seen_ids.add(rid)

        full_name = " ".join(filter(None, [
            r.get("order__receiver__last_name"),
            r.get("order__receiver__first_name"),
            r.get("order__receiver__father_name"),
        ])) or "-"

        employees.append({
            "id": rid,
            "full_name": full_name,
            "rank": r.get("order__receiver__rank__name") or "",
        })

    employees.sort(key=lambda e: e["full_name"])

    return JsonResponse({"organizations": result, "employees": employees})


@never_cache
@require_POST
@login_required
def download_pdf(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        return JsonResponse({"error": "Employee yo'q"}, status=403)

    raw_body = request.POST.get("body_html", "")
    body = sanitize_deed_body(raw_body)

    if not body.strip():
        return JsonResponse({"error": "Hujjat matni bo'sh"}, status=400)

    orientation = request.POST.get("orientation", "Landscape")
    if orientation not in ("Portrait", "Landscape"):
        orientation = "Landscape"

    base_filename = (request.POST.get("filename") or "hujjat").strip()
    base_filename = "".join(
        ch for ch in base_filename if ch.isalnum() or ch in ("_", "-")
    ) or "hujjat"

    try:
        pdf_bytes = html_to_pdf_bytes(body, orientation=orientation)
    except HtmlPdfError as e:
        return JsonResponse({"error": f"PDF yaratilmadi: {e}"}, status=500)
    except Exception as e:
        return JsonResponse({"error": f"Kutilmagan xatolik: {e}"}, status=500)

    filename = f"{base_filename}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    response = FileResponse(
        io.BytesIO(pdf_bytes),
        as_attachment=True,
        filename=filename,
        content_type="application/pdf",
    )
    return response



@never_cache
@require_GET
@login_required
def ajax_reestr_materials(request):
    """
    Tashkilot (majburiy) va hudud (ixtiyoriy) bo'yicha reestr materiallarini
    qaytaradi.

    HUDUD CHEKLOVI:
    - Agar foydalanuvchida "main.all_region" ruxsati bo'lsa, "region"
      parametri orqali istalgan hududni tanlashi (yoki bo'sh qoldirib
      barcha hududlarni ko'rishi) mumkin.
    - Aks holda (ruxsat yo'q) — "region" parametridan qat'i nazar,
      MAJBURAN faqat foydalanuvchining o'z hududi qo'llaniladi
      (frontend'dan kelgan qiymatga ishonilmaydi).
    """
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    org_id = request.GET.get("organization")
    region_id = request.GET.get("region")
    d1 = request.GET.get("date1")
    d2 = request.GET.get("date2")

    if not org_id or not d1 or not d2:
        return JsonResponse([], safe=False)

    try:
        date1 = timezone.make_aware(datetime.strptime(d1, "%Y-%m-%d"))
        date2 = timezone.make_aware(datetime.strptime(d2, "%Y-%m-%d") + timedelta(days=1))
    except ValueError:
        return JsonResponse({"error": "Noto'g'ri sana formati"}, status=400)

    has_full_region = request.user.has_perm("main.all_region")

    common_filters = dict(
        order__date_finished__isnull=False,
        order__date_finished__gte=date1,
        order__date_finished__lt=date2,
        order__sender__organization_id=org_id,
    )

    if has_full_region:
        if region_id and region_id.isdigit():
            common_filters["order__sender__region_id"] = region_id
        # region_id bo'sh bo'lsa — barcha hududlar (cheklovsiz)
    else:
        if not employee.region_id:
            return JsonResponse([], safe=False)
        common_filters["order__sender__region_id"] = employee.region_id

    dec = DecimalField(max_digits=18, decimal_places=2)
    zero_dec = Value(0, output_field=dec)

    qs = (
        OrderMaterial.objects.filter(**common_filters)
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
            "order__sender__region_id",
            "order__sender__region__name",

            "receiver_full_name",
            "order__receiver__rank__name",

            "total_sum",
        )
        .order_by("order__sender__region_id", "material__code", "material__name", "order__id")
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
            "material__price": float(item.get("material__price") or 0),
            "total_sum": float(item.get("total_sum") or 0),

            "sender": (item.get("sender_full_name") or "").strip(),
            "sender_rank": item.get("order__sender__rank__name", ""),
            "department": item.get("order__sender__department__name", ""),
            "region": item.get("order__sender__region__name") or "Noma'lum hudud",

            "receiver": (item.get("receiver_full_name") or "").strip(),
            "receiver_rank": item.get("order__receiver__rank__name", ""),
        })

    return JsonResponse(data, safe=False)


@never_cache
@require_GET
@login_required
def ajax_document_preview(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    dep_id = (request.GET.get("department") or "").strip()
    org_id = (request.GET.get("organization") or "").strip()

    if not dep_id and not org_id:
        return JsonResponse(
            {"error": "Tashkilot yoki bo'lim tanlanmagan"},
            status=400,
        )

    liables = (
        Liable.objects
        .filter(employee=employee, category__isnull=False, contract__isnull=False)
        .select_related("contract", "category")
        .order_by("contract_id")          # ✅ tartib kafolatlanadi
        .values("contract_id", "contract__name", "category_id")
    )

    contract_map = {}
    for row in liables:
        cid   = row["contract_id"]
        cname = row["contract__name"] or f"Shartnoma {cid}"
        if cid not in contract_map:
            contract_map[cid] = {"name": cname, "category_ids": []}
        contract_map[cid]["category_ids"].append(row["category_id"])

    if not contract_map:
        return JsonResponse({"contracts": {}})

    loc_filter = {"department_id": dep_id} if dep_id else {"organization_id": org_id}

    all_category_ids = list({
        cat_id
        for v in contract_map.values()
        for cat_id in v["category_ids"]
    })

    all_technics = (
        Technics.objects
        .filter(is_active=True, **loc_filter)
        .filter(category_id__in=all_category_ids)
        .select_related("category")
        .prefetch_related("structure_set")
    )

    cat_to_technics = defaultdict(list)
    for tex in all_technics:
        cat_to_technics[tex.category_id].append(tex)

    PC_CONTRACT_ID = 1
    contracts_data = {}

    for cid, info in contract_map.items():
        items = []
        seen_ids = set()

        for cat_id in info["category_ids"]:
            for tex in cat_to_technics.get(cat_id, []):
                if tex.id in seen_ids:
                    continue
                seen_ids.add(tex.id)

                item = {
                    "id":            tex.id,
                    "name":          tex.name   or "",
                    "serial":        tex.serial or "",
                    "category_name": tex.category.name if tex.category else "",
                }

                if cid == PC_CONTRACT_ID:
                    item["extra_serials"] = [
                        f"{s['name']}\nSR: {s['serial']}"
                        for s in tex.structure_set.filter(is_active=True).values("name", "serial")
                        if s["serial"]
                    ]

                items.append(item)

        contracts_data[str(cid)] = {
            "contract_id":   cid,
            "contract_name": info["name"],
            "count":         len(items),
            "items":         items,
        }

    return JsonResponse({"contracts": contracts_data})


@require_POST
@login_required
def add_material_to_cart(request):
    employee = getattr(request.user, "employee", None)

    if not employee:
        return JsonResponse({
            "ok": False,
            "message": "Employee topilmadi"
        }, status=403)

    material_id = (request.POST.get("material_id") or "").strip()
    if not material_id.isdigit():
        return JsonResponse({"ok": False, "message": "Noto'g'ri material ID"}, status=400)

    material = get_object_or_404(
        Material,
        id=material_id
    )

    cart_item = OrderMaterial.objects.filter(
        order=None,
        user=employee,
        material=material
    ).first()

    # AGAR BOR BO'LSA O'CHIRAMIZ
    if cart_item:
        cart_item.delete()

        return JsonResponse({
            "ok": True,
            "action": "removed",
            "message": "Savatdan olib tashlandi"
        })

    # AGAR YO'Q BO'LSA QO'SHAMIZ
    OrderMaterial.objects.create(
        order=None,
        user=employee,
        material=material,
        number=1
    )

    return JsonResponse({
        "ok": True,
        "action": "added",
        "message": "Savatga saqlandi"
    })


@require_POST
@login_required
def delete_material_from_cart(request):
    employee = getattr(request.user, "employee", None)

    if not employee:
        return JsonResponse({
            "ok": False,
            "message": "Employee topilmadi"
        }, status=403)

    item_id = (request.POST.get("item_id") or "").strip()

    if not item_id or not item_id.isdigit():
        return JsonResponse({
            "ok": False,
            "message": "ID kelmadi"
        }, status=400)

    item = get_object_or_404(
        OrderMaterial,
        id=item_id,
        order__isnull=True,
        user=employee
    )

    item.delete()

    return JsonResponse({
        "ok": True,
        "message": "Savatdan o‘chirildi"
    })


@require_POST
@csrf_protect
@login_required
@permission_required("main.change_deed", raise_exception=True)
def toggle_user_edit(request, deed_id):
    employee = getattr(request.user, "employee", None)
    if not employee:
        return JsonResponse({"success": False, "error": "Employee yo'q"}, status=403)

    deed = get_object_or_404(Deed, pk=deed_id)

    deed.user_edit = not deed.user_edit
    deed.save(update_fields=["user_edit"])

    return JsonResponse({"success": True, "user_edit": deed.user_edit})