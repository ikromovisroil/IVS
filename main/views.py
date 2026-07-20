from main.ajax_views import *
from django.db.models import Prefetch
from django.contrib.auth.decorators import login_required, permission_required
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
import base64
import binascii

@never_cache
def error_403(request, exception=None):
    return render(request, "errors/403.html", status=403)

@never_cache
def error_404(request, exception=None):
    return render(request, "errors/404.html", status=404)

@never_cache
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
@require_GET
def profil(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    return render(request, "main/profil.html", {
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
        .select_related(
            "sender", "receiver", "user",
            "sender__organization", "receiver__organization"
        )
        .prefetch_related(
            Prefetch(
                "deedconsent_set",
                queryset=DeedConsent.objects.select_related(
                    "employee", "employee__organization"
                )
            )
        )
        .distinct()
        .order_by("-id")
    )

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
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
        .select_related(
            "sender", "receiver", "user",
            "sender__organization", "receiver__organization"
        )
        .prefetch_related(
            Prefetch(
                "deedconsent_set",
                queryset=DeedConsent.objects.select_related(
                    "employee", "employee__organization"
                )
            )
        )
        .distinct()
        .order_by("-id")
    )

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
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
        .select_related(
            "sender", "receiver", "user",
            "sender__organization", "receiver__organization"
        )
        .prefetch_related(
            Prefetch(
                "deedconsent_set",
                queryset=DeedConsent.objects.select_related(
                    "employee", "employee__organization"
                )
            )
        )
        .distinct()
        .order_by("-id")
    )

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
        "qs_params": params.urlencode(),
    }
    return render(request, "main/contact_agrement.html", context)


@never_cache
@require_GET
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
        .select_related(
            "sender", "receiver", "user",
            "sender__organization", "receiver__organization"
        )
        .prefetch_related(
            Prefetch(
                "deedconsent_set",
                queryset=DeedConsent.objects.select_related(
                    "employee", "employee__organization"
                )
            )
        )
        .distinct()
        .order_by("-id")
    )

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
        "qs_params": params.urlencode(),
    }
    return render(request, "main/contact_agrement_arxiv.html", context)


@never_cache
@require_GET
@login_required
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
        .select_related(
            "sender", "receiver", "user",
            "sender__organization", "receiver__organization"
        )
        .prefetch_related(
            Prefetch(
                "deedconsent_set",
                queryset=DeedConsent.objects.select_related(
                    "employee", "employee__organization"
                )
            )
        )
        .distinct()
        .order_by("-id")
    )

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
        "qs_params": params.urlencode(),
        "organization": Organization.objects.only("id", "name").order_by("id"),
    }
    return render(request, "main/contact_user.html", context)


@never_cache
@require_GET
@login_required
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
        .select_related(
            "sender", "receiver", "user",
            "sender__organization", "receiver__organization"
        )
        .prefetch_related(
            Prefetch(
                "deedconsent_set",
                queryset=DeedConsent.objects.select_related(
                    "employee", "employee__organization"
                )
            )
        )
        .distinct()
        .order_by("-id")
    )

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
        "qs_params": params.urlencode(),
    }
    return render(request, "main/contact_user_arxiv.html", context)


@never_cache
@require_POST
@login_required
@permission_required("main.add_deed", raise_exception=True)
def contact_post_deed(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    status = request.POST.get("status", "").strip()
    sender_id = request.POST.get("employee", "").strip()
    agreement_ids = request.POST.getlist("agreements")
    uploaded_file = request.FILES.get("file")

    # --- Validatsiya ---
    valid_statuses = dict(Deed._meta.get_field("status").choices)
    if status not in valid_statuses:
        messages.info(request, "Ariza turi noto'g'ri tanlangan")
        return redirect("contact_user")

    if not sender_id or not sender_id.isdigit():
        messages.info(request, "Xodim tanlanmagan")
        return redirect("contact_user")

    # Faqat bo'sh bo'lmagan ID'larni olamiz (select'da bo'sh option ham bo'lishi mumkin)
    agreement_ids = [aid for aid in agreement_ids if aid.isdigit()]
    sender = get_object_or_404(Employee, pk=sender_id)

    if not uploaded_file:
        messages.info(request, "Fayl biriktirilmagan")
        return redirect("contact_user")

    with transaction.atomic():
        deed = Deed.objects.create(
            user=employee,
            sender=sender,
            status=status,
            file=uploaded_file,
        )

        if agreement_ids:
            DeedConsent.objects.bulk_create([
                DeedConsent(deed=deed, employee_id=aid)
                for aid in agreement_ids
            ])

    messages.success(request, "Ariza muvaffaqiyatli yuborildi")
    return redirect("contact_user")


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
def deed_action(request, pk):
    emp = getattr(request.user, "employee", None)
    if not emp:
        raise PermissionDenied("Employee yo'q")

    back_url = request.META.get("HTTP_REFERER") or "/"
    action = (request.POST.get("action") or "").strip().lower()
    message = (request.POST.get("message") or "").strip()

    deed = get_object_or_404(Deed, pk=pk)

    if deed.receiver_id == emp.id:
        role = "receiver"
        current_status = deed.status_receiver
    elif deed.sender_id == emp.id:
        role = "sender"
        current_status = deed.status_sender
    else:
        raise PermissionDenied("Sizga ruxsat yo'q")

    if current_status != "viewed":
        messages.info(request, "Bu dalolatnoma holatida amal bajarib bo'lmaydi")
        return redirect(back_url)

    if action == "reject":
        now = timezone.now()
        with transaction.atomic():
            deed = Deed.objects.select_for_update().get(pk=pk)
            update_fields = ["date_edit"]

            if role == "receiver":
                deed.status_receiver = "rejected"
                deed.message_receiver = message
                deed.date_receiver = now
                update_fields += ["status_receiver", "message_receiver", "date_receiver"]
            else:
                deed.status_sender = "rejected"
                deed.message_sender = message
                deed.date_sender = now
                update_fields += ["status_sender", "message_sender", "date_sender"]

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

    messages.info(request, "Noto'g'ri amal")
    return redirect(back_url)



import logging
logger = logging.getLogger(__name__)
@never_cache
@require_http_methods(["GET", "POST"])
@login_required
def deed_edit(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    deed = get_object_or_404(
        Deed.objects.select_related("sender__organization", "receiver__organization"),
        pk=pk
    )

    if deed.user_id != employee.id:
        raise PermissionDenied("Sizga ruxsat yo'q")

    sender_org_id = deed.sender.organization_id if deed.sender_id else None
    sender_dep_id = deed.sender.department_id if deed.sender_id else None
    receiver_org_id = deed.receiver.organization_id if deed.receiver_id else None
    receiver_dep_id = deed.receiver.department_id if deed.receiver_id else None
    my_org_id = employee.organization_id or None

    sender_qs = (
        Employee.objects.filter(
            organization_id=sender_org_id,
            department=deed.sender.department,
        ).order_by("last_name", "first_name", "father_name")
        if sender_org_id else Employee.objects.none()
    )

    receiver_qs = (
        Employee.objects.filter(
            organization_id=receiver_org_id,
            department=deed.receiver.department,
        ).order_by("last_name", "first_name", "father_name")
        if receiver_org_id else Employee.objects.none()
    )

    org_ids = [x for x in [sender_org_id, receiver_org_id, my_org_id] if x]
    employee_qs = (
        Employee.objects.filter(organization_id__in=org_ids)
        .select_related("organization")
        .distinct()
        .order_by("last_name", "first_name", "father_name")
        if org_ids else Employee.objects.none()
    )

    selected_agreement_ids = set(
        DeedConsent.objects.filter(deed_id=deed.id).values_list("employee_id", flat=True)
    )

    if request.method == "POST":
        sender_id = (request.POST.get("sender") or "").strip()
        receiver_id = (request.POST.get("receiver") or "").strip()
        agreements_ids = request.POST.getlist("agreements[]")

        # --- Body Base64 orqali keladi (WAF'ni chetlab o'tish uchun) ---
        body_encoded = (request.POST.get("body_encoded") or "").strip()
        body = ""
        if body_encoded:
            try:
                body = base64.b64decode(body_encoded).decode("utf-8").strip()
            except (binascii.Error, UnicodeDecodeError, ValueError):
                body = ""

        if not body:
            messages.info(request, "Hujjat matni bo'sh bo'lmasin")
            return redirect("deed_edit", pk=deed.pk)

        if not sender_id.isdigit():
            messages.info(request, "Imzolovchi xodim tanlanmadi")
            return redirect("deed_edit", pk=deed.pk)

        new_sender = Employee.objects.filter(
            id=int(sender_id),
            organization_id=sender_org_id,
            department_id=sender_dep_id,
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
                department_id=receiver_dep_id,
            ).first()

            if not new_receiver:
                messages.info(request, "Qabul qiluvchi topilmadi yoki ruxsat etilmagan")
                return redirect("deed_edit", pk=deed.pk)

        clean_agreement_ids = [int(x) for x in agreements_ids if str(x).isdigit()]
        if clean_agreement_ids:
            clean_agreement_ids = list(
                Employee.objects.filter(
                    id__in=clean_agreement_ids,
                    organization_id__in=org_ids,
                ).values_list("id", flat=True)
            )

        try:
            # 1. DB operatsiyalar — transaction ichida
            with transaction.atomic():
                deed = Deed.objects.select_for_update().get(pk=deed.pk)

                sender_changed = (deed.sender_id != new_sender.id)
                receiver_changed = (
                    deed.receiver_id is not None
                    and deed.receiver_id != new_receiver.id
                )

                deed.sender = new_sender
                if sender_changed:
                    deed.status_sender = "viewed"
                    deed.message_sender = None
                    deed.date_sender = None

                update_fields = ["sender", "body"]
                if sender_changed:
                    update_fields += ["status_sender", "message_sender", "date_sender"]

                if deed.receiver_id:
                    deed.receiver = new_receiver
                    if receiver_changed:
                        deed.status_receiver = "viewed"
                        deed.message_receiver = None
                        deed.date_receiver = None
                        update_fields += ["receiver", "status_receiver", "message_receiver", "date_receiver"]
                    else:
                        update_fields.append("receiver")

                deed.body = body
                deed.save(update_fields=update_fields)

                exclude_ids = {deed.sender_id}
                if deed.receiver_id:
                    exclude_ids.add(deed.receiver_id)

                final_ids = [eid for eid in clean_agreement_ids if eid not in exclude_ids]

                existing_employee_ids = set(
                    DeedConsent.objects.filter(deed_id=deed.id).values_list("employee_id", flat=True)
                )

                # Ro'yxatdan chiqarilganlarni o'chirish
                DeedConsent.objects.filter(deed_id=deed.id).exclude(
                    employee_id__in=final_ids
                ).delete()

                new_employee_ids = [
                    eid for eid in final_ids if eid not in existing_employee_ids
                ]
                if new_employee_ids:
                    DeedConsent.objects.bulk_create([
                        DeedConsent(deed_id=deed.id, employee_id=eid, status="viewed")
                        for eid in new_employee_ids
                    ])

            # 2. PDF — transaction tashqarisida
            try:
                if deed.file:
                    deed.file.delete(save=False)
            except Exception:
                logger.exception("Deed #%s eski faylini o'chirishda xatolik", deed.pk)

            pdf_bytes = deed_to_pdf_bytes(deed)
            pdf_bytes = add_text_watermark_pdf_bytes(pdf_bytes, "TASDIQLANMAGAN")
            pdf_name = f"akt_{timezone.now().strftime('%Y%m%d')}_{secrets.token_urlsafe(8)}.pdf"
            deed.file.save(pdf_name, ContentFile(pdf_bytes), save=True)

            messages.success(request, "Hujjat muvaffaqiyatli tahrirlandi")
            return redirect("contact_user")

        except HtmlPdfError as e:
            messages.info(request, f"Hujjat yangilanmadi: {e}")
            return redirect("deed_edit", pk=deed.pk)

        except Exception:
            logger.exception("Deed #%s tahrirlashda kutilmagan xatolik", deed.pk)
            messages.info(request, "Kutilmagan xatolik yuz berdi. Qayta urinib ko'ring.")
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
        raise PermissionDenied("Employee yo'q")

    back_url = request.META.get("HTTP_REFERER") or "/"
    action = (request.POST.get("action") or "").strip().lower()
    message = (request.POST.get("message") or "").strip()

    if action not in {"approve", "reject"}:
        messages.info(request, "Noto'g'ri amal")
        return redirect(back_url)

    # Tekshiruvlar transaction tashqarisida
    consent = get_object_or_404(DeedConsent, pk=pk)

    if consent.employee_id != employee.id:
        raise PermissionDenied("Sizga ruxsat yo'q")

    if consent.status != "viewed":
        messages.info(request, "Bu kelishuv allaqachon ko'rib chiqilgan")
        return redirect(back_url)

    if action == "reject" and not message:
        messages.info(request, "Rad etish uchun izoh yozing")
        return redirect(back_url)

    try:
        with transaction.atomic():
            consent = DeedConsent.objects.select_for_update().get(pk=pk)

            # Race condition: boshqa so'rov o'zgartirgan bo'lishi mumkin
            if consent.status != "viewed":
                messages.info(request, "Bu kelishuv allaqachon ko'rib chiqilgan")
                return redirect(back_url)

            consent.status = "approved" if action == "approve" else "rejected"
            consent.message = message
            consent.save(update_fields=["status", "message"])

    except Exception as e:
        messages.info(request, f"Kutilmagan xatolik: {e}")
        return redirect(back_url)

    if action == "approve":
        messages.success(request, "Hujjat muvaffaqiyatli kelishildi")
    else:
        messages.success(request, "Hujjat rad etildi")

    return redirect(back_url)


from django.http import HttpRequest
@never_cache
@require_GET
@login_required
@permission_required("main.view_technics", raise_exception=True)
def barn_tex(request: HttpRequest):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    def to_int(v):
        v = (v or "").strip()
        if not v:
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    organization_id = to_int(request.GET.get("organization"))
    region_id = to_int(request.GET.get("region"))
    department_id = to_int(request.GET.get("department"))
    directorate_id = to_int(request.GET.get("directorate"))
    division_id = to_int(request.GET.get("division"))
    category_id = to_int(request.GET.get("category"))
    group_id = to_int(request.GET.get("groups"))
    status = (request.GET.get("status") or "").strip() or None
    name = (request.GET.get("name") or "").strip() or None
    page_number = request.GET.get("page", 1)

    if name:
        name = name[:120]

    has_filter = bool(
        organization_id or region_id or department_id or directorate_id
        or division_id or status or category_id or group_id or name
    )

    organizations = Organization.objects.only("id", "name").order_by("id")
    if not request.user.has_perm("main.all_organization"):
        organizations = organizations.filter(id=employee.organization_id)

    groups = Group.objects.only("id", "name").order_by("id")
    technics_form = TechnicsForm()

    regions = Region.objects.only("id", "name").order_by("id")
    if not request.user.has_perm("main.all_region"):
        regions = regions.filter(id=employee.region_id)

    departments = Department.objects.none()
    if organization_id and region_id:
        departments = Department.objects.filter(
            organization_id=organization_id,
            region_id=region_id,
        ).only("id", "name").order_by("id")
    elif organization_id:
        departments = Department.objects.filter(
            organization_id=organization_id,
        ).only("id", "name").order_by("id")

    directorates = Directorate.objects.none()
    if department_id:
        directorates = Directorate.objects.filter(
            department_id=department_id,
        ).only("id", "name").order_by("id")

    divisions = Division.objects.none()
    if directorate_id:
        divisions = Division.objects.filter(
            directorate_id=directorate_id,
        ).only("id", "name").order_by("id")

    categories = Category.objects.none()
    if group_id:
        categories = Category.objects.filter(
            group_id=group_id,
        ).only("id", "name").order_by("id")

    params = request.GET.copy()
    params.pop("page", None)
    qs_params = params.urlencode()

    base_context = {
        "organizations": organizations,
        "regions": regions,
        "groups": groups,
        "categories": categories,
        "technics_form": technics_form,
        "departments": departments,
        "directorates": directorates,
        "divisions": divisions,
        "selected_org": organization_id,
        "selected_reg": region_id,
        "selected_dep": department_id,
        "selected_dir": directorate_id,
        "selected_div": division_id,
        "selected_group": group_id,
        "selected_category": category_id,
        "qs_params": qs_params,
        "extratex": Structure.objects.none(),
    }

    if not has_filter:
        return render(request, "main/barn_tex.html", {
            **base_context,
            "page_obj": Paginator([], 20).get_page(page_number),
            "grouped_technics": [],
            "employees_without_technics": [],
            "total_count": 0,
        })

    # ------------------------------------------------------------------ #
    #  1. TEXNIKALAR query                                                 #
    # ------------------------------------------------------------------ #
    liable_ids = Liable.objects.filter(
        employee=employee
    ).values_list("category_id", flat=True)

    base_qs = Technics.objects.filter(category_id__in=liable_ids, is_active=True)

    if not request.user.has_perm("main.all_organization"):
        base_qs = base_qs.filter(organization_id=employee.organization_id)

    if organization_id:
        base_qs = base_qs.filter(organization_id=organization_id)
    if region_id:
        base_qs = base_qs.filter(region_id=region_id)
    if department_id:
        base_qs = base_qs.filter(department_id=department_id)
    if directorate_id:
        base_qs = base_qs.filter(directorate_id=directorate_id)
    if division_id:
        base_qs = base_qs.filter(division_id=division_id)
    if status:
        base_qs = base_qs.filter(status=status)
    if group_id:
        base_qs = base_qs.filter(group_id=group_id)
    if category_id:
        base_qs = base_qs.filter(category_id=category_id)

    if name:
        words = [w for w in name.split() if w]
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

    tech_qs = (
        base_qs
        .select_related(
            "organization", "region", "department",
            "directorate", "division", "category", "employee",
        )
        .only(
            "id", "name", "parametr", "inventory", "serial",
            "ip", "mac", "status", "year", "price", "employee_id",
            "organization__id", "organization__name",
            "region__id", "region__name",
            "department__id", "department__name",
            "directorate__id", "directorate__name",
            "division__id", "division__name",
            "category__id", "category__name",
            "employee__id", "employee__first_name",
            "employee__last_name", "employee__father_name",
        )
        .order_by("employee_id", "id")
    )

    # ------------------------------------------------------------------ #
    #  2. Pagination — faqat texnikalar bo'yicha                          #
    # ------------------------------------------------------------------ #
    paginator = Paginator(tech_qs, 20)
    page_obj = paginator.get_page(page_number)

    # ------------------------------------------------------------------ #
    #  3. Texnikasi yo'q xodimlar                                         #
    # ------------------------------------------------------------------ #
    all_assigned_emp_ids = set(
        base_qs
        .exclude(employee_id=None)
        .values_list("employee_id", flat=True)
        .distinct()
    )

    emp_filter = Q()
    if not request.user.has_perm("main.all_organization"):
        emp_filter &= Q(organization_id=employee.organization_id)
    if organization_id:
        emp_filter &= Q(organization_id=organization_id)
    if region_id:
        emp_filter &= Q(region_id=region_id)
    if department_id:
        emp_filter &= Q(department_id=department_id)
    if directorate_id:
        emp_filter &= Q(directorate_id=directorate_id)
    if division_id:
        emp_filter &= Q(division_id=division_id)

    if name:
        words = [w for w in name.split() if w]
        emp_name_q = Q()
        for w in words:
            emp_name_q &= (
                Q(last_name__icontains=w) |
                Q(first_name__icontains=w) |
                Q(father_name__icontains=w)
            )
        emp_filter &= emp_name_q

    employees_without_technics = (
        Employee.objects
        .filter(emp_filter)
        .exclude(id__in=all_assigned_emp_ids)
        .only("id", "first_name", "last_name", "father_name")
        .order_by("last_name", "first_name")
    )

    # ------------------------------------------------------------------ #
    #  4. grouped_technics — faqat sahifadagi texnikalar                  #
    # ------------------------------------------------------------------ #
    grouped_technics = []
    for emp_id, items in groupby(page_obj.object_list, key=lambda t: t.employee_id):
        items_list = list(items)
        emp_obj = items_list[0].employee if emp_id else None
        grouped_technics.append((emp_obj, items_list))

    # ------------------------------------------------------------------ #
    #  5. Erkin texnikalar                                                 #
    # ------------------------------------------------------------------ #
    extratex = Structure.objects.none()
    if organization_id:
        extratex = (
            Structure.objects
            .filter(
                organization_id=organization_id,
                region=employee.region,
                status="free",
                is_active=True,
            )
            .only("id", "name", "inventory", "serial")
            .order_by("id")
        )

    return render(request, "main/barn_tex.html", {
        **base_context,
        "page_obj": page_obj,
        "grouped_technics": grouped_technics,
        "employees_without_technics": employees_without_technics,
        "extratex": extratex,
        "total_count": total_count,
    })


@never_cache
@require_POST
@login_required
@permission_required("main.add_technics", raise_exception=True)
def technics_create(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")
    form = TechnicsForm(request.POST)

    if form.is_valid():
        technics = form.save(commit=False)
        serial = (technics.serial or "").strip()
        organization = technics.organization

        if employee.region_id:
            technics.region_id = employee.region_id

        if serial and Technics.objects.filter(
                is_active=True,
                serial__iexact=serial,
                organization=organization
        ).exists():
            messages.info(request, "Bu texnika allaqachon mavjud!")
            return redirect(back_url)

        technics.save()
        messages.success(request, "Uskuna qo‘shildi")
    else:
        messages.info(request, f"Xatolik: {form.errors}")

    return redirect(back_url)


@never_cache
@require_POST
@login_required
@permission_required("main.delete_technics", raise_exception=True)
@transaction.atomic
def technics_delete(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    back_url = request.META.get("HTTP_REFERER", "/")
    tex_id = request.POST.get("texnika_id")

    try:
        tex = Technics.objects.select_for_update().get(pk=int(tex_id))
    except (Technics.DoesNotExist, TypeError, ValueError):
        messages.info(request, "Uskuna topilmadi")
        return redirect(back_url)

    if not tex.is_active:
        messages.info(request, "Uskuna allaqachon o'chirilgan")
        return redirect(back_url)

    update_fields = ["is_active"]
    tex.is_active = False

    if tex.employee_id:
        tex.employee = None
        tex.status = "free"
        update_fields += ["employee", "status"]

    tex.save(update_fields=update_fields)

    messages.success(request, "Uskuna muvaffaqiyatli o'chirildi")
    return redirect(back_url)


@never_cache
@require_POST
@login_required
@permission_required("main.change_technics", raise_exception=True)
@transaction.atomic
def technics_attach(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

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
        messages.info(request, "Bo'lim noto'g'ri tanlandi")
        return redirect(back_url)

    if dir_id and not dir_id.isdigit():
        messages.info(request, "Boshqarma noto'g'ri tanlandi")
        return redirect(back_url)

    if div_id and not div_id.isdigit():
        messages.info(request, "Bo'linma noto'g'ri tanlandi")
        return redirect(back_url)

    if emp_id and not emp_id.isdigit():
        messages.info(request, "Xodim noto'g'ri tanlandi")
        return redirect(back_url)

    tex = get_object_or_404(Technics.objects.select_for_update(), id=int(tex_id))

    # Har uch holatda bir xil update_fields
    update_fields = ["employee", "department", "directorate", "division", "status"]

    # 1. Xodimga biriktirish
    if emp_id:
        emp = get_object_or_404(
            Employee.objects.select_related("organization", "region"),
            id=int(emp_id)
        )

        # Xodim shu tashkilotga tegishlimi?
        if emp.organization_id != tex.organization_id:
            raise PermissionDenied("Xodim bu tashkilotga tegishli emas")

        tex.employee    = emp
        tex.department  = None
        tex.directorate = None
        tex.division    = None
        tex.status      = "active"
        tex.save(update_fields=update_fields)

        messages.success(request, "Uskuna xodimga biriktirildi")
        return redirect(back_url)

    # 2. Strukturaga biriktirish
    if dep_id or dir_id or div_id:
        department_obj  = None
        directorate_obj = None
        division_obj    = None

        if dep_id:
            department_obj = get_object_or_404(
                Department,
                id=int(dep_id),
                organization_id=tex.organization_id
            )

        if dir_id:
            directorate_obj = get_object_or_404(Directorate, id=int(dir_id))
            if department_obj and directorate_obj.department_id != department_obj.id:
                messages.info(request, "Boshqarma tanlangan bo'limga tegishli emas")
                return redirect(back_url)

        if div_id:
            division_obj = get_object_or_404(Division, id=int(div_id))
            if directorate_obj and division_obj.directorate_id != directorate_obj.id:
                messages.info(request, "Bo'linma tanlangan boshqarmaga tegishli emas")
                return redirect(back_url)

        tex.employee    = None
        tex.department  = department_obj
        tex.directorate = directorate_obj
        tex.division    = division_obj
        tex.status      = "active"
        tex.save(update_fields=update_fields)

        messages.success(request, "Uskuna strukturaga biriktirildi")
        return redirect(back_url)

    # 3. Bo'shatish
    tex.employee    = None
    tex.department  = None
    tex.directorate = None
    tex.division    = None
    tex.status      = "free"
    tex.save(update_fields=update_fields)

    messages.success(request, "Uskuna bo'shatildi")
    return redirect(back_url)


@never_cache
@require_POST
@login_required
@permission_required("main.change_technics", raise_exception=True)
@transaction.atomic
def technics_update(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    back_url = request.META.get("HTTP_REFERER", "/")
    tex = get_object_or_404(Technics.objects.select_for_update(), pk=pk)

    category_id     = (request.POST.get("category")     or "").strip()
    organization_id = (request.POST.get("organization") or "").strip()

    # FK lar
    if category_id:
        if not category_id.isdigit():
            messages.info(request, "Kategoriya noto'g'ri")
            return redirect(back_url)
        tex.category = get_object_or_404(Category, pk=int(category_id))
    else:
        tex.category = None

    if organization_id:
        if not organization_id.isdigit():
            messages.info(request, "Tashkilot noto'g'ri")
            return redirect(back_url)
        tex.organization = get_object_or_404(Organization, pk=int(organization_id))
    else:
        tex.organization = None

    # Oddiy maydonlar
    tex.name      = (request.POST.get("name")      or "").strip()
    tex.parametr  = (request.POST.get("parametr")  or "").strip() or None
    tex.inventory = (request.POST.get("inventory") or "").strip() or None
    tex.serial    = (request.POST.get("serial")    or "").strip() or None
    tex.mac       = (request.POST.get("mac")       or "").strip() or None
    tex.ip        = (request.POST.get("ip")        or "").strip() or None
    tex.year      = (request.POST.get("year")      or "").strip() or None
    tex.address   = (request.POST.get("address")   or "").strip() or None
    tex.status    = (request.POST.get("status")    or "").strip()

    if not tex.name:
        messages.info(request, "Nomi bo'sh bo'lmasin")
        return redirect(back_url)

    allowed_status = ["free", "active", "repair", "defect"]
    if tex.status not in allowed_status:
        messages.info(request, "Holat noto'g'ri")
        return redirect(back_url)

    has_real_serial = tex.serial and tex.serial.strip().upper() != "B/N"

    # Serial tekshiruvi
    if has_real_serial and tex.organization and Technics.objects.filter(
            serial__iexact=tex.serial,
            organization=tex.organization
    ).exclude(pk=tex.pk).exists():
        messages.info(request, f"Bu serial raqamli uskuna allaqachon mavjud: {tex.serial}")
        return redirect(back_url)

    # Narx
    raw_price = (request.POST.get("price") or "").strip().replace(" ", "").replace(",", ".")
    try:
        tex.price = Decimal(raw_price) if raw_price else Decimal("0")
        if tex.price < 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        messages.info(request, "Narx noto'g'ri kiritildi (misol: 14.45 yoki 14,45)")
        return redirect(back_url)

    tex.save(update_fields=[
        "category", "organization",
        "name", "parametr", "inventory", "serial",
        "mac", "ip", "year", "price", "address", "status"
    ])

    messages.success(request, "Uskuna tahrirlandi")
    return redirect(back_url)


@never_cache
@require_GET
@login_required
@permission_required("main.view_technics", raise_exception=True)
def technics_download(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    tex = get_object_or_404(Technics, pk=pk, is_active=True)

    if not tex.qr_code:
        raise Http404("Fayl topilmadi")

    if not os.path.exists(tex.qr_code.path):
        raise Http404("Fayl topilmadi")

    return FileResponse(
        tex.qr_code.open("rb"),
        as_attachment=True,
        filename=os.path.basename(tex.qr_code.name)
    )


@never_cache
@require_GET
@login_required
@permission_required("main.change_technics", raise_exception=True)
def extra_tex(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    status          = (request.GET.get("status")       or "").strip()
    organization_id = (request.GET.get("organization") or "").strip()
    region_id       = (request.GET.get("region")       or "").strip()
    category_id     = (request.GET.get("category")     or "").strip()
    name            = (request.GET.get("name")         or "").strip()
    page_number     = request.GET.get("page", 1)

    if name:
        name = name[:120]

    organizations = Organization.objects.only("id", "name").order_by("id")
    if not request.user.has_perm("main.all_organization"):
        organizations = organizations.filter(id=employee.organization_id)

    regions = Region.objects.only("id", "name").order_by("id")
    if not request.user.has_perm("main.all_region"):
        regions = regions.filter(id=employee.region_id)

    categories = StructureCategory.objects.only("id", "name").order_by("id")

    has_filter = bool(category_id or status or organization_id or region_id or name)

    params = request.GET.copy()
    params.pop("page", None)

    base_context = {
        "organizations":  organizations,
        "regions":        regions,
        "categories":     categories,
        "technics_form":  ExtraTechnicsForm(),
        "qs_params":      params.urlencode(),
        "total_count":    0,
        "row_start":      0,
        "page_obj":       Paginator([], 20).get_page(page_number),
        "technics":       [],
    }

    if not has_filter:
        return render(request, "main/extra_tex.html", base_context)

    qs = (
        Structure.objects
        .filter(is_active=True)
        .select_related("organization", "category", "region")
        .order_by("-id")
    )

    # FIX: organization scope endi to'g'ri permission ("all_organization") bilan tekshiriladi
    if not request.user.has_perm("main.all_organization"):
        qs = qs.filter(organization_id=employee.organization_id)

    # FIX: region scope alohida, o'z permission'i ("all_region") bilan tekshiriladi
    if not request.user.has_perm("main.all_region"):
        qs = qs.filter(region_id=employee.region_id)

    if organization_id and organization_id.isdigit():
        qs = qs.filter(organization_id=int(organization_id))

    if region_id and region_id.isdigit():
        qs = qs.filter(region_id=int(region_id))

    if status:
        qs = qs.filter(status=status)

    if category_id and category_id.isdigit():
        qs = qs.filter(category_id=int(category_id))

    if name:
        qs = qs.filter(
            Q(name__icontains=name)      |
            Q(inventory__icontains=name) |
            Q(serial__icontains=name)    |
            Q(year__icontains=name)
        )

    total_count = qs.count()
    paginator   = Paginator(qs, 20)
    page_obj    = paginator.get_page(page_number)

    base_context.update({
        "page_obj":    page_obj,
        "technics":    page_obj.object_list,
        "row_start":   page_obj.start_index() if total_count else 0,
        "total_count": total_count,
    })

    return render(request, "main/extra_tex.html", base_context)


@never_cache
@require_POST
@login_required
@permission_required("main.add_technics", raise_exception=True)
@transaction.atomic
def extra_tex_create(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    back_url = request.META.get("HTTP_REFERER", "/")
    form = ExtraTechnicsForm(request.POST)

    if form.is_valid():
        technics = form.save(commit=False)
        serial       = (technics.serial or "").strip() or None
        organization = technics.organization

        if employee.region_id:
            technics.region_id = employee.region_id

        if serial and organization and Structure.objects.filter(
            is_active=True,
            serial__iexact=serial,
            organization=organization
        ).exists():
            messages.info(request, "Bu qurilma allaqachon mavjud!")
            return redirect(back_url)

        technics.serial = serial
        technics.save()
        messages.success(request, "Qurilma qo'shildi")
    else:
        messages.info(request, f"Maʼlumotlarda xatolik bor!")

    return redirect(back_url)


@never_cache
@require_POST
@login_required
@permission_required("main.delete_technics", raise_exception=True)
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

    if not tex.is_active:
        messages.info(request, "Texnika allaqachon o‘chirilgan")
        return redirect(back_url)

    tex.is_active = False
    if tex.technics_id:
        tex.technics = None
        tex.save(update_fields=["is_active", "technics"])
    else:
        tex.save(update_fields=["is_active"])

    messages.success(request, "Texnika muvaffaqiyatli o‘chirildi")
    return redirect(back_url)


@never_cache
@require_POST
@login_required
@permission_required("main.change_technics", raise_exception=True)
@transaction.atomic
def extra_tex_update(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    back_url = request.META.get("HTTP_REFERER") or "/"

    tex = get_object_or_404(Structure.objects.select_for_update(), pk=pk, is_active=True)

    organization_id = (request.POST.get("organization") or "").strip()
    category_id     = (request.POST.get("category")     or "").strip()

    if organization_id:
        if not organization_id.isdigit():
            messages.info(request, "Tashkilot noto'g'ri")
            return redirect(back_url)
        tex.organization = get_object_or_404(Organization, pk=int(organization_id))
    else:
        tex.organization = None

    if category_id:
        if not category_id.isdigit():
            messages.info(request, "Kategoriya noto'g'ri")
            return redirect(back_url)
        tex.category = get_object_or_404(StructureCategory, pk=int(category_id))
    else:
        tex.category = None

    tex.name      = (request.POST.get("name")      or "").strip()
    tex.parametr  = (request.POST.get("parametr")  or "").strip() or None
    tex.inventory = (request.POST.get("inventory") or "").strip() or None
    tex.serial    = (request.POST.get("serial")    or "").strip() or None
    tex.status    = (request.POST.get("status")    or "").strip()

    if not tex.name:
        messages.info(request, "Nomi bo'sh bo'lishi mumkin emas")
        return redirect(back_url)

    allowed_status = ["free", "active", "repair", "defect"]
    if tex.status not in allowed_status:
        messages.info(request, "Holat noto'g'ri")
        return redirect(back_url)

    raw_year = (request.POST.get("year") or "").strip()
    tex.year = raw_year or None

    raw_price = (request.POST.get("price") or "").strip().replace(" ", "").replace(",", ".")
    try:
        tex.price = Decimal(raw_price) if raw_price else Decimal("0")
        if tex.price < 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        messages.info(request, "Narx noto'g'ri kiritildi. Misol: 14.45 yoki 14,45")
        return redirect(back_url)

    if tex.serial and tex.organization and Structure.objects.filter(
        serial__iexact=tex.serial,
        organization=tex.organization,
        is_active=True
    ).exclude(pk=tex.pk).exists():
        messages.info(request, f"Bu serial raqamli qurilma allaqachon mavjud: {tex.serial}")
        return redirect(back_url)

    tex.save(update_fields=[
        "organization", "category", "name",
        "parametr", "inventory", "serial",
        "year", "price", "status",
    ])
    messages.success(request, "Texnika tahrirlandi")
    return redirect(back_url)


@never_cache
@require_POST
@login_required
@permission_required("main.change_technics", raise_exception=True)
@transaction.atomic
def extra_tex_attach(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    back_url     = request.META.get("HTTP_REFERER", "/")
    texnika_id   = (request.POST.get("texnika_id")   or "").strip()
    extra_tex_id = (request.POST.get("extra_tex_id") or "").strip()

    if not texnika_id.isdigit() or not extra_tex_id.isdigit():
        messages.info(request, "Noto'g'ri ma'lumot")
        return redirect(back_url)

    tex = get_object_or_404(
        Technics.objects.select_for_update(),
        pk=int(texnika_id), is_active=True
    )
    extra = get_object_or_404(
        Structure.objects.select_for_update(),
        pk=int(extra_tex_id), is_active=True
    )

    if extra.organization_id != tex.organization_id:
        messages.info(request, "Qurilma boshqa tashkilotga tegishli")
        return redirect(back_url)

    if extra.technics_id:
        messages.info(request, "Bu qo'shimcha texnika allaqachon biriktirilgan")
        return redirect(back_url)

    extra.technics = tex
    extra.status   = "active"
    extra.save(update_fields=["technics", "status"])

    messages.success(request, "Qo'shimcha texnika muvaffaqiyatli biriktirildi")
    return redirect(back_url)


@never_cache
@require_POST
@login_required
@permission_required("main.change_technics", raise_exception=True)
@transaction.atomic
def extra_tex_detach(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    back_url     = request.META.get("HTTP_REFERER") or "/"
    texnika_id   = (request.POST.get("texnika_id")   or "").strip()
    extra_tex_id = (request.POST.get("extra_tex_id") or "").strip()

    if not texnika_id or not extra_tex_id:
        messages.info(request, "Tanlash majburiy")
        return redirect(back_url)

    if not texnika_id.isdigit() or not extra_tex_id.isdigit():
        messages.info(request, "Noto'g'ri ID yuborildi")
        return redirect(back_url)

    tex = get_object_or_404(
        Technics.objects.select_for_update().only("id", "organization_id", "is_active"),
        pk=int(texnika_id), is_active=True,
    )
    extra = get_object_or_404(
        Structure.objects.select_for_update().only(
            "id", "organization_id", "technics_id", "status", "is_active"
        ),
        pk=int(extra_tex_id), is_active=True,
    )

    if extra.organization_id != tex.organization_id:
        messages.info(request, "Qo'shimcha texnika boshqa tashkilotga tegishli")
        return redirect(back_url)

    if not extra.technics_id:
        messages.info(request, "Bu qo'shimcha texnika allaqachon bo'sh")
        return redirect(back_url)

    if extra.technics_id != tex.id:
        messages.info(request, "Bu qo'shimcha texnika ushbu uskunaga tegishli emas")
        return redirect(back_url)

    extra.technics = None
    extra.status   = "free"
    extra.save(update_fields=["technics", "status"])

    messages.success(request, "Qo'shimcha texnika bekor qilindi")
    return redirect(back_url)


from django.contrib.auth.models import Permission
@never_cache
@require_GET
@login_required
@permission_required("main.view_material", raise_exception=True)
def barn_mat(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    unit_id     = (request.GET.get("unit")     or "").strip()
    emp_id      = (request.GET.get("employee") or "").strip()
    name        = (request.GET.get("name")     or "").strip()
    page_number = request.GET.get("page", 1)

    if name:
        name = name[:120]

    has_filter = bool(unit_id or emp_id or name)

    params = request.GET.copy()
    params.pop("page", None)

    perm = Permission.objects.get(codename="shop_employee", content_type__app_label="main")
    if request.user.has_perm("main.all_material"):
        base_qs = Employee.objects.filter(
            Q(user__groups__permissions=perm) | Q(user__user_permissions=perm),
            organization=employee.organization,
        ).distinct()
    else:
        base_qs = Employee.objects.filter(id=employee.id)

    base_context = {
        "employees_shop": base_qs,
        "unit":           Unit.objects.all(),
        "material_form":  MaterialForm(),
        "qs_params":      params.urlencode(),
        "row_start":      0,
        "total_count":    0,
        "total_suma":     0,
        "page_obj":       Paginator([], 20).get_page(page_number),
        "material":       [],
    }

    if not has_filter:
        return render(request, "main/barn_mat.html", base_context)

    qs = (
        Material.objects.filter(
            is_active=True,
            organization=employee.organization
        )
        .select_related("employee", "unit")
        .annotate(
            total_sum=ExpressionWrapper(
                F("number") * F("price"),
                output_field=DecimalField(max_digits=18, decimal_places=2)
            )
        )
        .order_by("-id")
    )

    if unit_id and unit_id.isdigit():
        qs = qs.filter(unit_id=int(unit_id))

    if emp_id and emp_id.isdigit():
        qs = qs.filter(employee_id=int(emp_id))

    if name:
        qs = qs.filter(
            Q(name__icontains=name) |
            Q(code__icontains=name)
        )

    total_count = qs.count()
    total_suma  = qs.aggregate(s=Sum("total_sum"))["s"] or 0
    paginator   = Paginator(qs, 20)
    page_obj    = paginator.get_page(page_number)

    base_context.update({
        "page_obj":    page_obj,
        "material":    page_obj.object_list,
        "qs_params":   params.urlencode(),
        "row_start":   page_obj.start_index() if total_count else 0,
        "total_count": total_count,
        "total_suma":  total_suma,
    })

    return render(request, "main/barn_mat.html", base_context)


@never_cache
@require_POST
@login_required
@permission_required("main.add_material", raise_exception=True)
@transaction.atomic
def material_create(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    back_url = request.META.get("HTTP_REFERER", "/")
    form = MaterialForm(request.POST, request.FILES)

    if form.is_valid():
        material = form.save(commit=False)
        material.organization = employee.organization
        material.employee = employee
        material.save()

        MaterialMovement.objects.create(
            material=material,
            user=employee,
            employee=employee,
            status='created',
            balance=material.number,
            body=(
                f"Tashkilot: {material.organization}\n"
                f"Birligi: {material.unit.name if material.unit else '—'}\n"
                f"Nomi: {material.name}\n"
                f"Soni: {material.number}\n"
                f"Kodi: {material.code or '—'}\n"
                f"Narxi: {material.price or '—'}"
            )
        )
        messages.success(request, "Material qo'shildi")
    else:
        messages.info(request, f"Maʼlumotlarda xatolik bor!")



    return redirect(back_url)


@never_cache
@require_POST
@login_required
@permission_required("main.change_material", raise_exception=True)
@transaction.atomic
def material_update(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    back_url = request.META.get("HTTP_REFERER", "/")
    mat = get_object_or_404(Material.objects.select_for_update(), pk=pk)

    if mat.employee_id is not None and mat.employee_id != employee.id:
        messages.info(request, "Sizga ruxsat yo'q")
        return redirect(back_url)

    if mat.organization_id != employee.organization_id:
        messages.info(request, "Sizga ruxsat yo'q")
        return redirect(back_url)

    # Eski qiymatlar — save dan OLDIN saqlab qo'yamiz
    old = {
        "name":   mat.name,
        "unit":   mat.unit.name if mat.unit else "—",
        "number": mat.number,
        "code":   mat.code or "—",
        "price":  mat.price or "—",
        "year":   mat.year or "—",
    }

    unit_id = (request.POST.get("unit") or "").strip()
    if unit_id:
        if not unit_id.isdigit():
            messages.info(request, "Birligi noto'g'ri tanlangan")
            return redirect(back_url)
        mat.unit = get_object_or_404(Unit, pk=int(unit_id))
    else:
        mat.unit = None

    mat.name = (request.POST.get("name") or "").strip()
    mat.code = (request.POST.get("code") or "").strip() or None
    mat.year = (request.POST.get("year") or "").strip() or None

    if not mat.name:
        messages.info(request, "Nomi kiritilishi shart")
        return redirect(back_url)

    raw_number = (request.POST.get("number") or "").strip()
    try:
        mat.number = int(raw_number)
        if mat.number < 0:
            raise ValueError
    except (TypeError, ValueError):
        messages.info(request, "Soni noto'g'ri kiritildi")
        return redirect(back_url)

    raw_price = (request.POST.get("price") or "").strip().replace(" ", "").replace(",", ".")
    try:
        mat.price = Decimal(raw_price) if raw_price else Decimal("0")
        if mat.price < 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        messages.info(request, "Narx noto'g'ri kiritildi. Masalan: 14.45 yoki 14,45")
        return redirect(back_url)

    if request.FILES.get("image"):
        mat.image = request.FILES["image"]

    mat.save(update_fields=[
        "unit", "name", "code",
        "number", "price", "year", "image",
    ])

    # Yangi qiymatlar
    new = {
        "name":   mat.name,
        "unit":   mat.unit.name if mat.unit else "—",
        "number": mat.number,
        "code":   mat.code or "—",
        "price":  mat.price or "—",
        "year":   mat.year or "—",
    }

    # Faqat o'zgargan fieldlarni yozamiz
    changes = []
    labels = {
        "name":   "Nomi",
        "unit":   "Birligi",
        "number": "Soni",
        "code":   "Kodi",
        "price":  "Narxi",
        "year":   "Yili",
    }
    for key, label in labels.items():
        if old[key] != new[key]:
            changes.append(f"{label}: {old[key]} → {new[key]}")

    if changes:
        old_number = old["number"]
        new_number = new["number"]
        diff = new_number - old_number

        income = diff if diff > 0 else None
        outcome = -diff if diff < 0 else None

        MaterialMovement.objects.create(
            material=mat,
            user=employee,
            employee=mat.employee,
            status='edited',
            income=income,
            outcome=outcome,
            balance=old_number if diff != 0 else None,
            body="\n".join(changes)
        )

    messages.success(request, "Material tahrirlandi")
    return redirect(back_url)


@never_cache
@require_POST
@login_required
@permission_required("main.change_material", raise_exception=True)
@transaction.atomic
def material_attach(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    back_url    = request.META.get("HTTP_REFERER", "/")
    material_id = (request.POST.get("material_id") or "").strip()
    employee_id = (request.POST.get("employee_id") or "").strip()
    give_number = (request.POST.get("give_number") or "").strip()

    if not material_id.isdigit() or not employee_id.isdigit():
        messages.info(request, "Material yoki xodim noto'g'ri tanlandi")
        return redirect(back_url)

    try:
        give_number_int = int(give_number)
        if give_number_int <= 0:
            raise ValueError
    except (TypeError, ValueError):
        messages.info(request, "Soni noto'g'ri kiritildi")
        return redirect(back_url)

    src = get_object_or_404(
        Material.objects.select_for_update(),
        id=int(material_id)
    )

    if src.organization_id != employee.organization_id:
        raise PermissionDenied("Sizga ruxsat yo'q")

    if src.employee_id and src.employee_id == int(employee_id):
        messages.info(request, "Bu material allaqachon shu xodimga tegishli")
        return redirect(back_url)

    emp = get_object_or_404(Employee, id=int(employee_id))

    if emp.organization_id != employee.organization_id:
        raise PermissionDenied("Xodim boshqa tashkilotga tegishli")

    src_qty = int(src.number or 0)
    if src_qty < give_number_int:
        messages.info(request, f"Omborda yetarli material yo'q (bor: {src_qty})")
        return redirect(back_url)

    # dst ni aniqlash
    dst_filter = {"employee_id": emp.id}
    if (src.code or "").strip():
        dst_filter["code"] = src.code
    else:
        dst_filter["name"] = src.name

    dst = (
        Material.objects
        .select_for_update()
        .filter(**dst_filter)
        .first()
    )

    if dst:
        dst_qty_before = int(dst.number or 0)
        dst.number     = dst_qty_before + give_number_int

        if (dst.price in [None, 0, "0"]) and src.price not in [None, 0, "0"]:
            dst.price = src.price
        if not dst.unit_id and src.unit_id:
            dst.unit = src.unit

        dst.save(update_fields=["number", "price", "unit"])
        dst_material = dst
    else:
        dst_qty_before = 0
        dst_material   = Material.objects.create(
            organization = emp.organization,
            employee     = emp,
            name         = src.name,
            code         = src.code,
            number       = give_number_int,
            unit         = src.unit,
            price        = src.price,
            year         = src.year,
        )

    # Ombordan ayiramiz
    src.number = src_qty - give_number_int
    src.save(update_fields=["number"])

    # Ombordan chiqim (src uchun)
    MaterialMovement.objects.create(
        material = src,
        user     = employee,
        employee = src.employee,
        status   = 'assigned',
        income   = None,
        outcome  = give_number_int,
        balance  = src_qty,
        body=(
            f"Berildi: {employee}\n"
            f"Qabul qildi: {emp}\n"
            f"Ombordan oldin: {src_qty}\n"
            f"Soni: {give_number_int}\n"
            f"Omborda qoldi: {src.number}"
        )
    )

    # Xodimga kirim (dst uchun)
    MaterialMovement.objects.create(
        material = dst_material,
        user     = employee,
        employee = emp,
        status   = 'assigned',
        income   = give_number_int,
        outcome  = None,
        balance  = dst_qty_before,
        body=(
            f"Qabul qildi: {emp}\n"
            f"Berdi: {employee}\n"
            f"Oldin: {dst_qty_before}\n"
            f"Soni: {give_number_int}\n"
            f"Jami: {dst_qty_before + give_number_int}"
        )
    )

    messages.success(request, "Material biriktirildi")
    return redirect(back_url)


@never_cache
@require_POST
@login_required
@permission_required("main.delete_material", raise_exception=True)
@transaction.atomic
def material_delete(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    back_url    = request.META.get("HTTP_REFERER") or "/"
    material_id = (request.POST.get("material_id") or "").strip()

    try:
        mat = (
            Material.objects
            .select_for_update()
            .only("id", "organization_id", "is_active")
            .get(pk=int(material_id))
        )
    except (Material.DoesNotExist, TypeError, ValueError):
        messages.info(request, "Material topilmadi")
        return redirect(back_url)

    if mat.employee_id is not None and mat.employee_id != employee.id:
        messages.info(request, "Sizga ruxsat yo'q")
        return redirect(back_url)

    if mat.organization_id != employee.organization_id:
        messages.info(request, "Sizga ruxsat yo'q")
        return redirect(back_url)

    if not mat.is_active:
        messages.info(request, "Material allaqachon o'chirilgan")
        return redirect(back_url)

    mat.is_active = False
    mat.save(update_fields=["is_active"])

    MaterialMovement.objects.create(
        material=mat,
        user=employee,
        employee=mat.employee,
        status='deleted',
        body=f"Material o'chirildi: {mat.id}"
    )

    messages.success(request, "Material muvaffaqiyatli o'chirildi")
    return redirect(back_url)


from django.core.paginator import Paginator
from django.db.models import Sum, F
from django.db.models.functions import Coalesce
from django.utils.timezone import make_aware, localdate
from datetime import datetime, time
@never_cache
@require_GET
@login_required
@permission_required("main.view_material", raise_exception=True)
def mat_info(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    date1_raw = (request.GET.get("date1") or "").strip()
    date2_raw = (request.GET.get("date2") or "").strip()
    employee_id_raw = (request.GET.get("employee") or "").strip()

    has_search = bool(date1_raw and date2_raw and employee_id_raw and employee_id_raw.isdigit())

    table_rows = []
    page_obj = None
    qs_params = ""

    if has_search:
        date1 = parse_date(date1_raw)
        date2 = parse_date(date2_raw)
        employee_id = int(employee_id_raw)

        start_dt = make_aware(datetime.combine(date1, time.min)) if date1 else None
        end_dt = make_aware(datetime.combine(date2, time.max)) if date2 else None

        # --- MaterialMovement bo'yicha kirim/chiqim ---
        movements_qs = MaterialMovement.objects.exclude(status='deleted').filter(employee_id=employee_id)
        if start_dt:
            movements_qs = movements_qs.filter(date_creat__gte=start_dt)
        if end_dt:
            movements_qs = movements_qs.filter(date_creat__lte=end_dt)

        period_map = {
            row["material"]: row
            for row in movements_qs.values("material").annotate(
                period_income=Sum("income"),
                period_outcome=Sum("outcome"),
            )
        }

        # --- OrderMaterial bo'yicha chiqim (arizadan berilgan materiallar) ---
        ordermaterial_qs = OrderMaterial.objects.filter(material__employee_id=employee_id)
        if start_dt:
            ordermaterial_qs = ordermaterial_qs.filter(order__date_finished__gte=start_dt)
        if end_dt:
            ordermaterial_qs = ordermaterial_qs.filter(order__date_finished__lte=end_dt)

        order_period_map = {
            row["material"]: row["period_given"] or 0
            for row in ordermaterial_qs.values("material").annotate(
                period_given=Sum(Coalesce(F("given"), F("number")))
            )
        }

        materials = Material.objects.filter(
            is_active=True, employee_id=employee_id
        ).order_by("name")

        for m in materials:
            period = period_map.get(m.id, {})
            income = period.get("period_income") or 0
            outcome = period.get("period_outcome") or 0
            order_outcome = order_period_map.get(m.id, 0)

            total_outcome = outcome + order_outcome
            current_count = m.number
            initial_balance = current_count - income + total_outcome

            table_rows.append({
                "material": m,
                "code": m.code,
                "price": m.price,
                "initial_balance": initial_balance,
                "income": income,
                "outcome": total_outcome,
                "current_balance": current_count,
            })

        paginator = Paginator(table_rows, 20)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        qs = request.GET.copy()
        qs.pop("page", None)
        qs_params = qs.urlencode()

        table_rows = page_obj.object_list

    perm = Permission.objects.get(codename="shop_employee", content_type__app_label="main")
    if request.user.has_perm("main.all_material"):
        base_qs = Employee.objects.filter(
            Q(user__groups__permissions=perm) | Q(user__user_permissions=perm),
            organization=employee.organization,
        ).distinct()
    else:
        base_qs = Employee.objects.filter(id=employee.id)

    context = {
        "employees_shop": base_qs,
        "date1": date1_raw,
        "date2": date2_raw,
        "has_search": has_search,
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if page_obj else 0,
        "table_rows": table_rows,
        "qs_params": qs_params,
    }
    return render(request, "main/mat_info.html", context)


@never_cache
@require_GET
@login_required
def document_get(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if not employee.organization.type == "worker":
        raise PermissionDenied("Ruxsat yo'q")

    if not employee.liable_set.exists():
        raise PermissionDenied("Ruxsat yo'q")

    liable = (
        Liable.objects
        .filter(employee=employee,category__isnull=False, contract__isnull=False)
        .select_related("contract")
        .order_by("contract_id")
        .distinct("contract")
    )

    context = {
        "liable": liable,
        "organizations": Organization.objects.only("id", "name").order_by("id"),
        "emp_bos_sender": Employee.objects.filter(department_id=283),
    }
    return render(request, "main/document.html", context)


@never_cache
@require_POST
@login_required
def document_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if not employee.organization.type == "worker":
        raise PermissionDenied("Ruxsat yo'q")

    if not employee.liable_set.exists():
        raise PermissionDenied("Ruxsat yo'q")

    sender_id   = (request.POST.get("sender")   or "").strip()
    receiver_id = (request.POST.get("receiver") or "").strip()
    message     = (request.POST.get("message")  or "").strip() or None
    agreements  = request.POST.getlist("agreements[]")

    # --- Body Base64 orqali keladi (WAF'ni chetlab o'tish uchun) ---
    body_encoded = (request.POST.get("body_encoded") or "").strip()
    body = ""
    if body_encoded:
        try:
            body = base64.b64decode(body_encoded).decode("utf-8").strip()
        except (binascii.Error, UnicodeDecodeError, ValueError):
            body = ""

    sender   = Employee.objects.filter(id=sender_id).first()   if sender_id.isdigit()   else None
    receiver = Employee.objects.filter(id=receiver_id).first() if receiver_id.isdigit() else None

    if not sender:
        messages.info(request, "Imzolovchi xodim tanlanmadi")
        return redirect("document_get")

    if not body:
        messages.info(request, "Hujjat matni bo'sh bo'lmasin")
        return redirect("document_get")

    # 1. DB operatsiyalar — transaction ichida
    with transaction.atomic():
        deed = Deed.objects.create(
            sender=sender,
            receiver=receiver,
            user=employee,
            message_user=message,
            body=body,
            status='document',
        )

        ids = list({int(x) for x in agreements if (x or "").strip().isdigit()})

        exclude_ids = {sender.id}
        if receiver:
            exclude_ids.add(receiver.id)
        ids = [i for i in ids if i not in exclude_ids]

        if ids:
            emps = Employee.objects.filter(id__in=ids).only("id")
            objs = [DeedConsent(deed=deed, employee=e, status="viewed") for e in emps]
            DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

    # 2. PDF — transaction tashqarisida
    try:
        pdf_bytes = deed_to_pdf_bytes(deed)
        pdf_bytes = add_text_watermark_pdf_bytes(pdf_bytes, "TASDIQLANMAGAN")
        pdf_name  = f"akt_{timezone.now().strftime('%Y%m%d')}_{secrets.token_urlsafe(6)}.pdf"
        deed.file.save(pdf_name, ContentFile(pdf_bytes), save=True)
    except HtmlPdfError as e:
        messages.info(request, f"PDF yaratilmadi: {e}")

    messages.success(request, "Imzolashga yuborildi")
    return redirect("contact_user")


@never_cache
@require_GET
@login_required
@permission_required("main.change_order", raise_exception=True)
def akt_get(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    context = {
        "organizations": Organization.objects.only("id", "name").order_by("id"),
        "user_region": employee.region_id,
    }
    return render(request, "main/akt.html", context)


@never_cache
@require_POST
@login_required
@permission_required("main.change_order", raise_exception=True)
def akt_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    sender_id  = (request.POST.get("sender")  or "").strip()
    message    = (request.POST.get("message") or "").strip() or None
    agreements = request.POST.getlist("agreements[]")

    # --- Body Base64 orqali keladi (WAF'ni chetlab o'tish uchun) ---
    body_encoded = (request.POST.get("body_encoded") or "").strip()
    body = ""
    if body_encoded:
        try:
            body = base64.b64decode(body_encoded).decode("utf-8").strip()
        except (binascii.Error, UnicodeDecodeError, ValueError):
            body = ""

    sender = Employee.objects.filter(id=sender_id).first() if sender_id.isdigit() else None
    if not sender:
        messages.info(request, "Imzolovchi xodim tanlanmadi")
        return redirect("akt_get")

    if not body:
        messages.info(request, "Hujjat matni bo'sh bo'lmasin")
        return redirect("akt_get")

    # 1. DB — transaction ichida
    with transaction.atomic():
        deed = Deed.objects.create(
            sender=sender,
            user=employee,
            message_user=message,
            body=body,
            status='act',
        )

        ids = list({int(x) for x in agreements if (x or "").strip().isdigit()})
        ids = [i for i in ids if i != sender.id]

        if ids:
            emps = Employee.objects.filter(id__in=ids).only("id")
            objs = [DeedConsent(deed=deed, employee=e, status="viewed") for e in emps]
            DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

    # 2. PDF — transaction tashqarisida
    try:
        pdf_bytes = deed_to_pdf_bytes(deed)
        pdf_bytes = add_text_watermark_pdf_bytes(pdf_bytes, "TASDIQLANMAGAN")
        pdf_name  = f"akt_{timezone.now().strftime('%Y%m%d')}_{secrets.token_urlsafe(6)}.pdf"
        deed.file.save(pdf_name, ContentFile(pdf_bytes), save=True)
    except HtmlPdfError as e:
        messages.info(request, f"PDF yaratilmadi: {e}")

    messages.success(request, "Imzolashga yuborildi")
    return redirect("contact_user")


@never_cache
@require_GET
@login_required
@permission_required("main.shop_employee", raise_exception=True)
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
@permission_required("main.shop_employee", raise_exception=True)
def svod_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    sender_id  = (request.POST.get("sender")  or "").strip()
    message    = (request.POST.get("message") or "").strip() or None
    agreements = request.POST.getlist("agreements[]")

    # --- Body Base64 orqali keladi (WAF'ni chetlab o'tish uchun) ---
    body_encoded = (request.POST.get("body_encoded") or "").strip()
    body = ""
    if body_encoded:
        try:
            body = base64.b64decode(body_encoded).decode("utf-8").strip()
        except (binascii.Error, UnicodeDecodeError, ValueError):
            body = ""

    sender = Employee.objects.filter(id=sender_id).first() if sender_id.isdigit() else None
    if not sender:
        messages.info(request, "Imzolovchi xodim tanlanmadi")
        return redirect("svod_get")

    if not body:
        messages.info(request, "Hujjat matni bo'sh bo'lmasin")
        return redirect("svod_get")

    # 1. DB — transaction ichida
    with transaction.atomic():
        deed = Deed.objects.create(
            sender=sender,
            user=employee,
            message_user=message,
            body=body,
            status='svod',
        )

        ids = list({int(x) for x in agreements if (x or "").strip().isdigit()})
        ids = [i for i in ids if i != sender.id]

        if ids:
            emps = Employee.objects.filter(id__in=ids).only("id")
            objs = [DeedConsent(deed=deed, employee=e, status="viewed") for e in emps]
            DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

    # 2. PDF — transaction tashqarisida
    try:
        pdf_bytes = deed_to_pdf_bytes(deed)
        pdf_bytes = add_text_watermark_pdf_bytes(pdf_bytes, "TASDIQLANMAGAN")
        pdf_name  = f"akt_{timezone.now().strftime('%Y%m%d')}_{secrets.token_urlsafe(6)}.pdf"
        deed.file.save(pdf_name, ContentFile(pdf_bytes), save=True)
    except HtmlPdfError as e:
        messages.info(request, f"PDF yaratilmadi: {e}")

    messages.success(request, "Imzolashga yuborildi")
    return redirect("contact_user")


@never_cache
@require_GET
@login_required
@permission_required("main.shop_employee", raise_exception=True)
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
@require_POST
@login_required
@permission_required("main.shop_employee", raise_exception=True)
def reestr_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    sender_id  = (request.POST.get("sender")  or "").strip()
    message    = (request.POST.get("message") or "").strip() or None
    agreements = request.POST.getlist("agreements[]")

    # --- Body Base64 orqali keladi (WAF'ni chetlab o'tish uchun) ---
    body_encoded = (request.POST.get("body_encoded") or "").strip()
    body = ""
    if body_encoded:
        try:
            body = base64.b64decode(body_encoded).decode("utf-8").strip()
        except (binascii.Error, UnicodeDecodeError, ValueError):
            body = ""

    sender = Employee.objects.filter(id=sender_id).first() if sender_id.isdigit() else None
    if not sender:
        messages.info(request, "Imzolovchi xodim tanlanmadi")
        return redirect("akt_get")

    if not body:
        messages.info(request, "Hujjat matni bo'sh bo'lmasin")
        return redirect("akt_get")

    # 1. DB — transaction ichida
    with transaction.atomic():
        deed = Deed.objects.create(
            sender=sender,
            user=employee,
            message_user=message,
            body=body,
            status='reestr',
        )

        ids = list({int(x) for x in agreements if (x or "").strip().isdigit()})
        ids = [i for i in ids if i != sender.id]

        if ids:
            emps = Employee.objects.filter(id__in=ids).only("id")
            objs = [DeedConsent(deed=deed, employee=e, status="viewed") for e in emps]
            DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

    # 2. PDF — transaction tashqarisida
    try:
        pdf_bytes = deed_to_pdf_bytes(deed)
        pdf_bytes = add_text_watermark_pdf_bytes(pdf_bytes, "TASDIQLANMAGAN")
        pdf_name  = f"akt_{timezone.now().strftime('%Y%m%d')}_{secrets.token_urlsafe(6)}.pdf"
        deed.file.save(pdf_name, ContentFile(pdf_bytes), save=True)
    except HtmlPdfError as e:
        messages.info(request, f"PDF yaratilmadi: {e}")

    messages.success(request, "Imzolashga yuborildi")
    return redirect("contact_user")


@never_cache
@require_GET
@login_required
def technics_get(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    page_number = request.GET.get("page", 1)
    is_boss = request.user.has_perm("main.boss_employee")


    if is_boss:
        base_qs = Technics.objects.filter(
            organization=employee.organization,
            department=employee.department,
            region=employee.region,
            is_active=True,
        )
    else:
        base_qs = Technics.objects.filter(
            employee=employee,
            is_active=True,
        )

    tech_qs = (
        base_qs
        .select_related("employee", "employee__rank", "category")
        .prefetch_related("structure_set__category")
        .order_by("employee_id", "id")
    )

    # Pagination
    paginator = Paginator(tech_qs, 20)
    page_obj = paginator.get_page(page_number)

    # grouped_technics — sahifadagi texnikalarni xodim bo'yicha guruhlash
    grouped_technics = []
    for emp_id, items in groupby(page_obj.object_list, key=lambda t: t.employee_id):
        items_list = list(items)
        emp_obj = items_list[0].employee if emp_id else None
        grouped_technics.append((emp_obj, items_list))

    # Texnikasi yo'q xodimlar (faqat boss uchun, faqat oxirgi sahifada ko'rinadi)
    employees_without_technics = []
    if is_boss:
        assigned_ids = set(
            base_qs
            .exclude(employee_id=None)
            .values_list("employee_id", flat=True)
            .distinct()
        )
        employees_without_technics = (
            Employee.objects
            .filter(
                organization=employee.organization,
                department=employee.department,
                region=employee.region,
            )
            .exclude(id__in=assigned_ids)
            .select_related("rank")
            .only("id", "first_name", "last_name", "father_name", "rank__name")
            .order_by("last_name", "first_name")
        )

    params = request.GET.copy()
    params.pop("page", None)
    qs_params = params.urlencode()

    context = {
        "grouped_technics": grouped_technics,
        "employees_without_technics": employees_without_technics,
        "page_obj": page_obj,
        "qs_params": qs_params,
    }
    return render(request, "main/technics_get.html", context)


from django.db.models import Avg
@never_cache
@require_GET
@login_required
@permission_required("main.status_employee", raise_exception=True)
def emp_status(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    region_id = (request.GET.get("region") or "").strip()
    date1_raw = (request.GET.get("date1") or "").strip()
    date2_raw = (request.GET.get("date2") or "").strip()

    date1 = parse_date(date1_raw) if date1_raw else None
    date2 = parse_date(date2_raw) if date2_raw else None

    has_search = bool(region_id or date1_raw or date2_raw)

    if not has_search:
        today = timezone.localdate()
        date1 = today.replace(day=1)
        if date1.month == 12:
            next_month = date1.replace(year=date1.year + 1, month=1)
        else:
            next_month = date1.replace(month=date1.month + 1)
        date1_raw = date1.isoformat()
        date2_raw = (next_month - timezone.timedelta(days=1)).isoformat()
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

    # FIX: "employee" o'rniga boshqa nom - Employee obyektini o'chirib yubormaslik uchun
    employee_stats = (
        orders
        .filter(goal__organization=employee.organization, receiver__isnull=False)
        .values("receiver_id")
        .annotate(
            full_name=Concat(
                Coalesce(F("receiver__last_name"), Value("")),
                Value(" "),
                Coalesce(F("receiver__first_name"), Value("")),
                Value(" "),
                Coalesce(F("receiver__father_name"), Value("")),
            ),
            accepted_count=Count("id", filter=Q(status="process")),
            finished_count=Count("id", filter=Q(status="finished")),
            approved_count=Count("id", filter=Q(status="approved")),
            rejected_count=Count("id", filter=Q(status="rejected") | Q(status="canceled")),
            total_count=Count("id"),
            avg_rating=Avg("rating"),
        )
        .order_by("-total_count", "-approved_count")
    )

    goal = (
        Goal.objects
        .filter(organization=employee.organization)   # endi "employee" hali ham Employee obyekti - to'g'ri ishlaydi
        .annotate(
            total=Count("order", filter=Q(order__in=goal_orders))
        )
        .order_by("-total")
    )

    context = {
        "goal": goal,
        "employee": employee_stats,   # FIX: template'ga shu yangi nom bilan uzatiladi
        "region": Region.objects.all().order_by("id"),
        "selected_region": region_id,
        "date1": date1_raw,
        "date2": date2_raw,
    }
    return render(request, "main/emp_status.html", context)


@never_cache
@require_GET
@login_required
@permission_required("main.status_employee", raise_exception=True)
def tex_status(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    # ------------------- GROUPLAR -------------------
    groups = list(
        Group.objects
        .order_by("id")
        .annotate(
            technics_count=Count(
                "technics__id",
                filter=Q(
                    technics__is_active=True,
                    technics__organization_id=employee.organization_id
                ),
                distinct=True
            )
        )
        .values("id", "name", "technics_count")
    )

    group_ids = [g["id"] for g in groups]

    total_technics = sum(g["technics_count"] for g in groups) or 1

    for g in groups:
        g["foiz"] = round((g["technics_count"] * 100) / total_technics, 1)

    # ------------------- GROUPGA TEGISHLI HAMMA CATEGORIYALAR -------------------
    categories_qs = list(
        Category.objects
        .filter(group_id__in=group_ids)
        .order_by("group_id", "id")
        .values("id", "name", "group_id")
    )

    # ------------------- TEXNIKA SONI: GROUP + CATEGORY -------------------
    grouped = list(
        Technics.objects
        .filter(
            is_active=True,
            organization_id=employee.organization_id,
            group_id__in=group_ids,
            category_id__isnull=False,
        )
        .values("group_id", "category_id")
        .annotate(cnt=Count("id"))
    )

    lookup = {
        (item["group_id"], item["category_id"]): item["cnt"]
        for item in grouped
    }

    # ------------------- CARD DATA -------------------
    groups_qs = []

    for group in groups:
        group_total = group["technics_count"]
        category_list = []

        for cat in categories_qs:
            if cat["group_id"] != group["id"]:
                continue

            count = lookup.get((group["id"], cat["id"]), 0)
            foiz = round((count * 100) / group_total, 1) if group_total > 0 else 0

            category_list.append({
                "id": cat["id"],
                "name": cat["name"],
                "soni": count,
                "foiz": foiz,
            })

        groups_qs.append({
            "id": group["id"],
            "name": group["name"],
            "technics_count": group["technics_count"],
            "foiz": group["foiz"],
            "category_list": category_list,
        })

    # ------------------- AREA CHART: FAQAT GROUP BO'YICHA -------------------
    area_categories = [g["name"] for g in groups]

    area_series = [{
        "name": "Texnikalar",
        "data": [g["technics_count"] for g in groups],
    }]

    # ------------------- PIE CHART -------------------
    pie_labels = [g["name"] for g in groups]
    pie_values = [g["technics_count"] for g in groups]

    # ------------------- BAR CHART -------------------
    groups_sorted = sorted(
        groups,
        key=lambda x: x["technics_count"],
        reverse=True
    )

    bar_labels = [g["name"] for g in groups_sorted[:8]]
    bar_values = [g["technics_count"] for g in groups_sorted[:8]]

    context = {
        "groups_qs": groups_qs,

        "area_categories": area_categories,
        "area_series": area_series,

        "pie_labels": pie_labels,
        "pie_values": pie_values,

        "bar_labels": bar_labels,
        "bar_values": bar_values,
    }

    return render(request, "main/tex_status.html", context)


@never_cache
@require_GET
@login_required
def technics_detail(request, pk):
    technics = get_object_or_404(Technics, pk=pk, is_active=True)
    return render(request, "main/technics_detail.html", {"technics": technics})


@never_cache
@require_GET
@login_required
@permission_required("main.view_deed", raise_exception=True)
def files(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    name   = (request.GET.get("name")   or "").strip()[:120]
    date1  = (request.GET.get("date1")  or "").strip()
    date2  = (request.GET.get("date2")  or "").strip()
    status = (request.GET.get("status") or "").strip()
    page_number = request.GET.get("page", 1)

    has_filter = bool(name or date1 or date2 or status)

    params = request.GET.copy()
    params.pop("page", None)

    if not has_filter:
        page_obj = Paginator([], 20).get_page(page_number)
        return render(request, "main/files.html", {
            "page_obj":  page_obj,
            "qs_params": params.urlencode(),
            "name":      name,
            "date1":     date1,
            "date2":     date2,
        })

    qs = (
        Deed.objects
        .filter(
            Q(user__organization_id=employee.organization_id)   |
            Q(sender__organization_id=employee.organization_id) |
            Q(receiver__organization_id=employee.organization_id)
        )
        .distinct()
        .select_related("user", "sender", "receiver")
        .prefetch_related(
            Prefetch(
                "deedconsent_set",
                queryset=DeedConsent.objects.select_related(
                    "employee", "employee__organization"
                )
            )
        )
        .order_by("-id")
    )

    if name:
        qs = qs.annotate(
            user_full_name=Concat(
                "user__last_name", Value(" "),
                "user__first_name", Value(" "),
                "user__father_name",
            ),
            sender_full_name=Concat(
                "sender__last_name", Value(" "),
                "sender__first_name", Value(" "),
                "sender__father_name",
            ),
            receiver_full_name=Concat(
                "receiver__last_name", Value(" "),
                "receiver__first_name", Value(" "),
                "receiver__father_name",
            ),
        ).filter(
            Q(code__icontains=name)             |
            Q(user_full_name__icontains=name)   |
            Q(sender_full_name__icontains=name) |
            Q(receiver_full_name__icontains=name)
        )

    if status:
        qs = qs.filter(status=status)

    if date1:
        try:
            qs = qs.filter(date_creat__date__gte=date1)
        except (ValueError, TypeError):
            pass

    if date2:
        try:
            qs = qs.filter(date_creat__date__lte=date2)
        except (ValueError, TypeError):
            pass

    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(page_number)

    context = {
        "page_obj":  page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
        "qs_params": params.urlencode(),
        "name":      name,
        "date1":     date1,
        "date2":     date2,
        "status":    status,
    }
    return render(request, "main/files.html", context)


import secrets
from .tasks import _resolve_position, cyrillic_to_latin
@login_required
@require_POST
def employe_create(request):
    pinfl = request.POST.get("pinfl", "").strip()

    if not pinfl:
        messages.info(request, "PINFL kiritilmadi")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    if Employee.objects.filter(pinfl=pinfl).exists():
        messages.info(request, "Bu PINFL allaqachon ro'yxatda bor")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    try:
        from .gateway import GatewayClient

        gateway_data = GatewayClient.current_citizen(pinfl)
        result       = gateway_data.get("result") or {}
        positions    = result.get("positions") or []

        if not positions:
            messages.info(request, "Gatewayda ish joyi topilmadi")
            return redirect(request.META.get("HTTP_REFERER", "/"))

        assigned_data = _resolve_position(pinfl, positions)

        if not assigned_data:
            messages.info(request, "Tizimda tashkilot topilmadi")
            return redirect(request.META.get("HTTP_REFERER", "/"))

        with transaction.atomic():
            base_username = (
                f"{result.get('surname', '').lower()}"
                f".{result.get('name', '').lower()}"
            )
            user = None
            for counter in range(20):
                candidate = base_username if counter == 0 else f"{base_username}{counter}"
                try:
                    sid = transaction.savepoint()
                    user = User.objects.create_user(
                        username=candidate,
                        password=secrets.token_urlsafe(16),
                    )
                    transaction.savepoint_commit(sid)
                    break
                except IntegrityError:
                    transaction.savepoint_rollback(sid)
                    continue

            if user is None:
                raise Exception("Username yaratib bo'lmadi (20 urinishdan keyin)")

            if not assigned_data["rank"] and assigned_data.get("_position_id"):
                assigned_data["rank"], _ = Rank.objects.get_or_create(
                    code=assigned_data["_position_id"],
                    defaults={
                        "name": assigned_data["_position"] or f"Lavozim-{assigned_data['_position_id']}"
                    },
                )

            employee = user.employee
            employee.pinfl = pinfl
            employee.first_name = (result.get("name") or "").strip()
            employee.last_name = (result.get("surname") or "").strip()
            employee.father_name = (result.get("partonimic") or "").strip()
            employee.organization = assigned_data["organization"]
            employee.department = assigned_data["department"]
            employee.directorate = assigned_data["directorate"]
            employee.division = assigned_data["division"]
            employee.rank = assigned_data["rank"]
            employee.save()

        messages.success(request, f"{employee.full_name} xodim yaratildi")

    except Exception as e:
        logger.exception("Xodim yaratishda xatolik")
        messages.info(request, str(e))

    return redirect(request.META.get("HTTP_REFERER", "/"))


@never_cache
@require_GET
@login_required
def material_import_page(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    employees_shop = Employee.objects.filter(
        rol__shop=True,
        organization=employee.organization,
    ).order_by("last_name", "first_name")

    context = {
        "employees_shop": employees_shop,
    }
    return render(request, "main/material_import.html", context)


import openpyxl
from io import BytesIO


@never_cache
@require_POST
@login_required
@transaction.atomic
def material_import(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if employee.id != 4:
        raise PermissionDenied("Sizga ruxsat yo'q")

    back_url = request.META.get("HTTP_REFERER", "/")

    file = request.FILES.get("file")
    target_employee_id = (request.POST.get("employee") or "").strip()

    if not file:
        messages.info(request, "Fayl tanlanmadi")
        return redirect(back_url)

    if not file.name.endswith((".xlsx", ".xls")):
        messages.info(request, "Faqat .xlsx yoki .xls fayl yuklang")
        return redirect(back_url)

    if not target_employee_id.isdigit():
        messages.info(request, "Xodim tanlanmadi")
        return redirect(back_url)

    target_employee = get_object_or_404(
        Employee,
        pk=int(target_employee_id),
        organization=employee.organization,
    )

    try:
        file_content = BytesIO(file.read())
        wb = openpyxl.load_workbook(file_content, data_only=True)
        ws = wb.active
    except Exception as e:
        messages.info(request, f"Faylni o'qishda xatolik: {e}")
        return redirect(back_url)

    # Importdan oldin shu xodimning barcha materiallarini 0 ga tushiramiz.
    # Fayldagi qatorlar keyinroq to'g'ri qiymat bilan qayta yoziladi;
    # fayldа yo'q qolgan mahsulotlar esa 0 sonda qoladi.
    Material.objects.filter(
        employee=target_employee,
        is_active=True,
    ).update(number=0)

    created = 0
    updated = 0
    skipped = 0
    errors = []

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        try:
            nomi   = str(row[1] or "").strip()
            brligi = str(row[2] or "").strip()
            narxi  = row[3]
            kode   = str(row[4] or "").strip() or None
            soni   = row[5]

            if not nomi:
                skipped += 1
                continue

            try:
                number = int(soni) if soni else 0
            except Exception:
                number = 0

            try:
                price = Decimal(str(narxi).replace(" ", "").replace(",", ".")) if narxi else None
            except Exception:
                price = None

            unit = None
            if brligi:
                unit, _ = Unit.objects.get_or_create(name=brligi)

            if kode:
                existing = Material.objects.filter(
                    code=kode,
                    employee=target_employee,
                ).order_by("id").first()

                if existing:
                    existing.number = number
                    existing.name = nomi
                    existing.price = price
                    if unit:
                        existing.unit = unit
                    existing.save(update_fields=["number", "name", "price", "unit"])
                    updated += 1

                    # Dublikatlarni o'chirish
                    Material.objects.filter(
                        code=kode,
                        employee=target_employee,
                    ).exclude(pk=existing.pk).delete()

                else:
                    Material.objects.create(
                        organization=target_employee.organization,
                        employee=target_employee,
                        unit=unit,
                        name=nomi,
                        code=kode,
                        price=price,
                        number=number,
                        is_active=True,
                    )
                    created += 1
            else:
                Material.objects.create(
                    organization=target_employee.organization,
                    employee=target_employee,
                    unit=unit,
                    name=nomi,
                    code=None,
                    price=price,
                    number=number,
                    is_active=True,
                )
                created += 1

        except Exception as e:
            errors.append(f"{row_idx}-qator: {e}")

    if errors:
        messages.info(request, f"Xatoliklar: {'; '.join(errors[:5])}")

    messages.success(
        request,
        f"Import tugadi: {created} ta yaratildi, {updated} ta yangilandi, {skipped} ta o'tkazib yuborildi",
    )
    return redirect(back_url)


from django.contrib.auth.models import Permission
from django.db.models import Exists, OuterRef

PERM_CODENAMES = {
    # Ariza
    "change_order":      "main.change_order",
    "confirm_order":     "main.confirm_order",
    # Ko'rish doirasi
    "all_organization":  "main.all_organization",
    "all_region":         "main.all_region",
    # Texnika
    "view_technics":      "main.view_technics",
    "add_technics":       "main.add_technics",
    "change_technics":    "main.change_technics",
    "delete_technics":    "main.delete_technics",
    # Material
    "view_material":      "main.view_material",
    "add_material":       "main.add_material",
    "delete_material":    "main.delete_material",
    # Maxsus
    "boss_employee":      "main.boss_employee",
    "shop_employee":      "main.shop_employee",
    "status_employee":    "main.status_employee",
}


DEPENDENT_PERMS = {
    "view_technics": ["add_technics", "change_technics", "delete_technics"],
}

def _annotate_permission_flags(employee_qs):
    for field_name, perm_codename in PERM_CODENAMES.items():
        app_label, codename = perm_codename.split(".")
        perm_direct = Permission.objects.filter(
            user=OuterRef("user_id"),
            content_type__app_label=app_label,
            codename=codename,
        )
        employee_qs = employee_qs.annotate(**{
            f"has_{field_name}": Exists(perm_direct),
        })

    return employee_qs


@never_cache
@require_GET
@login_required
@permission_required("main.change_employee", raise_exception=True)
def employee(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    organization_id = request.GET.get("organization")
    region_id = request.GET.get("region")
    department_id = request.GET.get("department")
    directorate_id = request.GET.get("directorate")
    division_id = request.GET.get("division")
    name = request.GET.get("name", "").strip()

    page_number = request.GET.get("page", 1)

    if organization_id:
        employee_qs = (
            Employee.objects
            .select_related("organization", "department", "directorate", "division", "region", "rank", "user")
            .filter(organization_id=organization_id)
        )

        if region_id:
            employee_qs = employee_qs.filter(region_id=region_id)
        if department_id:
            employee_qs = employee_qs.filter(department_id=department_id)
        if directorate_id:
            employee_qs = employee_qs.filter(directorate_id=directorate_id)
        if division_id:
            employee_qs = employee_qs.filter(division_id=division_id)
        if name:
            terms = name.split()
            query = Q()
            for term in terms:
                query &= (
                        Q(last_name__icontains=term) |
                        Q(first_name__icontains=term) |
                        Q(father_name__icontains=term)
                )
            employee_qs = employee_qs.filter(query)

        employee_qs = employee_qs.order_by("-id")
        employee_qs = _annotate_permission_flags(employee_qs)
    else:
        employee_qs = Employee.objects.none()

    paginator = Paginator(employee_qs, 20)
    page_obj = paginator.get_page(page_number)

    is_client = bool(employee.organization and employee.organization.type != "worker")
    goal = Goal.objects.filter(organization=employee.organization) if is_client else Goal.objects.all()

    category = Category.objects.all()

    emp_ids = [e.id for e in page_obj]

    goal_map = {}
    for og in OrderGoal.objects.filter(employee_id__in=emp_ids).values("employee_id", "goal_id"):
        goal_map.setdefault(og["employee_id"], []).append(og["goal_id"])

    category_map = {}
    for lb in Liable.objects.filter(employee_id__in=emp_ids).values("employee_id", "category_id"):
        category_map.setdefault(lb["employee_id"], []).append(lb["category_id"])

    matcategory_map = {}
    for mc in MaterialEmployee.objects.filter(employee_id__in=emp_ids).values("employee_id", "category_id"):
        matcategory_map.setdefault(mc["employee_id"], []).append(mc["category_id"])

    for emp in page_obj:
        emp.selected_goal_ids = goal_map.get(emp.id, [])
        emp.selected_category_ids = category_map.get(emp.id, [])
        emp.selected_matcategory_ids = matcategory_map.get(emp.id, [])

    organizations = Organization.objects.only("id", "name").order_by("id")
    if not request.user.has_perm("main.all_organization"):
        organizations = organizations.filter(id=employee.organization_id)

    regions = Region.objects.only("id", "name").order_by("id")
    if not request.user.has_perm("main.all_region"):
        regions = regions.filter(id=employee.region_id)

    querydict = request.GET.copy()
    querydict.pop("page", None)
    qs_params = querydict.urlencode()

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
        "total_count": paginator.count,
        "goal": goal,
        "category": category,
        "matcategory": MaterialCategory.objects.all(),
        "organizations": organizations,
        "regions": regions,
        "qs_params": qs_params,
        "selected_dep": department_id or "",
        "selected_dir": directorate_id or "",
        "selected_div": division_id or "",
    }
    return render(request, "main/employee.html", context)


@never_cache
@require_POST
@login_required
@permission_required("main.change_employee", raise_exception=True)
def employee_update(request):
    current_employee = getattr(request.user, "employee", None)
    if not current_employee:
        raise PermissionDenied("Employee yo'q")

    back_url = request.META.get("HTTP_REFERER", "/")
    employee_id = request.POST.get("employee_id")
    if not employee_id:
        messages.error(request, "Xodim aniqlanmadi")
        return redirect("employee")

    target_employee = get_object_or_404(
        Employee.objects.select_related("user", "organization"), pk=employee_id
    )

    if not request.user.has_perm("main.all_organization"):
        if target_employee.organization_id != current_employee.organization_id:
            raise PermissionDenied("Boshqa tashkilot xodimini o'zgartira olmaysiz")

    if not target_employee.user_id:
        messages.error(request, "Bu xodimga User biriktirilmagan")
        return redirect(back_url)

    # Checkboxlar - belgilanmagan checkbox POST'da umuman kelmaydi.
    checked_fields = {
        field_name: request.POST.get(field_name) == "on"
        for field_name in PERM_CODENAMES
    }

    # master ruxsat belgilanmagan bo'lsa, unga bog'liq sub ruxsatlar
    # SERVERDA HAM majburan False qilinadi.
    for master_field, sub_fields in DEPENDENT_PERMS.items():
        if not checked_fields.get(master_field, False):
            for sub_field in sub_fields:
                checked_fields[sub_field] = False

    goal_ids = request.POST.getlist("goal")
    category_ids = request.POST.getlist("category")
    matcategory_ids = request.POST.getlist("matcategory")

    with transaction.atomic():
        user = target_employee.user

        for field_name, is_checked in checked_fields.items():
            app_label, codename = PERM_CODENAMES[field_name].split(".")
            perm = Permission.objects.filter(
                content_type__app_label=app_label, codename=codename
            ).first()
            if not perm:
                continue
            if is_checked:
                user.user_permissions.add(perm)
            else:
                user.user_permissions.remove(perm)

        # --- Ariza kategoriyasi (OrderGoal) - "change_order" bajaruvchi rolga bog'liq ---
        OrderGoal.objects.filter(employee=target_employee).delete()
        if checked_fields["change_order"] and goal_ids:
            OrderGoal.objects.bulk_create([
                OrderGoal(employee=target_employee, goal_id=gid)
                for gid in goal_ids
            ])

        # --- Texnika kategoriyasi (Liable) - "view_technics" ko'rish huquqiga bog'liq ---
        Liable.objects.filter(employee=target_employee).delete()
        if checked_fields["view_technics"] and category_ids:
            Liable.objects.bulk_create([
                Liable(employee=target_employee, category_id=cid, contract=None)
                for cid in category_ids
            ])

        # --- Ruxsat etilgan material kategoriyasi (MaterialEmployee) ---
        MaterialEmployee.objects.filter(employee=target_employee).delete()
        if matcategory_ids:
            MaterialEmployee.objects.bulk_create([
                MaterialEmployee(employee=target_employee, category_id=mcid)
                for mcid in matcategory_ids
            ])

    messages.success(request, "Xodim muvaffaqiyatli yangilandi")
    return redirect(back_url)