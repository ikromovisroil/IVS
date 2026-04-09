from main.ajax_views import *
from django.db.models import Prefetch
from django.contrib.auth.decorators import login_required
from main.forms import *
from django.core.paginator import Paginator
from decimal import Decimal, InvalidOperation
from main.sso_views import *
from django.db.models import Count, F, ExpressionWrapper
from functools import wraps
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.shortcuts import redirect
from functools import wraps
from django.contrib.auth.decorators import login_required
from itertools import groupby
from django.http import FileResponse, Http404
from django.utils.dateparse import parse_date


def role_required(permission):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            employee = getattr(request.user, "employee", None)
            if not employee:
                raise PermissionDenied("Employee topilmadi")

            role = getattr(employee, "rol", None)
            if not role:
                raise PermissionDenied("Rol biriktirilmagan")

            if not hasattr(role, permission):
                raise PermissionDenied(f"'{permission}' ruxsat maydoni mavjud emas")

            if not getattr(role, permission):
                raise PermissionDenied("Sizda bu amal uchun ruxsat yo‘q")

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator

@never_cache
@require_GET
def error_403(request, exception=None):
    return render(request, "errors/403.html", status=403)

@never_cache
@require_GET
def error_404(request, exception=None):
    return render(request, "errors/404.html", status=404)

@never_cache
@require_GET
def error_500(request):
    return render(request, "errors/500.html", status=500)


@never_cache
@require_GET
def home(request):
    if request.user.is_authenticated:
        return redirect("profil")
    return redirect("login")


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def profil(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    if request.method == "POST":
        emp_form = EmployeeProfileForm(request.POST, instance=employee)
        email_form = UserEmailForm(request.POST, instance=request.user)

        if emp_form.is_valid() and email_form.is_valid():
            with transaction.atomic():
                emp_form.save()
                email_form.save()

            messages.success(request, "Profil muvaffaqiyatli yangilandi")
            return redirect("profil")

        messages.info(request, "Maydonlarda xatolik bor. Qayta tekshiring")
    else:
        emp_form = EmployeeProfileForm(instance=employee)
        email_form = UserEmailForm(instance=request.user)

    return render(request, "main/profil.html", {
        "emp_form": emp_form,
        "email_form": email_form,
        "employee": employee,
    })


@never_cache
@require_GET
@login_required
def contact(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    qs = (
        Deed.objects
        .filter(
            Q(sender_id=employee.id, status_sender="viewed") |
            Q(receiver_id=employee.id, status_receiver="viewed")
        )
        .select_related("user", "sender", "receiver")
        .order_by("-id")
    )

    paginator = Paginator(qs, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)

    context = {
        "deed_receiver": page_obj,
        "page_obj": page_obj,
        "qs_params": params.urlencode(),
    }
    return render(request, "main/contact.html", context)


@never_cache
@require_GET
@login_required
def contact_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    qs = (
        Deed.objects
        .filter(
            Q(sender_id=employee.id, status_sender__in=["approved", "rejected"]) |
            Q(receiver_id=employee.id, status_receiver__in=["approved", "rejected"])
        )
        .select_related("user", "sender", "receiver")
        .order_by("-id")
    )

    paginator = Paginator(qs, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)

    context = {
        "deed_receiver": page_obj,
        "page_obj": page_obj,
        "qs_params": params.urlencode(),
    }
    return render(request, "main/contact_arxiv.html", context)


@never_cache
@require_GET
@login_required
def contact_agrement(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    qs = (
        Deed.objects
        .filter(
            deedconsent__employee_id=employee.id,
            deedconsent__status="viewed"
        )
        .select_related("user", "sender", "receiver")
        .order_by("-id")
    )

    paginator = Paginator(qs, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)

    context = {
        "deed_consent": page_obj,
        "page_obj": page_obj,
        "qs_params": params.urlencode(),
    }
    return render(request, "main/contact_agrement.html", context)


@never_cache
@login_required
def contact_agrement_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    qs = (
        Deed.objects
        .filter(
            deedconsent__employee_id=employee.id,
            deedconsent__status__in=["approved", "rejected"]
        )
        .select_related("user", "sender", "receiver")
        .order_by("-id")
    )

    paginator = Paginator(qs, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)

    context = {
        "deed_consent": page_obj,
        "page_obj": page_obj,
        "qs_params": params.urlencode(),
    }
    return render(request, "main/contact_agrement_arxiv.html", context)


@never_cache
@require_GET
@login_required
@role_required("order")
def contact_user(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    qs = (
        Deed.objects
        .filter(user_id=employee.id)
        .filter(
            Q(receiver__isnull=True, status_sender="viewed") |
            Q(receiver__isnull=False, status_sender="viewed", status_receiver="viewed")
        )
        .select_related("sender", "receiver", "user")
        .order_by("-id")
    )

    paginator = Paginator(qs, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)

    context = {
        "deed_user": page_obj,
        "page_obj": page_obj,
        "qs_params": params.urlencode(),
    }
    return render(request, "main/contact_user.html", context)


@never_cache
@require_GET
@login_required
@role_required("order")
def contact_user_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    qs = (
        Deed.objects
        .filter(user_id=employee.id)
        .filter(
            Q(status_sender__in=["approved", "rejected"]) |
            Q(status_receiver__in=["approved", "rejected"])
        )
        .select_related("sender", "receiver", "user")
        .order_by("-id")
    )

    paginator = Paginator(qs, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)

    context = {
        "deed_user": page_obj,
        "page_obj": page_obj,
        "qs_params": params.urlencode(),
    }
    return render(request, "main/contact_user_arxiv.html", context)


@require_GET
def deed_status(request, code, pk):
    deed = get_object_or_404(Deed, pk=pk, code=code)
    context = {"d": deed}
    return render(request, "main/deed_status.html", context)


def validate_pdf_file(file_field):
    if not file_field:
        return False, "PDF yo‘q"

    try:
        file_path = file_field.path
    except Exception:
        return False, "PDF yo‘li topilmadi"

    if not file_path or not os.path.exists(file_path):
        return False, "PDF topilmadi"

    if not file_path.lower().endswith(".pdf"):
        return False, "PDF noto‘g‘ri"

    if os.path.getsize(file_path) < 1024:
        return False, "PDF buzilgan"

    try:
        PdfReader(file_path)
    except Exception:
        return False, "PDF o‘qilmadi"

    return True, None


@never_cache
@require_POST
@login_required
@transaction.atomic
def deed_action(request, pk):
    emp = getattr(request.user, "employee", None)
    if not emp:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER") or "/"
    action = (request.POST.get("action") or "").strip().lower()
    message = (request.POST.get("message") or "").strip()

    deed = get_object_or_404(
        Deed.objects.select_for_update(),
        pk=pk
    )

    if deed.receiver_id == emp.id:
        role = "receiver"
        current_status = deed.status_receiver
    elif deed.sender_id == emp.id:
        role = "sender"
        current_status = deed.status_sender
    else:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    allowed_actions_from = {"viewed"}
    if current_status not in allowed_actions_from:
        messages.info(request, "Bu dalolatnoma holatida amal bajarib bo‘lmaydi")
        return redirect(back_url)

    if action == "reject":
        now = timezone.now()
        update_fields = ["date_edit"]

        if role == "receiver":
            deed.status_receiver = "rejected"
            deed.message_receiver = message
            update_fields += ["status_receiver", "message_receiver"]
        else:
            deed.status_sender = "rejected"
            deed.message_sender = message
            update_fields += ["status_sender", "message_sender"]

        deed.date_edit = now
        deed.save(update_fields=update_fields)

        messages.success(request, "Dalolatnoma rad etildi")
        return redirect(back_url)

    if action == "approve":
        is_valid_pdf, error_message = validate_pdf_file(deed.file)
        if not is_valid_pdf:
            messages.info(request, error_message)
            return redirect(back_url)

        request.session["PENDING_APPROVE"] = {
            "deed_id": deed.id,
            "role": role,
            "message": message,
            "redirect_url": back_url,
        }
        request.session.modified = True

        return redirect("sso_start_approve")

    messages.info(request, "Noto‘g‘ri amal")
    return redirect(back_url)


@never_cache
@require_http_methods(["GET", "POST"])
@login_required
@role_required("akt")
def deed_edit(request, pk):
    emp_me = getattr(request.user, "employee", None)
    if not emp_me:
        raise PermissionDenied("Employee yo‘q")

    deed = get_object_or_404(Deed, pk=pk)

    if deed.user_id != emp_me.id:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    sender_org_id = deed.sender.organization_id if deed.sender_id else None
    receiver_org_id = deed.receiver.organization_id if deed.receiver_id else None
    my_org_id = emp_me.organization_id if emp_me.organization_id else None

    sender_qs = (
        Employee.objects.filter(
            organization_id=sender_org_id,
            rol__boss=True,
        ).order_by("last_name", "first_name", "father_name")
        if sender_org_id
        else Employee.objects.none()
    )

    receiver_qs = (
        Employee.objects.filter(
            organization_id=receiver_org_id,
            rol__boss=True,
        ).order_by("last_name", "first_name", "father_name")
        if receiver_org_id
        else Employee.objects.none()
    )

    org_ids = [x for x in [sender_org_id, receiver_org_id, my_org_id] if x]
    employee_qs = (
        Employee.objects.filter(organization_id__in=org_ids)
        .select_related("organization", "rol")
        .distinct()
        .order_by("last_name", "first_name", "father_name")
        if org_ids
        else Employee.objects.none()
    )

    selected_agreement_ids = set(
        DeedConsent.objects.filter(deed_id=deed.id).values_list("employee_id", flat=True)
    )

    if request.method == "POST":
        sender_id = (request.POST.get("sender") or "").strip()
        receiver_id = (request.POST.get("receiver") or "").strip()
        body = (request.POST.get("body") or "").strip()
        agreements_ids = request.POST.getlist("agreements[]")

        if not body:
            messages.info(request, "Hujjat matni bo‘sh bo‘lmasin")
            return redirect("deed_edit", pk=deed.pk)

        if not sender_id.isdigit():
            messages.info(request, "Imzolovchi xodim tanlanmadi")
            return redirect("deed_edit", pk=deed.pk)

        new_sender = Employee.objects.filter(
            id=int(sender_id),
            organization_id=sender_org_id,
            rol__boss=True,
        ).first()

        if not new_sender:
            messages.info(request, "Imzolovchi topilmadi yoki ruxsat etilmagan")
            return redirect("deed_edit", pk=deed.pk)

        new_receiver = None
        if deed.receiver_id:
            if not receiver_id.isdigit():
                messages.info(request, "Qabul qiluvchi tanlanmadi")
                return redirect("deed_edit", pk=deed.pk)

            new_receiver = Employee.objects.filter(
                id=int(receiver_id),
                organization_id=receiver_org_id,
                rol__boss=True,
            ).first()

            if not new_receiver:
                messages.info(request, "Qabul qiluvchi topilmadi yoki ruxsat etilmagan")
                return redirect("deed_edit", pk=deed.pk)

        clean_agreement_ids = []
        for x in agreements_ids:
            if str(x).isdigit():
                clean_agreement_ids.append(int(x))

        if clean_agreement_ids:
            valid_agreement_ids = set(
                Employee.objects.filter(
                    id__in=clean_agreement_ids,
                    organization_id__in=org_ids,
                ).values_list("id", flat=True)
            )
            clean_agreement_ids = list(valid_agreement_ids)
        else:
            clean_agreement_ids = []

        try:
            with transaction.atomic():
                deed = Deed.objects.select_for_update().get(pk=deed.pk)

                deed.sender = new_sender
                if deed.receiver_id:
                    deed.receiver = new_receiver
                deed.body = body
                deed.date_edit = timezone.now()

                update_fields = ["sender", "body", "date_edit"]
                if deed.receiver_id:
                    update_fields.append("receiver")

                deed.save(update_fields=update_fields)

                DeedConsent.objects.filter(deed_id=deed.id).delete()

                exclude_ids = {deed.sender_id}
                if deed.receiver_id:
                    exclude_ids.add(deed.receiver_id)

                new_consents = [
                    DeedConsent(deed_id=deed.id, employee_id=e_id)
                    for e_id in clean_agreement_ids
                    if e_id not in exclude_ids
                ]

                if new_consents:
                    DeedConsent.objects.bulk_create(new_consents)

                try:
                    if deed.file:
                        deed.file.delete(save=False)
                except Exception:
                    pass

                pdf_bytes = deed_to_pdf_bytes(deed)
                pdf_bytes = add_text_watermark_pdf_bytes(pdf_bytes, "TASDIQLANMAGAN")

                today_str = timezone.now().strftime("%Y%m%d")
                random_part = secrets.token_urlsafe(8)
                pdf_name = f"akt_{today_str}_{random_part}.pdf"

                deed.file.save(pdf_name, ContentFile(pdf_bytes), save=True)

            messages.success(request, "Hujjat muvaffaqiyatli tahrirlandi")
            return redirect("contact_user")

        except HtmlPdfError as e:
            messages.info(request, f"Hujjat yangilanmadi: {e}")
            return redirect("deed_edit", pk=deed.pk)

        except Exception as e:
            messages.info(request, f"Kutilmagan xatolik: {e}")
            return redirect("deed_edit", pk=deed.pk)

    context = {
        "deed": deed,
        "sender": sender_qs,
        "receiver": receiver_qs,
        "employee": employee_qs,
        "selected_agreement_ids": selected_agreement_ids,
    }
    return render(request, "main/deed_edit.html", context)


@never_cache
@require_POST
@login_required
def deedconsent_action(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER") or "/"

    action = (request.POST.get("action") or "").strip().lower()
    message = (request.POST.get("message") or "").strip()

    if action not in {"approve", "reject"}:
        messages.error(request, "Noto‘g‘ri amal")
        return redirect(back_url)

    try:
        with transaction.atomic():
            consent = get_object_or_404(
                DeedConsent.objects.select_for_update(),
                pk=pk
            )

            if consent.employee_id != employee.id:
                raise PermissionDenied("Sizga ruxsat yo‘q")

            if consent.status != "viewed":
                messages.info(request, "Bu kelishuv allaqachon ko‘rib chiqilgan")
                return redirect(back_url)

            if action == "reject" and not message:
                messages.info(request, "Rad etish uchun izoh yozing")
                return redirect(back_url)

            consent.status = "approved" if action == "approve" else "rejected"
            consent.message = message
            consent.date_edit = timezone.now()
            consent.save(update_fields=["status", "message", "date_edit"])

    except PermissionDenied:
        raise
    except Exception as e:
        messages.info(request, f"Kutilmagan xatolik: {e}")
        return redirect(back_url)

    if action == "approve":
        messages.success(request, "Hujjat muvaffaqiyatli kelishildi")
    else:
        messages.success(request, "Hujjat rad etildi")

    return redirect(back_url)



@never_cache
@require_GET
@login_required
@role_required("technics")
def barn_tex(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    def to_int(v):
        v = (v or "").strip()
        if not v:
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    organization_id = to_int(request.GET.get("organization"))
    department_id   = to_int(request.GET.get("department"))
    directorate_id  = to_int(request.GET.get("directorate"))
    division_id     = to_int(request.GET.get("division"))
    category_id     = to_int(request.GET.get("category"))
    group_id        = to_int(request.GET.get("groups"))   # ✅ shu joy muhim
    status          = (request.GET.get("status") or "").strip() or None
    name            = (request.GET.get("name") or "").strip() or None
    page_number     = request.GET.get("page", 1)

    if name:
        name = name[:120]

    has_filter = bool(
        organization_id or department_id or directorate_id or division_id or
        status or category_id or group_id or name
    )

    organizations = Organization.objects.only("id", "name").order_by("id")
    if not employee.rol.full:
        organizations = organizations.filter(id=employee.organization_id)

    groups = Group.objects.only("id", "name")
    technics_form = TechnicsForm()

    departments = Department.objects.none()
    if organization_id:
        departments = Department.objects.filter(
            organization_id=organization_id
        ).only("id", "name")

    directorates = Directorate.objects.none()
    if department_id:
        directorates = Directorate.objects.filter(
            department_id=department_id
        ).only("id", "name")

    divisions = Division.objects.none()
    if directorate_id:
        divisions = Division.objects.filter(
            directorate_id=directorate_id
        ).only("id", "name")

    categories = Category.objects.none()
    if group_id:
        categories = Category.objects.filter(
            group_id=group_id
        ).only("id", "name")

    params = request.GET.copy()
    params.pop("page", None)
    qs_params = params.urlencode()

    if not has_filter:
        empty_page = Paginator([], 50).get_page(page_number)
        return render(request, "main/barn_tex.html", {
            "organizations": organizations,
            "groups": groups,
            "categories": categories,
            "technics_form": technics_form,
            "departments": departments,
            "directorates": directorates,
            "divisions": divisions,
            "selected_org": organization_id,
            "selected_dep": department_id,
            "selected_dir": directorate_id,
            "selected_div": division_id,
            "selected_group": group_id,
            "selected_category": category_id,
            "page_obj": empty_page,
            "grouped_technics": [],
            "qs_params": qs_params,
            "extratex": Structure.objects.none(),
            "total_count": 0,
        })

    base_qs = Technics.objects.filter(is_active=True)

    if organization_id:
        base_qs = base_qs.filter(organization_id=organization_id)
    if department_id:
        base_qs = base_qs.filter(department_id=department_id)
    if directorate_id:
        base_qs = base_qs.filter(directorate_id=directorate_id)
    if division_id:
        base_qs = base_qs.filter(division_id=division_id)
    if status:
        base_qs = base_qs.filter(status=status)
    if group_id:
        base_qs = base_qs.filter(group_id=group_id)   # ✅ group filter shu bo‘lishi kerak
    if category_id:
        base_qs = base_qs.filter(category_id=category_id)

    if name:
        words = [w for w in name.split() if w]
        if words:
            q = Q()
            for w in words:
                q &= (
                    Q(employee__last_name__icontains=w) |
                    Q(employee__first_name__icontains=w) |
                    Q(employee__father_name__icontains=w) |
                    Q(name__icontains=w) |
                    Q(inventory__icontains=w) |
                    Q(serial__icontains=w) |
                    Q(mac__icontains=w) |
                    Q(ip__icontains=w)
                )
            base_qs = base_qs.filter(q)

    total_count = base_qs.count()

    emp_ids_qs = (
        base_qs.order_by("employee_id")
        .values_list("employee_id", flat=True)
        .distinct()
    )

    paginator = Paginator(emp_ids_qs, 50)
    page_obj = paginator.get_page(page_number)

    page_emp_ids = list(page_obj.object_list)
    include_null = any(e is None for e in page_emp_ids)
    page_emp_ids_no_null = [e for e in page_emp_ids if e is not None]

    structure_prefetch = Prefetch(
        "structure_set",
        queryset=Structure.objects.select_related("category").only(
            "id", "name", "inventory", "serial", "parametr", "year", "price",
            "category__id", "category__name"
        ).order_by("id")
    )

    page_tech_qs = (
        base_qs
        .filter(
            Q(employee_id__in=page_emp_ids_no_null) |
            (Q(employee__isnull=True) if include_null else Q(pk__in=[]))
        )
        .select_related(
            "organization", "department", "directorate", "division", "category", "employee"
        )
        .prefetch_related(structure_prefetch)
        .only(
            "id", "name", "parametr", "inventory", "serial", "ip", "mac",
            "status", "year", "price", "employee_id",
            "organization__id", "organization__name",
            "department__id", "department__name",
            "directorate__id", "directorate__name",
            "division__id", "division__name",
            "category__id", "category__name",
            "employee__id", "employee__first_name", "employee__last_name", "employee__father_name",
        )
        .order_by("employee_id", "id")
    )

    grouped_technics = []
    for emp_id, items in groupby(page_tech_qs, key=lambda t: t.employee_id):
        items_list = list(items)
        emp_obj = items_list[0].employee
        grouped_technics.append((emp_obj, items_list))

    extratex = Structure.objects.none()
    if organization_id:
        extratex = (
            Structure.objects
            .filter(organization_id=organization_id, status="free", is_active=True)
            .only("id", "name", "inventory", "serial")
        )

    return render(request, "main/barn_tex.html", {
        "organizations": organizations,
        "groups": groups,
        "categories": categories,
        "technics_form": technics_form,
        "departments": departments,
        "directorates": directorates,
        "divisions": divisions,
        "selected_org": organization_id,
        "selected_dep": department_id,
        "selected_dir": directorate_id,
        "selected_div": division_id,
        "selected_group": group_id,
        "selected_category": category_id,
        "page_obj": page_obj,
        "grouped_technics": grouped_technics,
        "qs_params": qs_params,
        "extratex": extratex,
        "total_count": total_count,
    })


@never_cache
@require_POST
@login_required
@role_required("technics_edit")
def technics_create(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    if employee.roll__full:
        messages.info(request, "Sizga ruxsat yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")
    form = TechnicsForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Uskuna qo‘shildi")
    else:
        messages.info(request, f"Xatolik: {form.errors}")
    return redirect(back_url)


@never_cache
@require_POST
@login_required
@role_required("technics_edit")
@transaction.atomic
def technics_delete(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")
    tex_id = request.POST.get("texnika_id")

    try:
        tex = Technics.objects.select_for_update().get(pk=int(tex_id))
    except (Technics.DoesNotExist, TypeError, ValueError):
        messages.info(request, "Uskuna topilmadi")
        return redirect(back_url)

    if not getattr(employee.rol, "full", False) and tex.organization_id != employee.organization_id:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    if not tex.is_active:
        messages.info(request, "Uskuna allaqachon o‘chirilgan")
        return redirect(back_url)

    tex.is_active = False
    tex.save(update_fields=["is_active"])

    messages.success(request, "Uskuna muvaffaqiyatli o‘chirildi")
    return redirect(back_url)


@never_cache
@require_POST
@login_required
@role_required("technics_edit")
@transaction.atomic
def technics_attach(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")

    tex_id = (request.POST.get("texnika_id") or "").strip()
    dep_id = (request.POST.get("department_id") or "").strip()
    dir_id = (request.POST.get("directorate_id") or "").strip()
    div_id = (request.POST.get("division_id") or "").strip()
    emp_id = (request.POST.get("employee_id") or "").strip()

    if not tex_id.isdigit():
        messages.info(request, "Uskuna topilmadi")
        return redirect(back_url)

    if dep_id and not dep_id.isdigit():
        messages.info(request, "Bo‘lim noto‘g‘ri tanlandi")
        return redirect(back_url)

    if dir_id and not dir_id.isdigit():
        messages.info(request, "Boshqarma noto‘g‘ri tanlandi")
        return redirect(back_url)

    if div_id and not div_id.isdigit():
        messages.info(request, "Bo‘linma noto‘g‘ri tanlandi")
        return redirect(back_url)

    if emp_id and not emp_id.isdigit():
        messages.info(request, "Xodim noto‘g‘ri tanlandi")
        return redirect(back_url)

    tex = get_object_or_404(Technics.objects.select_for_update(), id=int(tex_id))

    if not getattr(employee.rol, "full", False) and tex.organization_id != employee.organization_id:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    if emp_id:
        emp = get_object_or_404(
            Employee.objects.select_related("organization", "region"),
            id=int(emp_id)
        )

        tex.employee = emp
        tex.department = None
        tex.directorate = None
        tex.division = None
        tex.status = "active"

        update_fields = ["employee", "department", "directorate", "division", "status"]
        if hasattr(tex, "date_edit"):
            update_fields.append("date_edit")

        tex.save(update_fields=update_fields)
        messages.success(request, "Uskuna xodimga biriktirildi")
        return redirect(back_url)

    if dep_id or dir_id or div_id:
        department_obj = None
        directorate_obj = None
        division_obj = None

        if dep_id:
            department_obj = get_object_or_404(Department, id=int(dep_id))

        if dir_id:
            directorate_obj = get_object_or_404(Directorate, id=int(dir_id))
            if department_obj and directorate_obj.department_id != department_obj.id:
                messages.info(request, "Boshqarma tanlangan bo‘limga tegishli emas")
                return redirect(back_url)

        if div_id:
            division_obj = get_object_or_404(Division, id=int(div_id))
            if directorate_obj and division_obj.directorate_id != directorate_obj.id:
                messages.info(request, "Bo‘linma tanlangan boshqarmaga tegishli emas")
                return redirect(back_url)

        tex.employee = None
        tex.department = department_obj
        tex.directorate = directorate_obj
        tex.division = division_obj
        tex.status = "active"

        update_fields = ["employee", "department", "directorate", "division", "status"]
        if hasattr(tex, "date_edit"):
            update_fields.append("date_edit")

        tex.save(update_fields=update_fields)
        messages.success(request, "Uskuna strukturaga biriktirildi")
        return redirect(back_url)

    tex.employee = None
    tex.department = None
    tex.directorate = None
    tex.division = None
    tex.status = "free"

    update_fields = ["employee", "department", "directorate", "division", "status"]
    if hasattr(tex, "date_edit"):
        update_fields.append("date_edit")

    tex.save(update_fields=update_fields)
    messages.success(request, "Uskuna bo‘shatildi")
    return redirect(back_url)


@never_cache
@require_POST
@login_required
@role_required("technics_edit")
@transaction.atomic
def technics_update(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")
    tex = get_object_or_404(Technics, pk=pk)

    if not getattr(employee.rol, "full", False) and tex.organization_id != employee.organization_id:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    category_id = (request.POST.get("category") or "").strip()
    organization_id = (request.POST.get("organization") or "").strip()

    # FK lar
    if category_id:
        if not category_id.isdigit():
            messages.info(request, "Kategoriya noto‘g‘ri")
            return redirect(back_url)
        tex.category = get_object_or_404(Category, pk=int(category_id))
    else:
        tex.category = None

    if organization_id:
        if not organization_id.isdigit():
            messages.info(request, "Tashkilot noto‘g‘ri")
            return redirect(back_url)
        tex.organization = get_object_or_404(Organization, pk=int(organization_id))
    else:
        tex.organization = None

    # Oddiy maydonlar
    tex.name = (request.POST.get("name") or "").strip()
    tex.parametr = (request.POST.get("parametr") or "").strip()
    tex.inventory = (request.POST.get("inventory") or "").strip()
    tex.serial = (request.POST.get("serial") or "").strip()
    tex.mac = (request.POST.get("mac") or "").strip()
    tex.ip = (request.POST.get("ip") or "").strip()
    tex.year = (request.POST.get("year") or "").strip()

    # 💰 Price: 14.45 yoki 14,45 ni qabul qiladi
    raw_price = (request.POST.get("price") or "").strip().replace(" ", "")
    raw_price = raw_price.replace(",", ".")  # 14,45 -> 14.45

    try:
        tex.price = Decimal(raw_price) if raw_price else Decimal("0")
        if tex.price < 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        messages.info(request, "Narx noto‘g‘ri kiritildi (misol: 14.45 yoki 14,45)")
        return redirect(back_url)

    # 💾 Minimal saqlash
    tex.save(update_fields=[
        "category", "organization",
        "name", "parametr", "inventory", "serial", "mac", "ip", "year", "price"
    ])

    messages.success(request, "Uskuna tahrirlandi!")
    return redirect(back_url)


@never_cache
@require_GET
@login_required
def technics_download(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    tex = get_object_or_404(Technics, pk=pk, is_active=True)

    # 🔐 organization check
    if not getattr(employee.rol, "full", False) and tex.organization_id != employee.organization_id:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    if not tex.qr_code:
        raise Http404("Fayl topilmadi")

    file = tex.qr_code.open("rb")

    return FileResponse(
        file,
        as_attachment=True,
        filename=tex.qr_code.name.split("/")[-1]
    )


@never_cache
@require_GET
@login_required
@role_required("technics")
def extra_tex(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    status = (request.GET.get("status") or "").strip()
    organization_id = (request.GET.get("organization") or "").strip()
    category_id = (request.GET.get("category") or "").strip()
    name = (request.GET.get("name") or "").strip()
    page_number = request.GET.get("page", 1)

    organizations = Organization.objects.only("id", "name")
    if not employee.rol.full:
        organizations = organizations.filter(id=employee.organization_id)

    has_filter = bool(category_id or status or organization_id or name)

    if not has_filter:
        qs = Structure.objects.none()
        page_obj = Paginator(qs, 50).get_page(page_number)

        params = request.GET.copy()
        params.pop("page", None)

        return render(request, "main/extra_tex.html", {
            "organizations": organizations,
            "categories": Structure.objects.only("id", "name"),
            "technics_form": ExtraTechnicsForm(),

            "page_obj": page_obj,
            "technics": page_obj.object_list,
            "qs_params": params.urlencode(),
            "row_start": 0,

            "total_count": 0,
        })

    # ✅ Filter bor bo‘lsa — query ishlaydi
    qs = (
        Structure.objects.filter(is_active=True)
        .select_related("organization")
        .order_by("-id")
    )

    if organization_id:
        qs = qs.filter(organization_id=organization_id)
    if status:
        qs = qs.filter(status=status)
    if category_id:
        qs = qs.filter(category=category_id)

    if name:
        qs = qs.filter(
            Q(name__icontains=name) |
            Q(inventory__icontains=name) |
            Q(serial__icontains=name) |
            Q(year__icontains=name)
        )

    # ✅ countlar faqat filter bo‘lganda
    total_count = qs.count()

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)

    context = {
        "organizations": organizations,
        "categories": StructureCategory.objects.only("id", "name"),
        "technics_form": ExtraTechnicsForm(),

        "page_obj": page_obj,
        "technics": page_obj.object_list,
        "qs_params": params.urlencode(),
        "row_start": page_obj.start_index() if total_count else 0,

        "total_count": total_count,
    }
    return render(request, "main/extra_tex.html", context)


@never_cache
@require_POST
@login_required
@role_required("technics_edit")
def extra_tex_create(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")

    form = ExtraTechnicsForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Texnika qo‘shildi")
    else:
        messages.error(request, "Maʼlumotlarda xatolik bor")
    return redirect(back_url)


@never_cache
@require_POST
@login_required
@role_required("technics_edit")
@transaction.atomic
def extra_tex_delete(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")
    tex_id = request.POST.get("texnika_id")

    try:
        tex = Structure.objects.select_for_update().get(pk=int(tex_id))
    except (Structure.DoesNotExist, TypeError, ValueError):
        messages.info(request, "Texnika topilmadi")
        return redirect(back_url)

    if not getattr(employee.rol, "full", False) and tex.organization_id != employee.organization_id:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    if not tex.is_active:
        messages.info(request, "Texnika allaqachon o‘chirilgan")
        return redirect(back_url)

    tex.is_active = False
    tex.save(update_fields=["is_active"])

    messages.success(request, "Texnika muvaffaqiyatli o‘chirildi")
    return redirect(back_url)


@never_cache
@require_POST
@login_required
@role_required("technics_edit")
@transaction.atomic
def extra_tex_update(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER") or "/"

    tex = get_object_or_404(Structure.objects.select_for_update(),pk=pk,is_active=True)

    if not getattr(employee.rol, "full", False) and tex.organization_id != employee.organization_id:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    organization_id = (request.POST.get("organization") or "").strip()
    category_id = (request.POST.get("category") or "").strip()

    # organization
    if organization_id:
        if not organization_id.isdigit():
            messages.info(request, "Tashkilot noto‘g‘ri")
            return redirect(back_url)
        tex.organization = get_object_or_404(Organization, pk=int(organization_id))
    else:
        tex.organization = None

    # category
    if category_id:
        if not category_id.isdigit():
            messages.info(request, "Kategoriya noto‘g‘ri")
            return redirect(back_url)
        tex.category = get_object_or_404(StructureCategory, pk=int(category_id))
    else:
        tex.category = None

    # oddiy maydonlar
    tex.name = (request.POST.get("name") or "").strip()
    tex.parametr = (request.POST.get("parametr") or "").strip()
    tex.inventory = (request.POST.get("inventory") or "").strip()
    tex.serial = (request.POST.get("serial") or "").strip()

    raw_year = (request.POST.get("year") or "").strip()
    tex.year = raw_year if raw_year else None

    # price
    raw_price = (request.POST.get("price") or "").strip().replace(" ", "")
    raw_price = raw_price.replace(",", ".")

    try:
        tex.price = Decimal(raw_price) if raw_price else Decimal("0")
        if tex.price < 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        messages.error(request, "Narx noto‘g‘ri kiritildi. Misol: 14.45 yoki 14,45")
        return redirect(back_url)

    if not tex.name:
        messages.error(request, "Nomi bo‘sh bo‘lishi mumkin emas")
        return redirect(back_url)

    tex.save(update_fields=[
        "organization",
        "category",
        "name",
        "parametr",
        "inventory",
        "serial",
        "year",
        "price",
    ])

    messages.success(request, "Texnika tahrirlandi!")
    return redirect(back_url)


@never_cache
@require_POST
@login_required
@role_required("technics_edit")
@transaction.atomic
def extra_tex_attach(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    texnika_id = (request.POST.get("texnika_id") or "").strip()
    extra_tex_id = (request.POST.get("extra_tex_id") or "").strip()

    if not texnika_id or not extra_tex_id:
        messages.info(request, "Tanlash majburiy (texnika va qo‘shimcha texnika).")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    # obyektlarni olish
    tex = get_object_or_404(
        Technics.objects.select_for_update(),
        pk=int(texnika_id), is_active=True,
    )

    extra = get_object_or_404(
        Structure.objects.select_for_update(),
        pk=int(extra_tex_id), is_active=True,
    )

    if not getattr(employee.rol, "full", False) and tex.organization_id != employee.organization_id:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    if extra.technics_id:
        messages.info(request, "Bu qo‘shimcha texnika allaqachon biriktirilgan.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    # biriktirish
    extra.technics = tex
    extra.status = "active"
    extra.save(update_fields=["technics", "status"])  # <-- MUHIM

    messages.success(request, "Qo‘shimcha texnika muvaffaqiyatli biriktirildi.")
    return redirect(request.META.get("HTTP_REFERER", "/"))


@never_cache
@require_POST
@login_required
@role_required("technics_edit")
@transaction.atomic
def extra_tex_detach(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER") or "/"

    texnika_id = (request.POST.get("texnika_id") or "").strip()
    extra_tex_id = (request.POST.get("extra_tex_id") or "").strip()

    if not texnika_id or not extra_tex_id:
        messages.info(request, "Tanlash majburiy (texnika va qo‘shimcha texnika).")
        return redirect(back_url)

    if not texnika_id.isdigit() or not extra_tex_id.isdigit():
        messages.info(request, "Noto‘g‘ri ID yuborildi")
        return redirect(back_url)

    tex = get_object_or_404(
        Technics.objects.select_for_update().only("id", "organization_id", "is_active"),
        pk=int(texnika_id),
        is_active=True,
    )

    extra = get_object_or_404(
        Structure.objects.select_for_update().only(
            "id", "organization_id", "technics_id", "status", "is_active"
        ),
        pk=int(extra_tex_id),
        is_active=True,
    )

    # 🔐 permission
    if not getattr(employee.rol, "full", False) and tex.organization_id != employee.organization_id:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    # 🔐 organization check
    if extra.organization_id != tex.organization_id:
        messages.info(request, "Qo‘shimcha texnika boshqa tashkilotga tegishli")
        return redirect(back_url)

    # 🔐 MUHIM: aynan shu texnikaga tegishli bo‘lishi kerak
    if extra.technics_id != tex.id:
        messages.info(request, "Bu qo‘shimcha texnika ushbu uskunaga tegishli emas")
        return redirect(back_url)

    if not extra.technics_id:
        messages.info(request, "Bu qo‘shimcha texnika allaqachon bo‘sh")
        return redirect(back_url)

    extra.technics = None
    extra.status = "free"
    extra.save(update_fields=["technics", "status"])

    messages.success(request, "Qo‘shimcha texnika bekor qilindi.")
    return redirect(back_url)


@never_cache
@require_GET
@login_required
@role_required("material")
def barn_mat(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    category_id = (request.GET.get("category") or "").strip()
    unit_id = (request.GET.get("unit") or "").strip()
    emp_id = (request.GET.get("employee") or "").strip()
    status = (request.GET.get("status") or "").strip()
    name = (request.GET.get("name") or "").strip()
    page_number = request.GET.get("page", 1)

    has_filter = bool(category_id or unit_id or emp_id or status or name)

    # filter bo‘lmasa bo‘sh ko‘rsatamiz
    if not has_filter:
        qs = Material.objects.none()
        page_obj = Paginator(qs, 50).get_page(page_number)

        params = request.GET.copy()
        params.pop("page", None)

        return render(request, "main/barn_mat.html", {
            "employees_boss": Employee.objects.filter(rol__shop=True),
            "unit": Unit.objects.all(),
            "page_obj": page_obj,
            "material": page_obj.object_list,
            "material_form": MaterialForm(),
            "qs_params": params.urlencode(),
            "row_start": 0,
            "total_count": 0,
            "total_suma": 0,
        })

    qs = (
        Material.objects.filter(
            is_active=True,
            organization=employee.organization
        )
        .select_related("employee", "category", "unit")
        .annotate(
            total_sum=ExpressionWrapper(
                F("number") * F("price"),
                output_field=DecimalField(max_digits=18, decimal_places=2)
            )
        )
    )

    if category_id:
        qs = qs.filter(category_id=int(category_id))

    if unit_id:
        qs = qs.filter(unit_id=int(unit_id))

    if status:
        qs = qs.filter(status=status)

    if emp_id:
        qs = qs.filter(employee_id=int(emp_id))

    if name:
        qs = qs.filter(
            Q(name__icontains=name) |
            Q(code__icontains=name)
        )

    total_count = qs.count()
    total_suma = qs.aggregate(s=Sum("total_sum"))["s"] or 0

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)
    qs_params = params.urlencode()

    context = {
        "employees_boss": Employee.objects.filter(rol__client=False, rol__boss=True),
        "unit": Unit.objects.all(),
        "page_obj": page_obj,
        "material": page_obj.object_list,
        "material_form": MaterialForm(),
        "qs_params": qs_params,
        "row_start": page_obj.start_index() if total_count else 0,
        "total_count": total_count,
        "total_suma": total_suma,
    }
    return render(request, "main/barn_mat.html", context)


@never_cache
@require_POST
@login_required
@role_required("material_edit")
def material_create(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")
    form = MaterialForm(request.POST)
    if form.is_valid():
        material = form.save(commit=False)
        material.organization = employee.organization
        material.save()
        messages.success(request, "Material qo‘shildi!")
    else:
        messages.info(request, "Maʼlumotlarda xatolik bor. Maydonlarni tekshirib qayta kiriting.")
    return redirect(back_url)


@never_cache
@require_POST
@login_required
@role_required("material_edit")
def material_update(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")
    mat = get_object_or_404(Material, pk=pk)

    if mat.organization_id != employee.organization_id:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    category_id = (request.POST.get("category") or "").strip()
    unit_id = (request.POST.get("unit") or "").strip()

    # unit
    if unit_id:
        if not unit_id.isdigit():
            messages.info(request, "Birligi noto‘g‘ri tanlangan")
            return redirect(back_url)
        mat.unit = get_object_or_404(Unit, pk=int(unit_id))
    else:
        mat.unit = None

    mat.name = (request.POST.get("name") or "").strip()
    mat.code = (request.POST.get("code") or "").strip()

    if not mat.name:
        messages.info(request, "Nomi kiritilishi shart")
        return redirect(back_url)

    if not mat.code:
        messages.info(request, "1C kodi kiritilishi shart")
        return redirect(back_url)

    # number
    raw_number = (request.POST.get("number") or "").strip()
    try:
        mat.number = int(raw_number)
        if mat.number < 0:
            raise ValueError
    except (TypeError, ValueError):
        messages.error(request, "Soni noto‘g‘ri kiritildi")
        return redirect(back_url)

    # price
    raw_price = (request.POST.get("price") or "").strip().replace(" ", "").replace(",", ".")
    try:
        mat.price = Decimal(raw_price) if raw_price else Decimal("0")
        if mat.price < 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        messages.info(request, "Narx noto‘g‘ri kiritildi. Masalan: 14.45 yoki 14,45")
        return redirect(back_url)

    mat.save(update_fields=["category", "unit", "name", "code", "number", "price"])
    messages.success(request, "Material tahrirlandi!")
    return redirect(back_url)


@never_cache
@require_POST
@login_required
@role_required("material_edit")
@transaction.atomic
def material_attach(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")

    material_id = (request.POST.get("material_id") or "").strip()
    employee_id = (request.POST.get("employee_id") or "").strip()
    give_number = (request.POST.get("give_number") or "").strip()

    # id lar validatsiya
    if not material_id.isdigit() or not employee_id.isdigit():
        messages.error(request, "Material yoki xodim noto‘g‘ri tanlandi")
        return redirect(back_url)

    # son validatsiya
    try:
        give_number_int = int(give_number)
        if give_number_int <= 0:
            raise ValueError
    except (TypeError, ValueError):
        messages.error(request, "Soni noto‘g‘ri kiritildi")
        return redirect(back_url)

    # 🔒 Ombordagi materialni lock qilamiz
    src = get_object_or_404(
        Material.objects.select_for_update(),
        id=int(material_id)
    )
    if src.organization_id != employee.organization_id:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    emp = get_object_or_404(Employee, id=int(employee_id))

    src_qty = int(src.number or 0)
    if src_qty < give_number_int:
        messages.error(request, f"Omborda yetarli material yo‘q (bor: {src_qty})")
        return redirect(back_url)

    # dst ni aniqlash: code bo‘lsa code, bo‘lmasa name
    dst_filter = {"employee_id": emp.id}
    if (src.code or "").strip():
        dst_filter["code"] = src.code
    else:
        dst_filter["name"] = src.name

    # 🔒 dst ni ham lock bilan olamiz (bor bo‘lsa)
    dst = (
        Material.objects
        .select_for_update()
        .filter(**dst_filter)
        .first()
    )

    if dst:
        # mavjud bo‘lsa qo‘shamiz
        dst.number = int(dst.number or 0) + give_number_int

        # price/unit bo‘sh bo‘lsa src dan ko‘chirib qo‘yamiz
        if (dst.price in [None, 0, "0"]) and src.price not in [None, 0, "0"]:
            dst.price = src.price
        if not (dst.unit or "").strip() and (src.unit or "").strip():
            dst.unit = src.unit

        # status active bo‘lsin (ixtiyoriy)
        if hasattr(dst, "status") and dst.status != "active":
            dst.status = "active"

        save_fields = ["number"]
        if "price" in [f.name for f in dst._meta.fields]:
            save_fields += ["price"]
        if "unit" in [f.name for f in dst._meta.fields]:
            save_fields += ["unit"]
        if "status" in [f.name for f in dst._meta.fields]:
            save_fields += ["status"]

        dst.save(update_fields=list(set(save_fields)))
    else:
        # yo‘q bo‘lsa yaratamiz
        Material.objects.create(
            employee=emp,
            status="active",
            name=src.name,
            code=src.code,
            number=give_number_int,
            unit=src.unit,
            price=src.price,
            year=getattr(src, "year", None),
        )

    # Ombordan ayiramiz
    src.number = src_qty - give_number_int
    src.save(update_fields=["number"])

    messages.success(request, "Material biriktirildi")
    return redirect(back_url)


@never_cache
@require_POST
@login_required
@role_required("material_edit")
@transaction.atomic
def material_delete(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER") or "/"
    material_id = (request.POST.get("material_id") or "").strip()

    try:
        mat = (
            Material.objects
            .select_for_update()
            .only("id", "organization_id", "is_active")
            .get(pk=int(material_id))
        )
    except Material.DoesNotExist:
        messages.info(request, "Material topilmadi")
        return redirect(back_url)

    # 🔐 eng muhim check
    if mat.organization_id != employee.organization_id:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    if not mat.is_active:
        messages.info(request, "Material allaqachon o‘chirilgan")
        return redirect(back_url)

    mat.is_active = False
    mat.save(update_fields=["is_active"])

    messages.success(request, "Material muvaffaqiyatli o‘chirildi")
    return redirect(back_url)


@never_cache
@require_GET
@login_required
@role_required("akt")
def document_get(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    liable = Liable.objects.filter(employee=employee).select_related("contract").distinct("contract")

    context = {
        "liable": liable,
        "organizations": Organization.objects.only("id", "name").order_by("id"),
        "emp_bos_sender": Employee.objects.filter(department_id=283),
    }
    return render(request, "main/document.html", context)


@never_cache
@require_POST
@login_required
@role_required("akt")
@transaction.atomic
def document_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")
    # formdan keladiganlar
    sender_id = (request.POST.get("sender") or "").strip()
    receiver_id = (request.POST.get("receiver") or "").strip()
    message = (request.POST.get("message") or "").strip() or None
    agreements = request.POST.getlist("agreements[]")
    body = request.POST.get("body") or ""

    # sender obyekt
    receiver = Employee.objects.filter(id=receiver_id).first() if receiver_id.isdigit() else None
    sender = Employee.objects.filter(id=sender_id).first() if sender_id.isdigit() else None
    if not sender:
        messages.info(request, "Imzolovchi xodim tanlanmadi")
        return redirect("akt_get")

    if not body.strip():
        messages.info(request, "Hujjat matni (body) bo‘sh bo‘lmasin")
        return redirect("akt_get")

    # ✅ Deed yaratamiz
    deed = Deed.objects.create(
        sender=sender,  # FK obyekt
        receiver=receiver,  # FK obyekt
        user=employee,  # FK obyekt
        message_user=message,
        body=body,
        file_type=True,
    )

    # ✅ PDF yaratib deed.file ga saqlaymiz
    try:
        pdf_bytes = deed_to_pdf_bytes(deed)
        wm_text = "TASDIQLANMAGAN"
        pdf_bytes = add_text_watermark_pdf_bytes(pdf_bytes, wm_text)
        today_str = timezone.now().strftime("%Y%m%d")
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        random_part = ''.join(secrets.choice(alphabet) for _ in range(6))
        pdf_name = f"akt_{today_str}_{random_part}.pdf"
        deed.file.save(pdf_name, ContentFile(pdf_bytes), save=True)

    except HtmlPdfError as e:
        messages.info(request, f"PDF yaratilmadi: {e}")

    # ✅ kelishuvchilar IDs tozalash
    ids = []
    for x in (agreements or []):
        x = (x or "").strip()
        if x.isdigit():
            ids.append(int(x))
    ids = list(set(ids))  # uniq

    # ✅ sender va hozirgi employee’ni exclude
    exclude_ids = {receiver.id, sender.id}
    ids = [i for i in ids if i not in exclude_ids]

    # ✅ DeedConsent bulk_create
    if ids:
        emps = Employee.objects.filter(id__in=ids).only("id")
        objs = [DeedConsent(deed=deed, employee=e, status="viewed") for e in emps]
        DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

    messages.success(request, "Imzolashga yuborildi")
    return redirect("contact_user")



@never_cache
@require_GET
@login_required
@role_required("akt")
def akt_get(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    context = {
        "organizations": Organization.objects.only("id", "name").order_by("id"),
    }
    return render(request, "main/akt.html", context)



@never_cache
@require_POST
@login_required
@role_required("akt")
@transaction.atomic
def akt_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")
    # formdan keladiganlar
    sender_id = (request.POST.get("sender") or "").strip()
    message = (request.POST.get("message") or "").strip() or None
    agreements = request.POST.getlist("agreements[]")
    body = request.POST.get("body") or ""

    # sender obyekt
    sender = Employee.objects.filter(id=sender_id).first() if sender_id.isdigit() else None
    if not sender:
        messages.info(request, "Imzolovchi xodim tanlanmadi")
        return redirect("akt_get")

    if not body.strip():
        messages.info(request, "Hujjat matni (body) bo‘sh bo‘lmasin")
        return redirect("akt_get")

    # ✅ Deed yaratamiz
    deed = Deed.objects.create(
        sender=sender,          # FK obyekt
        user=employee,          # FK obyekt
        message_user=message,
        body=body,
        file_type=False,    # ✅ True/False
    )

    # ✅ PDF yaratib deed.file ga saqlaymiz
    try:
        pdf_bytes = deed_to_pdf_bytes(deed)
        wm_text = "TASDIQLANMAGAN"
        pdf_bytes = add_text_watermark_pdf_bytes(pdf_bytes, wm_text)
        today_str = timezone.now().strftime("%Y%m%d")
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        random_part = ''.join(secrets.choice(alphabet) for _ in range(6))
        pdf_name = f"akt_{today_str}_{random_part}.pdf"
        deed.file.save(pdf_name, ContentFile(pdf_bytes), save=True)

    except HtmlPdfError as e:
        messages.warning(request, f"PDF yaratilmadi: {e}")

    # ✅ kelishuvchilar IDs tozalash
    ids = []
    for x in (agreements or []):
        x = (x or "").strip()
        if x.isdigit():
            ids.append(int(x))
    ids = list(set(ids))  # uniq

    # ✅ sender va hozirgi employee’ni exclude
    exclude_ids = {sender.id}
    ids = [i for i in ids if i not in exclude_ids]

    # ✅ DeedConsent bulk_create
    if ids:
        emps = Employee.objects.filter(id__in=ids).only("id")
        objs = [DeedConsent(deed=deed, employee=e, status="viewed") for e in emps]
        DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

    messages.success(request, "Imzolashga yuborildi")
    return redirect("contact_user")


@never_cache
@require_GET
@login_required
@role_required("akt")
def svod_get(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    context = {
        "organizations": Organization.objects.only("id", "name").order_by("id"),
        "emp_bos": Employee.objects.filter(department_id=283).select_related("rank"),
        "employee": Employee.objects.filter(organization_id=4).select_related("rank"),
    }
    return render(request, 'main/svod.html', context)


@never_cache
@require_POST
@login_required
@role_required("akt")
def svod_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    # formdan keladiganlar
    sender_id = (request.POST.get("sender") or "").strip()
    message = (request.POST.get("message") or "").strip() or None
    agreements = request.POST.getlist("agreements[]")
    body = request.POST.get("body") or ""

    # sender obyekt
    sender = Employee.objects.filter(id=sender_id).first() if sender_id.isdigit() else None
    if not sender:
        messages.info(request, "Imzolovchi xodim tanlanmadi")
        return redirect("akt_get")

    if not body.strip():
        messages.info(request, "Hujjat matni (body) bo‘sh bo‘lmasin")
        return redirect("akt_get")

    # ✅ Deed yaratamiz
    deed = Deed.objects.create(
        sender=sender,  # FK obyekt
        user=employee,  # FK obyekt
        message_user=message,
        body=body,
        file_type=False,  # ✅ True/False
    )

    # ✅ PDF yaratib deed.file ga saqlaymiz
    try:
        pdf_bytes = deed_to_pdf_bytes(deed)
        wm_text = "TASDIQLANMAGAN"
        pdf_bytes = add_text_watermark_pdf_bytes(pdf_bytes, wm_text)
        today_str = timezone.now().strftime("%Y%m%d")
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        random_part = ''.join(secrets.choice(alphabet) for _ in range(6))
        pdf_name = f"akt_{today_str}_{random_part}.pdf"
        deed.file.save(pdf_name, ContentFile(pdf_bytes), save=True)

    except HtmlPdfError as e:
        messages.info(request, f"PDF yaratilmadi: {e}")

    # ✅ kelishuvchilar IDs tozalash
    ids = []
    for x in (agreements or []):
        x = (x or "").strip()
        if x.isdigit():
            ids.append(int(x))
    ids = list(set(ids))  # uniq

    # ✅ sender va hozirgi employee’ni exclude
    exclude_ids = {sender.id}
    ids = [i for i in ids if i not in exclude_ids]

    # ✅ DeedConsent bulk_create
    if ids:
        emps = Employee.objects.filter(id__in=ids).only("id")
        objs = [DeedConsent(deed=deed, employee=e, status="viewed") for e in emps]
        DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

    messages.success(request, "Imzolashga yuborildi")
    return redirect("contact_user")


@never_cache
@require_GET
@login_required
@role_required("akt")
def reestr_get(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    context = {
        "organizations": Organization.objects.only("id", "name").order_by("id"),
        "emp_bos": Employee.objects.filter(department_id=283).select_related("rank"),
        "employee": Employee.objects.filter(organization_id=4).select_related("rank"),
    }
    return render(request, 'main/reestr.html', context)


@never_cache
@login_required
@role_required("akt")
def reestr_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    # formdan keladiganlar
    sender_id = (request.POST.get("sender") or "").strip()
    message = (request.POST.get("message") or "").strip() or None
    agreements = request.POST.getlist("agreements[]")
    body = request.POST.get("body") or ""

    file_type = False

    # sender obyekt
    sender = Employee.objects.filter(id=sender_id).first() if sender_id.isdigit() else None
    if not sender:
        messages.info(request, "Imzolovchi xodim tanlanmadi")
        return redirect("akt_get")

    if not body.strip():
        messages.info(request, "Hujjat matni (body) bo‘sh bo‘lmasin")
        return redirect("akt_get")

    # ✅ Deed yaratamiz
    deed = Deed.objects.create(
        sender=sender,  # FK obyekt
        user=employee,  # FK obyekt
        message_user=message,
        body=body,
        file_type=file_type,  # ✅ True/False
    )

    # ✅ PDF yaratib deed.file ga saqlaymiz
    try:
        pdf_bytes = deed_to_pdf_bytes(deed)
        wm_text = "TASDIQLANMAGAN"
        pdf_bytes = add_text_watermark_pdf_bytes(pdf_bytes, wm_text)
        today_str = timezone.now().strftime("%Y%m%d")
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        random_part = ''.join(secrets.choice(alphabet) for _ in range(6))
        pdf_name = f"akt_{today_str}_{random_part}.pdf"
        deed.file.save(pdf_name, ContentFile(pdf_bytes), save=True)

    except HtmlPdfError as e:
        messages.info(request, f"PDF yaratilmadi: {e}")

    # ✅ kelishuvchilar IDs tozalash
    ids = []
    for x in (agreements or []):
        x = (x or "").strip()
        if x.isdigit():
            ids.append(int(x))
    ids = list(set(ids))  # uniq

    # ✅ sender va hozirgi employee’ni exclude
    exclude_ids = {sender.id}
    ids = [i for i in ids if i not in exclude_ids]

    # ✅ DeedConsent bulk_create
    if ids:
        emps = Employee.objects.filter(id__in=ids).only("id")
        objs = [DeedConsent(deed=deed, employee=e, status="viewed") for e in emps]
        DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

    messages.success(request, "Imzolashga yuborildi")
    return redirect("contact_user")


@never_cache
@require_GET
@login_required
def technics_get(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    if employee.rol.boss:
        technics = Technics.objects.filter(
            employee__organization=employee.organization,
            employee__department=employee.department,
        )
    else:
        technics = Technics.objects.filter(employee=employee)

    context = {
        'technics': technics,
    }
    return render(request, 'main/technics_get.html', context)



@never_cache
@require_GET
@login_required
@role_required("status")
def emp_status(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    region_id = (request.GET.get("region") or "").strip()
    date1_raw = (request.GET.get("date1") or "").strip()
    date2_raw = (request.GET.get("date2") or "").strip()

    date1 = parse_date(date1_raw) if date1_raw else None
    date2 = parse_date(date2_raw) if date2_raw else None

    has_search = bool(region_id or date1_raw or date2_raw)

    if not has_search:
        today = timezone.localdate()
        date1 = today.replace(day=1)  # oyning 1-kuni

        # keyingi oyning 1-kuni (end)
        if date1.month == 12:
            next_month = date1.replace(year=date1.year + 1, month=1)
        else:
            next_month = date1.replace(month=date1.month + 1)

        # default qiymatlarni inputlarda ko'rsatish uchun
        date1_raw = date1.isoformat()
        date2_raw = (next_month - timezone.timedelta(days=1)).isoformat()  # oyning oxirgi kuni
        date2 = parse_date(date2_raw)

    orders = Order.objects.filter(receiver__isnull=False)
    goal_orders = Order.objects.filter(receiver__isnull=False)

    if region_id.isdigit():
        orders = orders.filter(receiver__region_id=int(region_id))
        goal_orders = goal_orders.filter(receiver__region_id=int(region_id))

    if date1:
        orders = orders.filter(date_creat__date__gte=date1)
        goal_orders = goal_orders.filter(date_creat__date__gte=date1)
    if date2:
        orders = orders.filter(date_creat__date__lte=date2)
        goal_orders = goal_orders.filter(date_creat__date__lte=date2)

    employee = (
        orders
        .filter(receiver__isnull=False)
        .values("receiver_id")
        .annotate(
            full_name=Concat(
                Coalesce(F("receiver__last_name"), Value("")),
                Value(" "),
                Coalesce(F("receiver__first_name"), Value("")),
                Value(" "),
                Coalesce(F("receiver__father_name"), Value("")),
            ),
            accepted_count=Count("id", filter=Q(status="accepted")),
            finished_count=Count("id", filter=Q(status="finished")),
            approved_count=Count("id", filter=Q(status="approved")),
            rejected_count=Count("id", filter=Q(status="rejected")),
            total_count=Count("id"),
        )
        .order_by("-total_count", "-approved_count")
    )

    goal = (
        Goal.objects
        .annotate(
            total=Count(
                "order",
                filter=Q(order__in=goal_orders)
            )
        )
        .order_by("-total")
    )

    context = {
        "goal": goal,
        "employee": employee,
        "region": Region.objects.all().order_by("id"),
        "selected_region": region_id,
        "date1": date1_raw,
        "date2": date2_raw,
    }
    return render(request, "main/emp_status.html", context)


@never_cache
@require_GET
@login_required
@role_required("status")
def tex_status(
        request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    # ------------------- Tashkilotlar -------------------
    orgs = list(
        Organization.objects
        .order_by("id")
        .annotate(
            technics_count=Count(
                "technics__id",
                filter=Q(technics__is_active=True,technics__group_id=1),
                distinct=True
            )
        )
        .values("id", "name", "technics_count")
    )

    total_technics = sum(o["technics_count"] for o in orgs) or 1

    for o in orgs:
        o["foiz"] = round((o["technics_count"] * 100) / total_technics, 1)

    # ------------------- Kategoriyalar -------------------
    cats_qs = list(
        Category.objects
        .filter(group_id=1)
        .order_by("id")
        .values("id", "name")
    )

    cat_ids = [c["id"] for c in cats_qs]
    categories = [c["name"] for c in cats_qs]
    org_ids = [o["id"] for o in orgs]

    # ------------------- Organization + Category count -------------------
    grouped = list(
        Technics.objects
        .filter(
            is_active=True,
            organization_id__in=org_ids,
            category_id__in=cat_ids,
            group_id = 1
        )
        .values("organization_id", "category_id")
        .annotate(cnt=Count("id"))
        .order_by("organization_id", "category_id")
    )

    lookup = {
        (g["organization_id"], g["category_id"]): g["cnt"]
        for g in grouped
    }

    # ------------------- CARD DATA -------------------
    orgs_qs = []

    for org in orgs:

        category_list = []
        org_total = org["technics_count"]

        for cat in cats_qs:

            count = lookup.get((org["id"], cat["id"]), 0)

            foiz = round((count * 100) / org_total, 1) if org_total > 0 else 0

            category_list.append({
                "id": cat["id"],
                "name": cat["name"],
                "soni": count,
                "foiz": foiz,
            })

        orgs_qs.append({
            "id": org["id"],
            "name": org["name"],
            "technics_count": org["technics_count"],
            "foiz": org["foiz"],
            "category_list": category_list,
        })

    # ------------------- PIE CHART -------------------
    pie_labels = [o["name"] for o in orgs]
    pie_values = [o["technics_count"] for o in orgs]

    # ------------------- AREA CHART -------------------
    series = []

    for org in orgs:
        data = [lookup.get((org["id"], cid), 0) for cid in cat_ids]

        series.append({
            "name": org["name"],
            "data": data
        })

    # ------------------- FUNNEL CHART -------------------
    orgs_sorted = sorted(orgs, key=lambda x: x["technics_count"], reverse=True)

    funnel_labels = [o["name"] for o in orgs_sorted[:8]]
    funnel_values = [o["technics_count"] for o in orgs_sorted[:8]]

    context = {
        "orgs_qs": orgs_qs,
        "categories": categories,
        "series": series,
        "pie_labels": pie_labels,
        "pie_values": pie_values,
        "funnel_labels": funnel_labels,
        "funnel_values": funnel_values,
    }

    return render(request, "main/tex_status.html", context)

@never_cache
@require_GET
def technics_detail(request, pk):
    technics = get_object_or_404(Technics, pk=pk, is_active=True)
    return render(request, "main/technics_detail.html", {"technics": technics})
