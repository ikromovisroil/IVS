from collections import defaultdict
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.admin.models import LogEntry
from .ajax_views import *
from django.db.models import Count, Prefetch
from django.contrib.auth.decorators import login_required
from .forms import *
from django.core.paginator import Paginator
from decimal import Decimal, InvalidOperation
from .sso_views import *
from django.db.models import Count, F, FloatField, ExpressionWrapper
from functools import wraps

def global_data(request):
    return {
        "global_organizations": Organization.objects.only("id", "name").order_by("name"),
        "global_categorys": Category.objects.only("id", "name").order_by("name"),
    }


def role_required(permission):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):

            employee = getattr(request.user, "employee", None)
            if not employee:
                return redirect("login")

            role = getattr(employee, "rol", None)
            if not role:
                raise PermissionDenied("Rol biriktirilmagan")

            if not getattr(role, permission, False):
                raise PermissionDenied("Ruxsat yo‘q")

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


@login_required
def home(request):
    return redirect("profil")


@never_cache
@login_required
def profil(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")
    user = request.user

    if request.method == "POST":
        emp_form = EmployeeProfileForm(request.POST, instance=employee)
        email_form = UserEmailForm(request.POST, instance=user)

        if emp_form.is_valid() and email_form.is_valid():
            emp_form.save()
            email_form.save()
            messages.success(request, "Profil muvaffaqiyatli yangilandi")
            return redirect("profil")
        else:
            messages.error(request, "Maydonlarda xatolik bor. Qayta tekshiring")
    else:
        emp_form = EmployeeProfileForm(instance=employee)
        email_form = UserEmailForm(instance=user)

    return render(request, "main/profil.html", {
        "emp_form": emp_form,
        "email_form": email_form,
        "employee":employee,
    })


@never_cache
@login_required
def contact(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    deed_receiver = (
        Deed.objects
        .filter(
            Q(sender=employee, status_sender="viewed") |
            Q(receiver=employee, status_receiver="viewed")
        )
        .select_related("sender", "receiver")
        .order_by("-id")
    )
    return render(request, "main/contact.html", {"deed_receiver": deed_receiver})


@never_cache
@login_required
def contact_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    deed_receiver = (
        Deed.objects
        .filter(
            Q(sender=employee, status_sender__in=["approved", "rejected"]) |
            Q(receiver=employee, status_receiver__in=["approved", "rejected"])
        )
        .select_related("sender", "receiver")
        .order_by("-id")
    )
    context = {
        "deed_receiver": deed_receiver,
    }
    return render(request, "main/contact_arxiv.html", context)


@never_cache
@login_required
def contact_agrement(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    deed_consent = (
        Deed.objects
        .filter(deedconsent__employee=employee,deedconsent__status="viewed")
        .select_related("sender", "receiver")
        .distinct()              # ✅ dublikat bo‘lmasin
        .order_by("-id")
    )

    context = {
        "deed_consent": deed_consent,
    }
    return render(request, "main/contact_agrement.html", context)


@never_cache
@login_required
def contact_agrement_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    deed_consent = (
        Deed.objects
        .filter(deedconsent__employee=employee,deedconsent__status__in=["approved", "rejected"])
        .select_related("sender", "receiver")
        .distinct()              # ✅ dublikat bo‘lmasin
        .order_by("-id")
    )

    context = {
        "deed_consent": deed_consent,
    }
    return render(request, "main/contact_agrement_arxiv.html", context)


@never_cache
@login_required
@role_required("akt")
def contact_user(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    deed_user = (
        Deed.objects
        .filter(
            user=employee,
            status_sender="viewed",
            status_receiver="viewed",
        )
        .select_related("sender", "receiver", "user")
        .order_by("-id")
    )

    return render(request, "main/contact_user.html", {"deed_user": deed_user})


@never_cache
@login_required
@role_required("akt")
def contact_user_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    done_statuses = ["approved", "rejected"]
    deed_user = (
        Deed.objects
        .filter(user=employee)
        .filter(
            Q(status_sender__in=done_statuses) |
            Q(status_receiver__in=done_statuses)
        )
        .select_related("sender", "receiver", "user")
        .order_by("-id")
    )

    return render(request, "main/contact_user_arxiv.html", {"deed_user": deed_user})


def deed_status(request, pk):
    deed = get_object_or_404(Deed, pk=pk)
    context = {"d": deed}
    return render(request, "main/deed_status.html", context)


@never_cache
@login_required
def deed_action(request, pk):
    emp = getattr(request.user, "employee", None)
    if not emp:
        raise PermissionDenied("Employee yo‘q")

    if request.method != "POST":
        return redirect(request.META.get("HTTP_REFERER", "/"))


    back_url = request.META.get("HTTP_REFERER", "/")
    action = (request.POST.get("action") or "").strip()

    deed = get_object_or_404(
        Deed.objects.select_related("sender", "receiver"),
        pk=pk
    )

    # kim bosdi?
    if deed.receiver_id == emp.id:
        role = "receiver"
        message = (request.POST.get("message") or "").strip()
    elif deed.sender_id == emp.id:
        role = "sender"
        message = (request.POST.get("message") or "").strip()
    else:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    # ❌ Reject
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

        messages.info(request, "Dalolatnoma rad etildi")
        return redirect(back_url)

    # ✅ Approve → SSO → Viewer
    if action == "approve":
        if not deed.file:
            messages.info(request, "PDF yo‘q")
            return redirect(back_url)

        file_path = deed.file.path

        if not (file_path and os.path.exists(file_path)):
            messages.info(request, "PDF topilmadi")
            return redirect(back_url)

        if not file_path.lower().endswith(".pdf"):
            messages.info(request, "PDF noto‘g‘ri")
            return redirect(back_url)

        if os.path.getsize(file_path) < 1024:
            messages.info(request, "PDF buzilgan")
            return redirect(back_url)

        try:
            PdfReader(file_path)
        except Exception:
            messages.info(request, "PDF o‘qilmadi")
            return redirect(back_url)


        request.session["PENDING_APPROVE"] = {
            "deed_id": deed.id,
            "role": role,          # sender/receiver
            "message": message,
            "redirect_url": back_url,
        }
        request.session.modified = True
        return redirect("sso_start_approve")

    messages.error(request, "Noto‘g‘ri amal")
    return redirect(back_url)


@never_cache
@login_required
@role_required("akt")
def deed_edit(request, pk):
    emp_me = getattr(request.user, "employee", None)
    if not emp_me:
        raise PermissionDenied("Employee yo‘q")


    deed = get_object_or_404(
        Deed.objects.select_related("sender", "receiver"),
        pk=pk
    )

    if deed.user != emp_me:
        raise PermissionDenied

    # ✅ None bo‘lishi mumkin — shuning uchun organization_id orqali olamiz
    sender_org_id = deed.sender.organization_id if deed.sender_id else None
    receiver_org_id = deed.receiver.organization_id if deed.receiver_id else None
    my_org_id = emp_me.organization_id if emp_me.organization_id else None

    # ✅ selectlarda chiqadigan ro‘yxatlar
    sender_qs = (
        Employee.objects.filter(organization_id=sender_org_id)
        .order_by("last_name", "first_name", "father_name")
        if sender_org_id else Employee.objects.none()
    )

    receiver_qs = (
        Employee.objects.filter(organization_id=receiver_org_id)
        .order_by("last_name", "first_name", "father_name")
        if receiver_org_id else Employee.objects.none()
    )

    org_ids = [x for x in [sender_org_id, receiver_org_id, my_org_id] if x]
    employee_qs = (
        Employee.objects.filter(organization_id__in=org_ids)
        .distinct()
        .order_by("last_name", "first_name", "father_name")
        if org_ids else Employee.objects.none()
    )

    # ✅ agreements tanlangan idlar (related_name kerak emas!)
    selected_agreement_ids = set(
        DeedConsent.objects.filter(deed=deed).values_list("employee_id", flat=True)
    )

    if request.method == "POST":
        sender_id = (request.POST.get("sender") or "").strip()
        receiver_id = (request.POST.get("receiver") or "").strip()
        body = request.POST.get("body") or ""
        agreements_ids = request.POST.getlist("agreements[]")  # ["12","15",...]

        if not body.strip():
            messages.error(request, "Hujjat matni bo‘sh bo‘lmasin")
            return redirect("deed_edit", pk=deed.pk)

        # ✅ Sender majburiy (xohlasangiz shartni yumshatishingiz mumkin)
        if not sender_id.isdigit():
            messages.error(request, "Imzolovchi xodim tanlanmadi")
            return redirect("deed_edit", pk=deed.pk)

        new_sender = Employee.objects.filter(id=int(sender_id)).first()
        if not new_sender:
            messages.error(request, "Imzolovchi topilmadi")
            return redirect("deed_edit", pk=deed.pk)

        # ✅ Receiver faqat deed.receiver mavjud bo‘lsa tekshiriladi
        new_receiver = None
        if deed.receiver_id:
            if not receiver_id.isdigit():
                messages.error(request, "Qabul qiluvchi tanlanmadi")
                return redirect("deed_edit", pk=deed.pk)

            new_receiver = Employee.objects.filter(id=int(receiver_id)).first()
            if not new_receiver:
                messages.error(request, "Qabul qiluvchi topilmadi")
                return redirect("deed_edit", pk=deed.pk)

        # ✅ agreements tozalash
        clean_agreement_ids = []
        for x in agreements_ids:
            if str(x).isdigit():
                clean_agreement_ids.append(int(x))

        try:
            with transaction.atomic():
                # 1) Deed yangilash
                deed.sender = new_sender
                if deed.receiver_id:
                    deed.receiver = new_receiver
                deed.body = body
                deed.save()

                # 2) Agreements (DeedConsent) ni qayta yozish
                DeedConsent.objects.filter(deed=deed).delete()

                # sender/receiver kelishuvchi bo‘lib qolmasin desangiz:
                exclude_ids = {deed.sender_id}
                if deed.receiver_id:
                    exclude_ids.add(deed.receiver_id)

                for e_id in clean_agreement_ids:
                    if e_id in exclude_ids:
                        continue
                    DeedConsent.objects.create(deed=deed, employee_id=e_id)

                # 3) Eski PDFni o‘chiramiz
                if getattr(deed, "file", None):
                    if deed.file:
                        deed.file.delete(save=False)

                # 4) Yangi PDF generatsiya
                pdf_bytes = deed_to_pdf_bytes(deed)

                wm_text = "TASDIQLANMAGAN"
                pdf_bytes = add_text_watermark_pdf_bytes(pdf_bytes, wm_text)

                today_str = timezone.now().strftime("%Y%m%d")
                alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
                random_part = ''.join(secrets.choice(alphabet) for _ in range(6))
                pdf_name = f"deed/akt_{today_str}_{random_part}.pdf"

                deed.file.save(pdf_name, ContentFile(pdf_bytes), save=True)

            messages.success(request, "Hujjat muvaffaqiyatli tahrirlandi")
            return redirect("contact_user")

        except HtmlPdfError as e:
            messages.warning(request, f"Hujjat yangilanmadi: {e}")
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
    back_url = request.META.get("HTTP_REFERER", "/")

    consent = get_object_or_404(
        DeedConsent.objects.select_related("employee__user", "deed"),
        pk=pk
    )

    # faqat o‘sha employee egasi bosishi mumkin
    if consent.employee.user_id != request.user.id:
        messages.info(request, "Sizga ruxsat yo‘q")
        return redirect(back_url)

    # qayta bosib yubormasin
    if consent.status != "viewed":
        messages.info(request, "Bu kelishuv allaqachon ko‘rib chiqilgan")
        return redirect(back_url)

    action = (request.POST.get("action") or "").strip()
    message = (request.POST.get("message") or "").strip()

    if action == "reject":
        consent.status = "rejected"
        consent.message = message
        consent.date_edit = timezone.now()
        consent.save(update_fields=["status", "message", "date_edit"])
        messages.warning(request, "Rad etildi!")
        return redirect(back_url)

    if action == "approve":
        consent.status = "approved"
        consent.message = message
        consent.date_edit = timezone.now()
        consent.save(update_fields=["status", "message", "date_edit"])
        messages.warning(request, "Hujjat muvaffaqiyatli kelishildi")
        return redirect(back_url)

    messages.error(request, "Noto‘g‘ri amal")
    return redirect(back_url)


from itertools import groupby
@never_cache
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
    status          = (request.GET.get("status") or "").strip() or None
    name            = (request.GET.get("name") or "").strip() or None
    page_number     = request.GET.get("page", 1)

    # inputni haddan oshirmaslik (perf + xavfsizlik)
    if name:
        name = name[:120]

    has_filter = bool(
        organization_id or department_id or directorate_id or division_id or
        status or category_id or name
    )

    # Common data
    organizations = Organization.objects.only("id", "name")
    categories    = Category.objects.only("id", "name")
    technics_form = TechnicsForm()

    # Cascading (agar siz buni AJAX bilan tortsangiz — xohlasangiz remove qiling)
    departments = Department.objects.none()
    if organization_id:
        departments = Department.objects.filter(organization_id=organization_id).only("id", "name")

    directorates = Directorate.objects.none()
    if department_id:
        directorates = Directorate.objects.filter(department_id=department_id).only("id", "name")

    divisions = Division.objects.none()
    if directorate_id:
        divisions = Division.objects.filter(directorate_id=directorate_id).only("id", "name")

    params = request.GET.copy()
    params.pop("page", None)
    qs_params = params.urlencode()

    if not has_filter:
        empty_page = Paginator([], 50).get_page(page_number)
        return render(request, "main/barn_tex.html", {
            "organizations": organizations,
            "categories": categories,
            "technics_form": technics_form,
            "departments": departments,
            "directorates": directorates,
            "divisions": divisions,
            "selected_org": organization_id,
            "selected_dep": department_id,
            "selected_dir": directorate_id,
            "selected_div": division_id,
            "page_obj": empty_page,
            "grouped_technics": [],
            "qs_params": qs_params,
            "extratex": ExtraTechnics.objects.none(),
            "total_count": 0,
        })

    # ---------- base filtered queryset (HECH QACHON full loop qilmaymiz) ----------
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

    # Umumiy texnika soni (kerak bo‘lsa)
    total_count = base_qs.count()

    # ---------- 1) faqat employee_id larni topamiz (GROUP PAGINATION) ----------
    emp_ids_qs = (
        base_qs.order_by("employee_id")
        .values_list("employee_id", flat=True)
        .distinct()
    )

    paginator = Paginator(emp_ids_qs, 50)  # 1 sahifada 50 ta xodim (group)
    page_obj = paginator.get_page(page_number)

    page_emp_ids = list(page_obj.object_list)  # [1,2,3,None,...] bo‘lishi mumkin
    include_null = any(e is None for e in page_emp_ids)
    page_emp_ids_no_null = [e for e in page_emp_ids if e is not None]

    # ---------- 2) faqat shu sahifadagi xodim texnikalari ----------
    extratech_prefetch = Prefetch(
        "extratechnics_set",
        queryset=ExtraTechnics.objects.only("id", "name", "inventory", "serial").order_by("id")
    )

    page_tech_qs = (
        base_qs
        .filter(
            Q(employee_id__in=page_emp_ids_no_null) |
            (Q(employee__isnull=True) if include_null else Q(pk__in=[]))
        )
        .select_related("organization", "category", "employee")
        .prefetch_related(extratech_prefetch)
        .only(
            "id", "name", "inventory", "serial", "ip", "mac", "status",
            "organization__id", "organization__name",
            "category__id", "category__name",
            "employee__id", "employee__first_name", "employee__last_name", "employee__father_name",
        )
        .order_by("employee")
    )

    # ---------- 3) grouping (itertools.groupby) ----------
    grouped_technics = []
    for emp_id, items in groupby(page_tech_qs, key=lambda t: t.employee_id):
        items_list = list(items)
        emp_obj = items_list[0].employee  # None bo‘lishi mumkin
        grouped_technics.append((emp_obj, items_list))

    # Extratex (organization bo‘yicha)
    extratex = ExtraTechnics.objects.none()
    if organization_id:
        extratex = (
            ExtraTechnics.objects
            .filter(organization_id=organization_id, status="free", is_active=True)
            .only("id", "name", "inventory", "serial")
            .order_by("-id")
        )

    return render(request, "main/barn_tex.html", {
        "organizations": organizations,
        "categories": categories,
        "technics_form": technics_form,
        "departments": departments,
        "directorates": directorates,
        "divisions": divisions,
        "selected_org": organization_id,
        "selected_dep": department_id,
        "selected_dir": directorate_id,
        "selected_div": division_id,

        "page_obj": page_obj,
        "grouped_technics": grouped_technics,  # [(emp, [tex...]), ...]
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

    back_url = request.META.get("HTTP_REFERER", "/")
    form = TechnicsForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Texnika qo‘shildi")
    else:
        messages.error(request, "Maʼlumotlarda xatolik bor")

    return redirect(back_url)


@never_cache
@require_POST
@transaction.atomic
@login_required
@role_required("technics_edit")
def technics_delete(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")
    tex_id = request.POST.get("texnika_id")

    try:
        tex = Technics.objects.select_for_update().get(pk=int(tex_id))
    except (Technics.DoesNotExist, TypeError, ValueError):
        messages.info(request, "Texnika topilmadi")
        return redirect(back_url)

    if not tex.is_active:
        messages.info(request, "Texnika allaqachon o‘chirilgan")
        return redirect(back_url)

    tex.is_active = False
    tex.save(update_fields=["is_active"])

    messages.success(request, "Texnika muvaffaqiyatli o‘chirildi")
    return redirect(back_url)


@require_POST
@transaction.atomic
@login_required
@role_required("technics_edit")
def technics_attach(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")

    tex_id = (request.POST.get("texnika_id") or "").strip()
    emp_id = (request.POST.get("employee_id") or "").strip()

    if not tex_id.isdigit():
        messages.error(request, "Texnika topilmadi")
        return redirect(back_url)

    # ✅ lock: parallel bosishlar muammo qilmasin
    tex = get_object_or_404(Technics.objects.select_for_update(), id=int(tex_id))

    if emp_id:
        if not emp_id.isdigit():
            messages.error(request, "Xodim noto‘g‘ri tanlandi")
            return redirect(back_url)

        emp = get_object_or_404(Employee.objects.select_related("organization", "region"), id=int(emp_id))
        tex.employee_id = emp.id
        tex.status = "active"
        tex.save(update_fields=["employee", "status", "date_edit"] if hasattr(tex, "date_edit") else ["employee", "status"])
        messages.success(request, "Texnika xodimga biriktirildi")
    else:
        tex.employee = None
        tex.status = "free"
        tex.save(update_fields=["employee", "status", "date_edit"] if hasattr(tex, "date_edit") else ["employee", "status"])
        messages.success(request, "Texnika bo‘shatildi")

    return redirect(back_url)


@require_POST
@transaction.atomic
@login_required
@role_required("technics_edit")
def technics_update(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")
    tex = get_object_or_404(Technics.objects.select_for_update(), pk=pk)

    category_id = (request.POST.get("category") or "").strip()
    organization_id = (request.POST.get("organization") or "").strip()

    # FK lar
    if category_id:
        if not category_id.isdigit():
            messages.error(request, "Kategoriya noto‘g‘ri")
            return redirect(back_url)
        tex.category = get_object_or_404(Category, pk=int(category_id))
    else:
        tex.category = None

    if organization_id:
        if not organization_id.isdigit():
            messages.error(request, "Tashkilot noto‘g‘ri")
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
        messages.error(request, "Narx noto‘g‘ri kiritildi (misol: 14.45 yoki 14,45)")
        return redirect(back_url)

    # 💾 Minimal saqlash
    tex.save(update_fields=[
        "category", "organization",
        "name", "parametr", "inventory", "serial", "mac", "ip", "year", "price"
    ])

    messages.success(request, "Texnika tahrirlandi!")
    return redirect(back_url)


@never_cache
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

    has_filter = bool(category_id or status or organization_id or name)

    if not has_filter:
        qs = ExtraTechnics.objects.none()
        page_obj = Paginator(qs, 50).get_page(page_number)

        params = request.GET.copy()
        params.pop("page", None)

        return render(request, "main/extra_tex.html", {
            "organizations": Organization.objects.only("id", "name"),
            "categories": ExtraCategory.objects.only("id", "name"),
            "technics_form": ExtraTechnicsForm(),

            "page_obj": page_obj,
            "technics": page_obj.object_list,
            "qs_params": params.urlencode(),
            "row_start": 0,

            "total_count": 0,
        })

    # ✅ Filter bor bo‘lsa — query ishlaydi
    qs = (
        ExtraTechnics.objects.filter(is_active=True)
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
        "organizations": Organization.objects.only("id", "name"),
        "categories": ExtraCategory.objects.only("id", "name"),
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
@transaction.atomic
@login_required
@role_required("technics_edit")
def extra_tex_delete(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")
    tex_id = request.POST.get("texnika_id")

    try:
        tex = ExtraTechnics.objects.select_for_update().get(pk=int(tex_id))
    except (ExtraTechnics.DoesNotExist, TypeError, ValueError):
        messages.info(request, "Texnika topilmadi")
        return redirect(back_url)

    if not tex.is_active:
        messages.info(request, "Texnika allaqachon o‘chirilgan")
        return redirect(back_url)

    tex.is_active = False
    tex.save(update_fields=["is_active"])

    messages.success(request, "Texnika muvaffaqiyatli o‘chirildi")
    return redirect(back_url)


@require_POST
@transaction.atomic
@login_required
@role_required("technics_edit")
def extra_tex_update(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER") or "extra_tex"

    tex = get_object_or_404(
        ExtraTechnics.objects.select_for_update(),
        pk=pk,
        is_active=True,
    )

    organization_id = (request.POST.get("organization") or "").strip()
    category_id = (request.POST.get("category") or "").strip()

    # organization
    if organization_id:
        if not organization_id.isdigit():
            messages.error(request, "Tashkilot noto‘g‘ri")
            return redirect(back_url)
        tex.organization = get_object_or_404(Organization, pk=int(organization_id))
    else:
        tex.organization = None

    # category
    if category_id:
        if not category_id.isdigit():
            messages.error(request, "Kategoriya noto‘g‘ri")
            return redirect(back_url)
        tex.category = get_object_or_404(ExtraCategory, pk=int(category_id))
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


@require_POST
@login_required
@role_required("technics_edit")
def extra_tex_attach(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    texnika_id = (request.POST.get("texnika_id") or "").strip()
    extra_tex_id = (request.POST.get("extra_tex_id") or "").strip()

    if not texnika_id or not extra_tex_id:
        messages.error(request, "Tanlash majburiy (texnika va qo‘shimcha texnika).")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    # obyektlarni olish
    tex = get_object_or_404(Technics, id=texnika_id, is_active=True)
    extra = get_object_or_404(ExtraTechnics, id=extra_tex_id)

    # biriktirish
    extra.technics = tex
    extra.status = "active"
    extra.save(update_fields=["technics", "status"])  # <-- MUHIM

    messages.success(request, "Qo‘shimcha texnika muvaffaqiyatli biriktirildi.")
    return redirect(request.META.get("HTTP_REFERER", "/"))


@require_POST
@login_required
@role_required("technics_edit")
def extra_tex_detach(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    texnika_id = (request.POST.get("texnika_id") or "").strip()
    extra_tex_id = (request.POST.get("extra_tex_id") or "").strip()

    if not texnika_id or not extra_tex_id:
        messages.error(request, "Tanlash majburiy (texnika va qo‘shimcha texnika).")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    # Asosiy texnika mavjudligini tekshiramiz
    tex = get_object_or_404(Technics, id=texnika_id, is_active=True)

    # Faqat shu texnikaga biriktirilgan extra texnikani ajratamiz
    extra = get_object_or_404(ExtraTechnics, id=extra_tex_id, technics=tex)

    extra.technics = None
    extra.status = "free"
    extra.save(update_fields=["technics", "status"])

    messages.success(request, "Qo‘shimcha texnika bekor qilindi.")
    return redirect(request.META.get("HTTP_REFERER", "/"))


@never_cache
@login_required
@role_required("material")
def barn_mat(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")


    emp_id = (request.GET.get("employee") or "").strip()
    status = (request.GET.get("status") or "").strip()
    name = (request.GET.get("name") or "").strip()
    page_number = request.GET.get("page", 1)

    has_filter = bool(emp_id or status or name)

    # ✅ filter bo‘lmasa bo‘sh ko‘rsatamiz (tez)
    if not has_filter:
        qs = Material.objects.none()
        page_obj = Paginator(qs, 50).get_page(page_number)

        params = request.GET.copy()
        params.pop("page", None)

        return render(request, "main/barn_mat.html", {
            "employees_boss": Employee.objects.filter(rol__client=False, rol__boss=True),
            "page_obj": page_obj,
            "material": page_obj.object_list,
            "material_form": MaterialForm(),
            "qs_params": params.urlencode(),
            "row_start": 0,
            "total_count": 0,
            "total_suma": 0,
        })

    qs = (
        Material.objects.filter(is_active=True)
        .select_related("employee", "employee__user")
        .annotate(
            total_sum=ExpressionWrapper(
                F("number") * F("price"),
                output_field=DecimalField(max_digits=18, decimal_places=2)
            )
        )
        .order_by("-id")
    )

    if status:
        qs = qs.filter(status=status)

    if emp_id:
        # id bo‘lmasa ignore (xohlasangiz error ham qilamiz)
        if emp_id.isdigit():
            qs = qs.filter(employee_id=int(emp_id))
        else:
            qs = Material.objects.none()

    if name:
        qs = qs.filter(Q(name__icontains=name) | Q(code__icontains=name))

    total_count = qs.count()
    total_suma = qs.aggregate(s=Sum("total_sum"))["s"] or 0

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)
    qs_params = params.urlencode()

    context = {
        "employees_boss": Employee.objects.filter(rol__client=False, rol__boss=True),
        "page_obj": page_obj,
        "material": page_obj.object_list,
        "material_form": MaterialForm(),
        "qs_params": qs_params,
        "row_start": page_obj.start_index() if total_count else 0,
        "total_count": total_count,
        "total_suma": total_suma,
        "unit": Unit.objects.all()
    }
    return render(request, "main/barn_mat.html", context)


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
        form.save()
        messages.success(request, "Material qo‘shildi!")
    else:
        messages.error(request, "Maʼlumotlarda xatolik bor")

    return redirect(back_url)


@require_POST
@login_required
@role_required("material_edit")
def material_update(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")

    mat = get_object_or_404(Material, pk=pk)
    unit_id = (request.POST.get("unit") or "").strip()

    # FK lar
    if unit_id:
        if not unit_id.isdigit():
            messages.info(request, "Birligi noto‘g‘ri")
            return redirect(back_url)
        mat.unit = get_object_or_404(Unit, pk=int(unit_id))
    else:
        mat.unit = None

    mat.name = (request.POST.get("name") or "").strip()
    mat.code = (request.POST.get("code") or "").strip()

    # number validatsiya (butun son)
    raw_number = (request.POST.get("number") or "").strip()
    try:
        mat.number = int(raw_number) if raw_number else 0
        if mat.number < 0:
            raise ValueError
    except ValueError:
        messages.error(request, "Soni noto‘g‘ri kiritildi")
        return redirect(back_url)

    # price validatsiya (14.45 yoki 14,45)
    raw_price = (request.POST.get("price") or "").strip().replace(" ", "")
    raw_price = raw_price.replace(",", ".")
    try:
        mat.price = Decimal(raw_price) if raw_price else Decimal("0")
        if mat.price < 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        messages.error(request, "Narx noto‘g‘ri (misol: 14.45 yoki 14,45)")
        return redirect(back_url)

    mat.save(update_fields=["name", "number", "price", "code", "unit"])
    messages.success(request, "Material tahrirlandi!")
    return redirect(back_url)


@require_POST
@transaction.atomic
@login_required
@role_required("material_edit")
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
@transaction.atomic
@login_required
@role_required("material_edit")
def material_delete(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER") or "/"
    material_id = request.POST.get("material_id")

    try:
        mat = Material.objects.select_for_update().get(pk=int(material_id))
    except (Material.DoesNotExist, TypeError, ValueError):
        messages.error(request, "Material topilmadi")
        return redirect(back_url)

    if not mat.is_active:
        messages.info(request, "Material allaqachon o‘chirilgan")
        return redirect(back_url)

    mat.is_active = False
    mat.save(update_fields=["is_active"])

    messages.success(request, "Material muvaffaqiyatli o‘chirildi")
    return redirect(back_url)


@never_cache
@login_required
@role_required("akt")
def document_get(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    liable = Liable.objects.filter(employee=employee).select_related("contract").distinct("contract")

    context = {
        "liable": liable,
        "organizations": Organization.objects.only("id", "name", "slug"),
        "emp_bos_sender": Employee.objects.filter(id__in=[3470,3469,3468]),
    }
    return render(request, "main/document.html", context)


@never_cache
@require_POST
@login_required
@role_required("akt")
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
        messages.error(request, "Imzolovchi xodim tanlanmadi")
        return redirect("akt_get")

    if not body.strip():
        messages.error(request, "Hujjat matni (body) bo‘sh bo‘lmasin")
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
        pdf_name = f"deed/akt_{today_str}_{random_part}.pdf"
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
    exclude_ids = {receiver.id, sender.id}
    ids = [i for i in ids if i not in exclude_ids]

    # ✅ DeedConsent bulk_create
    if ids:
        emps = Employee.objects.filter(id__in=ids).only("id")
        objs = [DeedConsent(deed=deed, employee=e, status="viewed") for e in emps]
        DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

    messages.success(request, "Imzolashga yuborildi")
    return redirect("contact_user")


# yangi arizalar
@never_cache
@login_required
def order_sender(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orders_qs = (
        Order.objects
        .filter(sender=employee,status__in=["viewed", "accepted", "finished"],)
        .select_related("goal", "technics", "receiver", "sender")
        .order_by("-id")
    )

    goals_qs = (
        Goal.objects
        .only("id", "name",)
        .order_by("id")
    )

    # ✅ PAGINATION
    page_number = request.GET.get("page", 1)
    paginator = Paginator(orders_qs, 50)   # har sahifada 4 ta
    page_obj = paginator.get_page(page_number)

    context = {
        "order": page_obj,          # ✅ for loop shu orqali yuradi
        "page_obj": page_obj,       # ✅ pagination uchun
        "paginator": paginator,     # ✅ pagination uchun

        "goal": goals_qs,
    }
    return render(request, "main/order_sender.html", context)


# arizani tasdiqlash yoki bekor qilish
@never_cache
@require_POST
@login_required
def order_decide(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    order = get_object_or_404(Order, id=pk)
    action = request.POST.get("action")  # approve | reject

    if action == "rejected":
        order.status = "rejected"
        order.save()

        messages.success(request, "Ariza bekor qilindi!")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    if action == "approved":
        rating = request.POST.get("rating")

        if not rating:
            messages.error(request, "Iltimos, baho (yulduz) tanlang!")
            return redirect(request.META.get("HTTP_REFERER", "/"))

        try:
            rating = int(rating)
        except ValueError:
            messages.error(request, "Baho noto‘g‘ri!")
            return redirect(request.META.get("HTTP_REFERER", "/"))

        if rating < 1 or rating > 5:
            messages.error(request, "Baho 1 dan 5 gacha bo‘lishi kerak!")
            return redirect(request.META.get("HTTP_REFERER", "/"))

        order.rating = rating
        order.status = "approved"
        order.save()
        messages.success(request, "Ariza tasdiqlandi va baholandi!")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    messages.error(request, "Noma’lum amal!")
    return redirect(request.META.get("HTTP_REFERER", "/"))


# arizalar arxivi
@never_cache
@login_required
def order_sender_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orders_qs = (
        Order.objects
        .filter(sender=employee,status__in=["approved", "rejected",],)
        .select_related("goal", "technics", "receiver", "sender")
        .order_by("-id")
    )

    goals_qs = (
        Goal.objects
        .only("id", "name",)
        .order_by("-id")
    )

    # ✅ PAGINATION
    page_number = request.GET.get("page", 1)
    paginator = Paginator(orders_qs, 50)   # har sahifada 4 ta
    page_obj = paginator.get_page(page_number)

    context = {
        "order": page_obj,          # ✅ for loop shu orqali yuradi
        "page_obj": page_obj,       # ✅ pagination uchun
        "paginator": paginator,     # ✅ pagination uchun

        "goal": goals_qs,
    }
    return render(request, "main/order_sender_arxiv.html", context)


@never_cache
@require_POST
@login_required
def order_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")

    goal_id = (request.POST.get("goal") or "").strip()
    body = (request.POST.get("body") or "").strip()

    if not goal_id.isdigit():
        messages.info(request, "Ariza turi tanlanmadi yoki noto‘g‘ri.")
        return redirect("order_sender")

    goal = get_object_or_404(Goal, id=int(goal_id))

    Order.objects.create(
        sender=employee,
        goal=goal,
        body=body,
    )
    messages.success(request, "Ariza yuborildi")
    return redirect(back_url)


@never_cache
@login_required
@role_required("order")
def order_receiver(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orders_qs = (
        Order.objects
        .filter(sender__region=employee.region,status="viewed",)
        .select_related("goal", "technics", "receiver", "sender")
        .order_by("-id")
    )

    # ✅ PAGINATION
    page_number = request.GET.get("page", 1)
    paginator = Paginator(orders_qs, 50)   # har sahifada 4 ta
    page_obj = paginator.get_page(page_number)

    context = {
        "order": page_obj,          # ✅ for loop shu orqali yuradi
        "page_obj": page_obj,       # ✅ pagination uchun
        "paginator": paginator,     # ✅ pagination uchun
    }
    return render(request, "main/order_receiver.html", context)


@never_cache
@require_POST
@login_required
@role_required("order")
def order_accepted(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    order = get_object_or_404(Order, pk=pk)

    if order.status == "accepted":
        messages.warning(request, "Bu ariza allaqachon qabul qilingan")
        return redirect('order_receiver_activ')

    order.status = "accepted"
    order.receiver = employee
    order.save()

    messages.success(request, "Ariza qabul qilindi!")
    return redirect('order_receiver_activ')


@never_cache
@login_required
@role_required("order")
def order_receiver_deed(request,pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    order = get_object_or_404(Order, pk=pk)

    if order.receiver != employee:
        raise PermissionDenied

    my_dep_id = request.user.employee.department_id

    context = {
        'order':order,
        'emp_bos':Employee.objects.filter(department=order.sender.department),
        'employee': Employee.objects.filter(Q(department=order.sender.department) | Q(department_id=my_dep_id)),
    }
    return render(request, "main/order_receiver_deed.html", context)


@never_cache
@require_POST
@login_required
@role_required("order")
def order_receiver_deed_post(request):
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
        messages.error(request, "Imzolovchi xodim tanlanmadi")
        return redirect("akt_get")

    if not body.strip():
        messages.error(request, "Hujjat matni (body) bo‘sh bo‘lmasin")
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
        pdf_name = f"deed/akt_{today_str}_{random_part}.pdf"
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
@login_required
@role_required("order")
def order_receiver_activ(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orders_qs = (
        Order.objects
        .filter(receiver=employee,status__in=["accepted", "finished"],)
        .select_related("goal", "technics", "receiver", "sender")
        .order_by("-id")
    )
    my_materials = Material.objects.filter(employee=employee)
    if my_materials.exists():
        materials = my_materials
    else:
        materials = Material.objects.filter(
            employee__rol__shop=True,
            employee__region=employee.region,
            employee__organization=employee.organization,
            employee__department=employee.department,
        )

    # ✅ PAGINATION
    page_number = request.GET.get("page", 1)
    paginator = Paginator(orders_qs, 50)   # har sahifada 4 ta
    page_obj = paginator.get_page(page_number)

    context = {
        "order": page_obj,          # ✅ for loop shu orqali yuradi
        "page_obj": page_obj,       # ✅ pagination uchun
        "paginator": paginator,     # ✅ pagination uchun
        'materials': materials,
    }
    return render(request, "main/order_receiver_activ.html", context)


@never_cache
@login_required
@role_required("order")
def order_receiver_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orders_qs = (
        Order.objects
        .filter(receiver=employee,status__in=["approved", "rejected",],)
        .select_related("goal", "technics", "receiver", "sender")
        .order_by("-id")
    )

    # ✅ PAGINATION
    page_number = request.GET.get("page", 1)
    paginator = Paginator(orders_qs, 50)   # har sahifada 4 ta
    page_obj = paginator.get_page(page_number)

    context = {
        "order": page_obj,          # ✅ for loop shu orqali yuradi
        "page_obj": page_obj,       # ✅ pagination uchun
        "paginator": paginator,     # ✅ pagination uchun
    }
    return render(request, "main/order_receiver_arxiv.html", context)


@never_cache
@login_required
def order_approved(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    if request.method != "POST":
        return redirect("/")

    order_id = request.POST.get("order_id")
    rating = request.POST.get("rating")

    order = get_object_or_404(Order, id=order_id)
    order.rating = int(rating)
    order.status = "approved"
    order.receiver_seen = False
    order.save()

    messages.success(request, "Zayafka tasdiqlandi!")
    return redirect(request.META.get("HTTP_REFERER", "/"))


from django.db.models import F
@never_cache
@require_POST
@transaction.atomic
@login_required
@role_required("order")
def ordermaterial_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    order_id = request.POST.get("order_id")
    technics_id = request.POST.get("technics_id")
    material_ids = request.POST.getlist("material_id[]")
    numbers = request.POST.getlist("number[]")

    # 🔒 Order ni lock qilib olamiz (parallel submit bo‘lsa ham)
    order = get_object_or_404(Order.objects.select_for_update(), id=order_id)

    # ✅ Texnika majburiy bo‘lsa: tekshirish
    if not technics_id:
        messages.info(request, "Iltimos, texnikani tanlang!")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    order.technics_id = technics_id

    # ✅ Materiallar bo‘sh bo‘lishi mumkin (xohlasangiz majburiy qiling)
    pairs = []
    for m_id, num in zip(material_ids, numbers):
        if not m_id:
            continue
        try:
            n = int(num or 1)
        except ValueError:
            messages.info(request, "Material soni noto‘g‘ri kiritilgan!")
            return redirect(request.META.get("HTTP_REFERER", "/"))
        if n <= 0:
            messages.info(request, "Material soni 0 yoki manfiy bo‘lishi mumkin emas!")
            return redirect(request.META.get("HTTP_REFERER", "/"))
        pairs.append((m_id, n))

    # 🔁 Har bir materialni tekshirib, ombordagi sonni xavfsiz kamaytiramiz
    for m_id, n in pairs:
        material = Material.objects.select_for_update().filter(id=m_id).first()
        if not material:
            messages.info(request, "Material topilmadi!")
            return redirect(request.META.get("HTTP_REFERER", "/"))

        # ✅ Yetarlilik tekshiruvi
        if material.number < n:
            messages.info(request, f"{material.name} yetarli emas! Omborda {material.number} dona bor.")
            return redirect(request.META.get("HTTP_REFERER", "/"))

        # ✅ OrderMaterial yaratish
        OrderMaterial.objects.create(order=order, material=material, number=n)

        # ✅ Ombordan ayrish (atomic)
        material.number = F("number") - n
        material.save(update_fields=["number"])

    # ✅ Status yakunlandi qilish
    order.status = "finished"
    order.save(update_fields=["technics", "status", "date_edit", "date_finished"])

    messages.success(request, "Ariza yakunlandi!")
    return redirect(request.META.get("HTTP_REFERER", "/"))


@never_cache
@login_required
@role_required("akt")
def akt_get(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    context = {
        "organizations": Organization.objects.all(),
    }
    return render(request, "main/akt.html", context)



@never_cache
@require_POST
@login_required
@role_required("akt")
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
        messages.error(request, "Imzolovchi xodim tanlanmadi")
        return redirect("akt_get")

    if not body.strip():
        messages.error(request, "Hujjat matni (body) bo‘sh bo‘lmasin")
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
        pdf_name = f"deed/akt_{today_str}_{random_part}.pdf"
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
@login_required
@role_required("akt")
def svod_get(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    context = {
        "organizations": Organization.objects.all(),
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
        messages.error(request, "Imzolovchi xodim tanlanmadi")
        return redirect("akt_get")

    if not body.strip():
        messages.error(request, "Hujjat matni (body) bo‘sh bo‘lmasin")
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
        pdf_name = f"deed/akt_{today_str}_{random_part}.pdf"
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
@login_required
@role_required("akt")
def reestr_get(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    context = {
        "organizations": Organization.objects.all(),
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
        messages.error(request, "Imzolovchi xodim tanlanmadi")
        return redirect("akt_get")

    if not body.strip():
        messages.error(request, "Hujjat matni (body) bo‘sh bo‘lmasin")
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
        pdf_name = f"deed/akt_{today_str}_{random_part}.pdf"
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


from django.utils.dateparse import parse_date
@never_cache
@login_required
@role_required("status")
def emp_status(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    # ---- FILTER PARAMS ----
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
@login_required
@role_required("status")
def tex_status(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orgs = list(
        Organization.objects
        .all()
        .order_by("id")
        .annotate(technics_count=Count("technics", distinct=True))  # agar ishlamasa -> technics_set
        .values("id", "name", "technics_count")
    )

    total_technics = sum(o["technics_count"] for o in orgs) or 1
    for o in orgs:
        o["foiz"] = round((o["technics_count"] * 100) / total_technics, 1)

    # ------------------- PIE: tashkilotlar ulushi -------------------
    pie_labels = [o["name"] for o in orgs]
    pie_values = [o["technics_count"] for o in orgs]

    # ------------------- AREA: category (x) va organization (series) -------------------
    cats_qs = list(Category.objects.all().order_by("id").values("id", "name"))
    cat_ids = [c["id"] for c in cats_qs]
    categories = [c["name"] for c in cats_qs]

    org_ids = [o["id"] for o in orgs]

    grouped = (
        Technics.objects
        .filter(organization_id__in=org_ids, category_id__in=cat_ids)
        .values("organization_id", "category_id")
        .annotate(cnt=Count("id"))
    )

    lookup = {(g["organization_id"], g["category_id"]): g["cnt"] for g in grouped}

    series = []
    for o in orgs:
        data = [lookup.get((o["id"], cid), 0) for cid in cat_ids]
        series.append({"name": o["name"], "data": data})

    # ------------------- FUNNEL: tashkilotlar bo‘yicha (katta -> kichik) -------------------
    orgs_sorted = sorted(orgs, key=lambda x: x["technics_count"], reverse=True)
    # ko'p bo'lsa 8 ta ko'rsatamiz (xohlasangiz [:8] ni olib tashlang)
    funnel_labels = [o["name"] for o in orgs_sorted[:8]]
    funnel_values = [o["technics_count"] for o in orgs_sorted[:8]]

    context = {
        "orgs_qs": orgs,
        "categories": categories,
        "series": series,

        "pie_labels": pie_labels,
        "pie_values": pie_values,

        "funnel_labels": funnel_labels,
        "funnel_values": funnel_values,
    }
    return render(request, "main/tex_status.html", context)