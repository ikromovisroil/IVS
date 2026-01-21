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

    # Receiver uchun (Imzolovchi)
    receiver_qs = Employee.objects.filter(
        organization_id=org_id,
        # rol__boss=True
    ).select_related("rank").order_by("last_name", "first_name")

    data = []
    for e in receiver_qs:
        data.append({
            "id": e.id,
            "full_name": e.full_name,
        })

    return JsonResponse({"results": data})

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

    obj = get_object_or_404(Deedconsent, pk=pk)

    if obj.deed.user_id != emp.id:
        raise PermissionDenied

    obj.delete()
    return JsonResponse({"ok": True})

