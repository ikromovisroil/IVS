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
        status__in=['approved', 'rejected'],
        sender_seen=False
    ).update(sender_seen=True)

    return JsonResponse({'status': 'ok'})


def order_mark_seen(request):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'unauth'})

    Order.objects.filter(
        receiver__user=request.user,
        status__in=['approved', 'rejected'],
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


def get_employee_files(request):
    emp_id = request.GET.get("employee_id")
    current_emp = getattr(request.user, "employee", None)

    if current_emp is None:
        return JsonResponse({"html": "<p>Bu foydalanuvchi xodim emas</p>"})

    try:
        other_emp = Employee.objects.get(id=int(emp_id))
    except (Employee.DoesNotExist, TypeError, ValueError):
        return JsonResponse({"html": "<p>Xodim topilmadi</p>"})

    deeds = (
        Deed.objects.filter(
            # Men ↔ Tanlangan xodim
            Q(sender=current_emp, receiver=other_emp) |
            Q(sender=other_emp, receiver=current_emp) |

            # Men yoki tanlangan xodim kelishuvchi bo‘lsa
            Q(deedconsent__employee=current_emp,sender=other_emp)|
            Q(deedconsent__employee=other_emp, sender=current_emp)
        )
        .select_related("sender__user", "receiver__user")
        .prefetch_related("deedconsent_set__employee__user")
        .distinct()
        .order_by("-id")
    )

    # 🔥 ROLLNI ANIQLAYMIZ
    for d in deeds:
        if d.sender == current_emp:
            d.user_role = "Yuboruvchi"
        elif d.receiver == current_emp:
            d.user_role = "Qabul qiluvchi"
        elif d.deedconsent_set.filter(employee=current_emp).exists():
            d.user_role = "Kelishuvchi"
        else:
            d.user_role = ""

    html = render_to_string(
        "main/employee_files.html",
        {"deeds": deeds},
        request=request,
    )
    return JsonResponse({"html": html})


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

