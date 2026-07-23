from .models import *
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from datetime import datetime, timedelta
from django.db.models import Sum, F, DecimalField, ExpressionWrapper, Value,CharField
from django.db.models.functions import Coalesce, Cast,Concat
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST, require_GET

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

    sender_id = request.GET.get("sender_id")
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

    Order.objects.filter(
        sender=employee,
        status="rejected",
        sender_seen=False,
    ).update(sender_seen=True)

    Order.objects.filter(
        user=employee,
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

    latest_order = (
        Order.objects
        .filter(sender__region=employee.region,goal__organization__type="worker", status="viewed")
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

@never_cache
@require_GET
@login_required
def ajax_load_departments(request):
    org_id = (request.GET.get("organization") or "").strip()
    reg_id = (request.GET.get("region") or "").strip()

    if not org_id or not reg_id:
        return JsonResponse({"results": []})

    qs = Department.objects.filter(
        organization_id=org_id,
        region_id=reg_id
    ).values("id", "name").order_by("id")

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

    # ikkalasi ham bo'lmasa bo'sh
    if not org_id and not dep_id:
        return JsonResponse([], safe=False)

    qs = Employee.objects.select_related("rank")

    if dep_id:
        qs = qs.filter(department_id=dep_id)
    elif org_id:
        qs = qs.filter(organization_id=org_id,region=request.user.employee.region)
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

    if not org_id and not dep_id:
        return JsonResponse([], safe=False)

    qs = Employee.objects.select_related("rank")

    if dep_id:
        qs = qs.filter(Q(department_id=dep_id) | Q(department_id=my_dep_id))
    elif org_id:
        qs = qs.filter(Q(organization_id=org_id) | Q(organization_id=my_dep_id))
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
    reg_id = request.user.employee.region.id

    if not org_id:
        return JsonResponse({"results": []})

    qs = Employee.objects.filter(organization_id=org_id)
    if reg_id:
        qs = qs.filter(region_id=reg_id)

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
        Q(organization_id=org_id, region=my_region_id) |
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
    om = get_object_or_404(
        OrderMaterial.objects.select_related("material", "order"),
        pk=pk
    )

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
        material__employee=employee,
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


@never_cache
@require_GET
@login_required
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
            material__employee=employee,
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
            "material__price": float(item.get("material__price") or 0),
            "total_sum": float(item.get("total_sum") or 0),

            "sender": (item.get("sender_full_name") or "").strip(),
            "sender_rank": item.get("order__sender__rank__name", ""),
            "department": item.get("order__sender__department__name", ""),

            "receiver": (item.get("receiver_full_name") or "").strip(),
            "receiver_rank": item.get("order__receiver__rank__name", ""),
        })

    return JsonResponse(data, safe=False)


from collections import defaultdict
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

    material_id = request.POST.get("material_id")

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

    item_id = request.POST.get("item_id")

    if not item_id:
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