from django.shortcuts import render,redirect
from django.contrib import messages
from docx import Document
from django.http import HttpResponse
from collections import defaultdict
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.admin.models import LogEntry
from .utils import *
from django.core.files import File
from io import BytesIO
from .docx_tables import *
from .ajax_views import *
import requests
from PyPDF2 import PdfReader
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Prefetch
from django.core.exceptions import PermissionDenied
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from datetime import datetime, timedelta
from django.db import transaction
from .forms import *
from django.contrib.auth import update_session_auth_hash
from django.core.paginator import Paginator
import uuid
from django.urls import reverse
from urllib.parse import urlencode
from django.views.decorators.http import require_POST
from decimal import Decimal, InvalidOperation
from datetime import date

def global_data(request):
    return {
        "global_organizations": Organization.objects.all(),
        "global_categorys": Category.objects.all(),
    }


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

    emp_form = EmployeeProfileForm(instance=employee)
    email_form = UserEmailForm(instance=user)
    pwd_form = StyledPasswordChangeForm(user=user)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "edit_profile":
            emp_form = EmployeeProfileForm(request.POST, request.FILES or None, instance=employee)
            email_form = UserEmailForm(request.POST, instance=user)

            if emp_form.is_valid() and email_form.is_valid():
                emp_form.save()
                email_form.save()
                messages.success(request, "Profil muvaffaqiyatli yangilandi")
                return redirect("profil")
            messages.info(request, "Maydonlarda xatolik bor. Qayta tekshiring")

        elif action == "change_password":
            pwd_form = StyledPasswordChangeForm(user=user, data=request.POST)
            if pwd_form.is_valid():
                pwd_form.save()
                update_session_auth_hash(request, pwd_form.user)
                messages.success(request, "Parol muvaffaqiyatli o‘zgartirildi")
                return redirect("profil")
            messages.info(request, "Parolni o‘zgartirishda xatolik")

        else:
            messages.info(request, "Noto‘g‘ri so‘rov")
            return redirect("profil")

    return render(request, "main/profil.html", {
        "employee": employee,
        "emp_form": emp_form,
        "email_form": email_form,
        "pwd_form": pwd_form,
    })


@never_cache
@login_required
def index(request):
    # 1) Employee + Rol xavfsiz tekshiruv
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)  # rol yo‘q bo‘lsa None
    if not role:
        raise PermissionDenied

    if role.client:   # client bo‘lsa kirish yo‘q
        raise PermissionDenied

    org_qs = Organization.objects.filter(org_type__in=["IMV", "PENSIYA", "GAZNA"]).only("id", "name", "org_type")
    cat_qs = Category.objects.all().only("id", "name")

    orgs = list(org_qs)
    cats = list(cat_qs)

    # 2) Chart uchun bitta query: category + organization bo‘yicha group count
    grouped = (
        Technics.objects
        .filter(employee__organization__in=orgs, category__in=cats)
        .values("category_id", "employee__organization_id")
        .annotate(cnt=Count("id"))
    )

    # tez lookup: (cat_id, org_id) -> cnt
    m = {(g["category_id"], g["employee__organization_id"]): g["cnt"] for g in grouped}

    chart_data = []
    for cat in cats:
        row = {"category": cat.name}
        for org in orgs:
            row[f"org_{org.id}"] = m.get((cat.id, org.id), 0)
        chart_data.append(row)

    # 3) Pie uchun ham bitta query: org bo‘yicha count
    pie_grouped = (
        Technics.objects
        .filter(employee__organization__in=orgs)
        .values("employee__organization_id", "employee__organization__name")
        .annotate(cnt=Count("id"))
    )
    pie_data = [{"name": p["employee__organization__name"], "count": p["cnt"]} for p in pie_grouped]

    # 4) organizations1 (sizda kerak bo‘lsa) — shu yerda ham optimize
    organizations1 = (
        Organization.objects
        .filter(id__in=[o.id for o in orgs])
        .annotate(technics_count=Count("employee__technics", distinct=True))
        .only("id", "name")
    )

    logs = LogEntry.objects.select_related("user", "content_type").order_by("-action_time")[:10]

    context = {
        "logs": logs,
        "organizations1": organizations1,
        "organizations": orgs,
        "categorys": cats,
        "chart_data": json.dumps(chart_data, cls=DjangoJSONEncoder),
        "pie_data": json.dumps(pie_data, cls=DjangoJSONEncoder),
    }
    return render(request, "main/index.html", context)


@never_cache
@login_required
def contact(request):
    employee = getattr(request.user, "employee", None)

    # Deed listlar (tezroq bo‘lishi uchun select_related)
    deed_sender = (
        Deed.objects
        .filter(sender=employee)
        .select_related("sender", "receiver")
        .order_by("-id")
    )

    deed_receiver = (
        Deed.objects
        .filter(receiver=employee)
        .select_related("sender", "receiver")
        .order_by("-id")
    )

    deed_consent = (
        Deed.objects
        .filter(deedconsent__employee=employee)
        .select_related("sender", "receiver")
        .distinct()              # ✅ dublikat bo‘lmasin
        .order_by("-id")
    )

    senders = (
        Employee.objects.filter(rol__boss=True)
        .select_related("user", "rank", "organization", "department", "directorate", "division")
        .order_by("last_name", "first_name", "father_name")
    )

    context = {
        "deed_sender": deed_sender,
        "deed_receiver": deed_receiver,
        "deed_consent": deed_consent,
        "senders": senders,
        "organization": Organization.objects.exclude(org_type="IVS"),
    }
    return render(request, "main/contact.html", context)


def deed_status(request, pk):
    deed = get_object_or_404(Deed, pk=pk)
    context = {"deed": deed}
    return render(request, "main/deed_status.html", context)


@never_cache
@login_required
@transaction.atomic
def deed_post(request):
    if request.method != "POST":
        return redirect("contact")

    employee = getattr(request.user, "employee", None)
    back_url = request.META.get("HTTP_REFERER", "/")

    message = (request.POST.get("message") or "").strip()
    receiver_id = (request.POST.get("receiver_id") or "").strip()
    agreements = request.POST.getlist("agreements[]")

    if not receiver_id:
        messages.info(request, "Qabul qiluvchi tanlanmadi")
        return redirect(back_url)

    receiver = get_object_or_404(Employee.objects.select_related("user"), id=receiver_id)

    upload_file = request.FILES.get("file")
    if not upload_file:
        messages.info(request, "Fayl yuklanmadi")
        return redirect(back_url)

    ext = os.path.splitext(upload_file.name)[1].lower()
    if ext not in [".docx", ".pdf"]:
        messages.info(request, "❌ Faqat Word (DOCX) yoki PDF fayl yuklash mumkin")
        return redirect(back_url)

    # ✅ xavfsiz filename (ixtiyoriy, lekin tavsiya)
    upload_file.name = f"deed_{uuid.uuid4().hex}{ext}"

    # 1) Deed yaratamiz
    deed = Deed.objects.create(
        sender=employee,
        receiver=receiver,
        message_sender=message,
        file=upload_file,
        status_sender="viewed",
        status_receiver="viewed",
    )

    file_path = deed.file.path

    # 2) DOCX bo‘lsa PDF ga o‘tkazamiz
    if ext == ".docx":
        pdf_path, debug = convert_docx_to_pdf_libre(file_path)

        if not pdf_path or not os.path.exists(pdf_path):
            # atomic bo‘lgani uchun deed ham rollback bo‘ladi
            messages.info(request, "❌ DOCX → PDF konvertatsiya xatosi")
            raise Exception(f"DOCX->PDF failed: {debug}")

        # eski docx ni o‘chiramiz
        try:
            os.remove(file_path)
        except Exception:
            pass

        # pdf ni deed.file ga qayta saqlaymiz
        with open(pdf_path, "rb") as f:
            deed.file.save(os.path.basename(pdf_path), File(f), save=True)

        try:
            os.remove(pdf_path)
        except Exception:
            pass

    # 3) Kelishuvchilar — N+1 ni yo‘q qilamiz
    # agreements ichidan bo‘shlarni tozalaymiz, dublikatni olib tashlaymiz
    ids = []
    for x in agreements:
        x = (x or "").strip()
        if x.isdigit():
            ids.append(int(x))
    ids = list(set(ids))

    # xohlasangiz sender/receiver ni olib tashlaymiz
    ids = [i for i in ids if i not in (employee.id, receiver.id)]

    if ids:
        emps = Employee.objects.filter(id__in=ids).only("id")
        objs = [Deedconsent(deed=deed, employee=e, status="viewed") for e in emps]
        Deedconsent.objects.bulk_create(objs, ignore_conflicts=True)

    messages.success(request, "Imzolashga yuborildi")
    return redirect(back_url)


@never_cache
@login_required
def deed_action(request, pk):
    if request.method != "POST":
        return redirect(request.META.get("HTTP_REFERER", "/"))

    emp = getattr(request.user, "employee", None)
    if not emp:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")
    action = (request.POST.get("action") or "").strip()

    deed = get_object_or_404(
        Deed.objects.select_related("sender", "receiver"),
        pk=pk
    )

    # kim bosdi?
    if deed.receiver_id == emp.id:
        role = "receiver"
        message = (request.POST.get("message_receiver") or "").strip()
    elif deed.sender_id == emp.id:
        role = "sender"
        message = (request.POST.get("message_sender") or "").strip()
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

        # next url ni xavfsiz encode qilamiz
        after_sso_url = reverse("deed_pdf_view", args=[deed.id]) + "?" + urlencode({"next": back_url})

        request.session["PENDING_APPROVE"] = {
            "deed_id": deed.id,
            "role": role,          # sender/receiver
            "message": message,
            "redirect_url": back_url,
            "after_sso_url": after_sso_url,
        }
        request.session.modified = True
        return redirect("sso_start_page")

    messages.error(request, "Noto‘g‘ri amal")
    return redirect(back_url)


@login_required
@never_cache
def sso_start_page(request):
    pending = request.session.get("PENDING_APPROVE")
    if not pending:
        messages.info(request, "Tasdiqlash topilmadi")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    return render(request, "main/sso.html", {
        "client_id": settings.SSO_CLIENT_ID,
        "sso_auth_url": settings.SSO_AUTH_URL,
        "redirect_uri": get_sso_redirect_uri(request),
    })


@login_required
@never_cache
def sso_callback_page(request):
    return render(request, "main/callback.html", {
        "redirect_uri": get_sso_redirect_uri(request),
    })


@csrf_exempt
@never_cache
@login_required
@require_POST
def sso_exchange_and_finish(request):
    pending = None
    try:
        try:
            body = json.loads(request.body or "{}")
        except Exception:
            return JsonResponse({"status": "error", "message": "JSON noto‘g‘ri", "redirect": "/"}, status=400)

        code = body.get("code")
        code_verifier = body.get("codeVerifier")
        redirect_uri = body.get("redirectUri")

        if not code or not code_verifier or not redirect_uri:
            return JsonResponse(
                {"status": "error", "message": "SSO parametrlari to‘liq emas", "redirect": "/"},
                status=400
            )

        # 2) Pending tekshiruv
        pending = request.session.get("PENDING_APPROVE")
        if not pending:
            raise PermissionDenied("Pending yo‘q")

        role = pending.get("role")  # sender/receiver/consent
        message = pending.get("message", "")
        redirect_url = pending.get("redirect_url", "/")
        after_sso_url = pending.get("after_sso_url") or redirect_url

        employee = getattr(request.user, "employee", None)
        if not employee:
            request.session.pop("PENDING_APPROVE", None)
            return JsonResponse({"status": "forbidden", "message": "Employee yo‘q", "redirect": redirect_url}, status=403)

        token_data = exchange_code_for_token(code, code_verifier, redirect_uri)
        id_token = token_data.get("id_token")
        if not id_token:
            raise PermissionDenied("id_token yo‘q")

        user_data = decode_jwt(id_token) or {}
        sso_pinfl = user_data.get("pinfl")
        employee_pinfl = getattr(employee, "pinfl", None)

        if not employee_pinfl or not sso_pinfl or employee_pinfl != sso_pinfl:
            request.session.pop("PENDING_APPROVE", None)
            return JsonResponse(
                {"status": "forbidden", "message": "PINFL mos emas", "redirect": redirect_url},
                status=403
            )

        if role in ("sender", "receiver"):
            deed_id = pending.get("deed_id")
            if not deed_id:
                raise PermissionDenied("Deed topilmadi")

            request.session["SSO_OK"] = {
                "kind": "deed",
                "role": role,
                "deed_id": int(deed_id),
                "message": message or "",
            }
            request.session.pop("PENDING_APPROVE", None)
            request.session.modified = True
            return JsonResponse({"status": "ok", "redirect": after_sso_url})

        if role == "consent":
            consent_id = pending.get("consent_id")
            if not consent_id:
                raise PermissionDenied("consent_id yo‘q")

            consent = get_object_or_404(Deedconsent.objects.select_related("employee__user"), pk=consent_id)

            if consent.employee.user_id != request.user.id:
                raise PermissionDenied("Ruxsat yo‘q")

            if consent.status != "approved":
                consent.status = "approved"
                consent.message = message or ""
                consent.date_edit = timezone.now()
                consent.save(update_fields=["status", "message", "date_edit"])

            request.session.pop("PENDING_APPROVE", None)
            request.session.modified = True
            return JsonResponse({"status": "ok", "redirect": redirect_url})

        raise PermissionDenied("Noto‘g‘ri pending turi")

    except PermissionDenied as e:
        return JsonResponse({"status": "error", "message": str(e), "redirect": "/"}, status=403)

    except Exception as e:
        print("SSO ERROR:", e)
        return JsonResponse({"status": "error", "message": "SSO xatolik", "redirect": "/"}, status=500)


def exchange_code_for_token(code, code_verifier, redirect_uri):
    auth = base64.b64encode(
        f"{settings.SSO_CLIENT_ID}:{settings.SSO_CLIENT_SECRET}".encode()
    ).decode()

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
    }

    response = requests.post(
        settings.SSO_TOKEN_URL,
        data=data,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=10,
    )

    if response.status_code != 200:
        raise PermissionDenied(f"SSO token olinmadi: {response.text}")
    return response.json()


@never_cache
@login_required
@require_POST
def deedconsent_action(request, pk):
    back_url = request.META.get("HTTP_REFERER", "/")

    consent = get_object_or_404(
        Deedconsent.objects.select_related("employee__user", "deed"),
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

    # ❌ reject — SSO shart emas
    if action == "reject":
        consent.status = "rejected"
        consent.message = message
        consent.date_edit = timezone.now()
        consent.save(update_fields=["status", "message", "date_edit"])
        messages.warning(request, "Rad etildi!")
        return redirect(back_url)

    # ✅ approve — SSO orqali
    if action == "approve":
        request.session["PENDING_APPROVE"] = {
            "role": "consent",
            "consent_id": consent.id,
            "message": message,
            "redirect_url": back_url,
            "after_sso_url": back_url,
        }
        request.session.modified = True
        return redirect("sso_start_page")

    messages.error(request, "Noto‘g‘ri amal")
    return redirect(back_url)


@never_cache
@login_required
def barn_tex(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if not role or not role.barn:
        raise PermissionDenied

    status = (request.GET.get("status") or "").strip()
    organization_id = (request.GET.get("organization") or "").strip()
    category_id = (request.GET.get("category") or "").strip()
    name = (request.GET.get("name") or "").strip()
    page_number = request.GET.get("page", 1)

    has_filter = bool(status or organization_id or category_id or name)

    if not has_filter:
        qs = Technics.objects.none()
        page_obj = Paginator(qs, 100).get_page(page_number)

        params = request.GET.copy()
        params.pop("page", None)

        return render(request, "main/barn_tex.html", {
            "organizations": Organization.objects.only("id", "name").order_by("name"),
            "categories": Category.objects.only("id", "name").order_by("name"),
            "technics_form": TechnicsForm(),

            "page_obj": page_obj,
            "technics": page_obj.object_list,
            "qs_params": params.urlencode(),
            "row_start": 0,

            "total_count": 0,       # filter bo‘lmasa ko‘rsatmaymiz
            "filtered_count": 0,
        })

    # ✅ Filter bor bo‘lsa — query ishlaydi
    qs = (
        Technics.objects
        .select_related("organization", "category", "employee")
        .order_by("-id")
    )

    if organization_id:
        qs = qs.filter(organization_id=organization_id)
    if status:
        qs = qs.filter(status=status)
    if category_id:
        qs = qs.filter(category_id=category_id)

    if name:
        qs = qs.filter(
            Q(name__icontains=name) |
            Q(inventory__icontains=name) |
            Q(serial__icontains=name) |
            Q(year__icontains=name)
        )

    # ✅ countlar faqat filter bo‘lganda
    filtered_count = qs.count()

    # total_count ni ko‘rsatish shart bo‘lmasa olib tashlang (katta jadvalda og‘ir)
    total_count = Technics.objects.count()

    paginator = Paginator(qs, 100)
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)

    context = {
        "organizations": Organization.objects.only("id", "name").order_by("name"),
        "categories": Category.objects.only("id", "name").order_by("name"),
        "technics_form": TechnicsForm(),

        "page_obj": page_obj,
        "technics": page_obj.object_list,
        "qs_params": params.urlencode(),
        "row_start": page_obj.start_index() if filtered_count else 0,

        "total_count": total_count,
        "filtered_count": filtered_count,
    }
    return render(request, "main/barn_tex.html", context)


@login_required
@require_POST
def technics_create(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if not role or not role.barn:   # faqat omborchi qo‘sha olsin
        raise PermissionDenied

    back_url = request.META.get("HTTP_REFERER", "/")

    form = TechnicsForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Texnika qo‘shildi")
    else:
        messages.error(request, "Maʼlumotlarda xatolik bor")

    return redirect(back_url)


@login_required
@require_POST
def technics_delete(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if not role or not role.barn:   # faqat omborchi o‘chirishi mumkin
        raise PermissionDenied

    back_url = request.META.get("HTTP_REFERER", "/")

    tex_id = (request.POST.get("texnika_id") or "").strip()
    if not tex_id.isdigit():
        messages.error(request, "Texnika topilmadi")
        return redirect(back_url)

    tex = get_object_or_404(Technics, id=int(tex_id))
    tex.delete()
    messages.success(request, "Texnika o‘chirildi")
    return redirect(back_url)


@login_required
@require_POST
@transaction.atomic
def technics_attach(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if not role or not role.barn:   # faqat omborchi qo‘sha olsin
        raise PermissionDenied

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


@login_required
@require_POST
@transaction.atomic
def technics_update(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if not role or not role.barn:   # faqat omborchi tahrirlay oladi
        raise PermissionDenied

    back_url = request.META.get("HTTP_REFERER", "/")

    # 🔒 lock (parallel update muammosi bo‘lmasin)
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
def barn_mat(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if not role or not (role.barn or role.boss):
        raise PermissionDenied

    emp_id = (request.GET.get("employee") or "").strip()
    status = (request.GET.get("status") or "").strip()
    name = (request.GET.get("name") or "").strip()
    page_number = request.GET.get("page", 1)

    has_filter = bool(emp_id or status or name)

    # ✅ filter bo‘lmasa bo‘sh ko‘rsatamiz (tez)
    if not has_filter:
        qs = Material.objects.none()
        page_obj = Paginator(qs, 100).get_page(page_number)

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
            "filtered_count": 0,
        })

    qs = (
        Material.objects
        .select_related("employee", "employee__user")
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

    filtered_count = qs.count()
    total_count = Material.objects.count()  # kerak bo‘lmasa olib tashlang

    paginator = Paginator(qs, 100)
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
        "row_start": page_obj.start_index() if filtered_count else 0,
        "total_count": total_count,
        "filtered_count": filtered_count,
    }
    return render(request, "main/barn_mat.html", context)


@login_required
@require_POST
def material_create(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if not role or not role.barn:   # faqat omborchi qo‘sha oladi
        raise PermissionDenied

    back_url = request.META.get("HTTP_REFERER", "/")

    form = MaterialForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Material qo‘shildi!")
    else:
        messages.error(request, "Maʼlumotlarda xatolik bor")

    return redirect(back_url)


@login_required
@require_POST
def material_update(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if not role or not role.barn:   # faqat omborchi tahrirlay oladi
        raise PermissionDenied

    back_url = request.META.get("HTTP_REFERER", "/")

    mat = get_object_or_404(Material, pk=pk)

    mat.name = (request.POST.get("name") or "").strip()
    mat.code = (request.POST.get("code") or "").strip()
    mat.unit = (request.POST.get("unit") or "").strip()

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


@login_required
@require_POST
@transaction.atomic
def material_attach(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if not role or not role.barn:   # faqat omborchi
        raise PermissionDenied

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


@login_required
@require_POST
def material_delete(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if not role or not role.barn:   # faqat omborchi o‘chira oladi
        raise PermissionDenied

    back_url = request.META.get("HTTP_REFERER", "/")

    material_id = (request.POST.get("material_id") or "").strip()
    if not material_id.isdigit():
        messages.error(request, "Material topilmadi")
        return redirect(back_url)

    mat = get_object_or_404(Material, id=int(material_id))

    mat.delete()
    messages.success(request, "Material o‘chirildi")

    return redirect(back_url)


@never_cache
@login_required
def technics(request, slug=None):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if role and role.client:
        raise PermissionDenied

    category = None
    if slug:
        category = get_object_or_404(Category, slug=slug)

    org_id = (request.GET.get("organization") or "").strip()
    dep_id = (request.GET.get("department") or "").strip()
    dir_id = (request.GET.get("directorate") or "").strip()
    div_id = (request.GET.get("division") or "").strip()
    page_number = request.GET.get("page", 1)

    organizations = Organization.objects.only("id", "name").order_by("name")

    qs = (
        Technics.objects
        .select_related("category", "employee", "employee__user", "employee__rank")
        .prefetch_related("extratechnics_set")
        .only(
            "id", "name", "inventory", "serial", "ip", "mac", "year",
            "category__id", "category__name",
            "employee__id",
            "employee__first_name", "employee__last_name", "employee__father_name",
            "employee__user__username",
            "employee__rank__id", "employee__rank__name",
            "employee__organization_id",
            "employee__department_id",
            "employee__directorate_id",
            "employee__division_id",
        )
    )

    if category:
        qs = qs.filter(category=category)

    # id larni isdigit bilan tekshirib olamiz (xavfsiz)
    if org_id and org_id.isdigit():
        qs = qs.filter(employee__organization_id=int(org_id))
    if dep_id and dep_id.isdigit():
        qs = qs.filter(employee__department_id=int(dep_id))
    if dir_id and dir_id.isdigit():
        qs = qs.filter(employee__directorate_id=int(dir_id))
    if div_id and div_id.isdigit():
        qs = qs.filter(employee__division_id=int(div_id))

    filtered_count = qs.count()

    ordered_qs = qs.order_by(
        "employee__last_name",
        "employee__first_name",
        "category__name",
        "name"
    )

    grouped = defaultdict(list)
    for t in ordered_qs:
        grouped[t.employee].append(t)

    grouped_items = list(grouped.items())
    paginator = Paginator(grouped_items, 100)
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)
    qs_params = params.urlencode()

    context = {
        "category": category,
        "organizations": organizations,

        "page_obj": page_obj,
        "grouped_technics": page_obj.object_list,
        "qs_params": qs_params,

        "filtered_count": filtered_count,

        "selected_org": org_id,
        "selected_dep": dep_id,
        "selected_dir": dir_id,
        "selected_div": div_id,
    }
    return render(request, "main/technics.html", context)


@never_cache
@login_required
def organization(request, slug):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if role and role.client:
        raise PermissionDenied

    # ⚡ Technics ni oldindan yuklaymiz (faqat kerakli fieldlar)
    tech_prefetch = Prefetch(
        "technics_set",
        queryset=(
            Technics.objects
            .select_related("category")
            .only("id", "name", "serial", "inventory", "year", "category__id", "category__name")
        ),
        to_attr="tech_list"
    )

    # Employee prefetchniki ham yengillatamiz
    emp_prefetch_org = Prefetch(
        "employee_set",
        queryset=(
            Employee.objects
            .select_related("rank", "user")
            .only(
                "id", "first_name", "last_name", "father_name",
                "rank__id", "rank__name",
                "user__id", "user__username",
                "organization_id", "department_id", "directorate_id", "division_id",
            )
            .prefetch_related(tech_prefetch)
        )
    )

    # 🟢 ORGANIZATION
    org = get_object_or_404(
        Organization.objects
        .annotate(technics_count=Count("employee__technics", distinct=True))
        .prefetch_related(emp_prefetch_org),
        slug=slug
    )

    # 🟡 DEPARTMENTS
    departments = (
        Department.objects
        .filter(organization=org)
        .select_related("organization")
        .annotate(technics_count=Count("employee__technics", distinct=True))
        .prefetch_related(
            Prefetch(
                "employee_set",
                queryset=(
                    Employee.objects
                    .select_related("rank", "user")
                    .only(
                        "id", "first_name", "last_name", "father_name",
                        "rank__id", "rank__name",
                        "user__id", "user__username",
                        "organization_id", "department_id", "directorate_id", "division_id",
                    )
                    .prefetch_related(tech_prefetch)
                )
            )
        )
    )

    # 🔵 DIRECTORATES
    directorates = (
        Directorate.objects
        .filter(department__organization=org)
        .select_related("department")
        .annotate(technics_count=Count("employee__technics", distinct=True))
        .prefetch_related(
            Prefetch(
                "employee_set",
                queryset=(
                    Employee.objects
                    .select_related("rank", "user")
                    .only(
                        "id", "first_name", "last_name", "father_name",
                        "rank__id", "rank__name",
                        "user__id", "user__username",
                        "organization_id", "department_id", "directorate_id", "division_id",
                    )
                    .prefetch_related(tech_prefetch)
                )
            )
        )
    )

    # 🟣 DIVISIONS
    divisions = (
        Division.objects
        .filter(directorate__department__organization=org)
        .select_related("directorate")
        .annotate(technics_count=Count("employee__technics", distinct=True))
        .prefetch_related(
            Prefetch(
                "employee_set",
                queryset=(
                    Employee.objects
                    .select_related("rank", "user")
                    .only(
                        "id", "first_name", "last_name", "father_name",
                        "rank__id", "rank__name",
                        "user__id", "user__username",
                        "organization_id", "department_id", "directorate_id", "division_id",
                    )
                    .prefetch_related(tech_prefetch)
                )
            )
        )
    )

    context = {
        "organizations": org,
        "departments": departments,
        "directorates": directorates,
        "divisions": divisions,
    }
    return render(request, "main/organization.html", context)


@never_cache
@login_required
def document_get(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if role and role.client:
        raise PermissionDenied

    context = {
        "organizations": Organization.objects.only("id", "name", "slug", "org_type").order_by("name"),
        "departments": Department.objects.select_related("organization").only(
            "id", "name", "organization_id"
        ).order_by("name"),
        "directorate": Directorate.objects.select_related("department").only(
            "id", "name", "department_id"
        ).order_by("name"),
        "division": Division.objects.select_related("directorate").only(
            "id", "name", "directorate_id"
        ).order_by("name"),
    }
    return render(request, "main/document.html", context)


@never_cache
@login_required
@require_POST
def document_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if role and role.client:
        raise PermissionDenied

    oylar = [
        "yanvarda", "fevralda", "martda", "aprelda", "mayda", "iyunda",
        "iyulda", "avgustda", "sentabrda", "oktabrda", "noyabrda", "dekabrda"
    ]

    # === FORM ===
    org_id = (request.POST.get("organization") or "").strip()
    dep_id = (request.POST.get("department") or "").strip()
    dir_id = (request.POST.get("directorate") or "").strip()
    div_id = (request.POST.get("division") or "").strip()

    post_id = (request.POST.get("post_id") or "").strip()
    fio_id = (request.POST.get("fio_id") or "").strip()
    date_id = (request.POST.get("date_id") or "").strip()
    namber_id = (request.POST.get("namber_id") or "").strip()
    rim_id = (request.POST.get("rim_id") or "").strip()

    # === OBYEKTLAR (xavfsiz) ===
    org = dep = dir = div = None

    if div_id:
        if not div_id.isdigit():
            return HttpResponse("Division noto‘g‘ri", status=400)
        div = get_object_or_404(Division, id=int(div_id))
    elif dir_id:
        if not dir_id.isdigit():
            return HttpResponse("Directorate noto‘g‘ri", status=400)
        dir = get_object_or_404(Directorate, id=int(dir_id))
    elif dep_id:
        if not dep_id.isdigit():
            return HttpResponse("Department noto‘g‘ri", status=400)
        dep = get_object_or_404(Department, id=int(dep_id))
    elif org_id:
        if not org_id.isdigit():
            return HttpResponse("Organization noto‘g‘ri", status=400)
        org = get_object_or_404(Organization, id=int(org_id))
    else:
        return HttpResponse("Tashkilot / bo‘lim tanlanmagan!", status=400)

    # === SANANI FORMATLASH ===
    formatted_date = ""
    if date_id:
        try:
            dt = datetime.strptime(date_id, "%Y-%m-%d").date()
            formatted_date = f"{dt.year} yil {dt.day}-{oylar[dt.month - 1]}"
        except Exception:
            formatted_date = date_id

    # === QAYSI BO‘LIM TANLANGANI ===
    if div:
        full_obj = div
        filter_kwargs = {"employee__division_id": div.id}
    elif dir:
        full_obj = dir
        filter_kwargs = {"employee__directorate_id": dir.id}
    elif dep:
        full_obj = dep
        filter_kwargs = {"employee__department_id": dep.id}
    else:
        full_obj = org
        filter_kwargs = {"employee__organization_id": org.id}

    # === TEXNIKA QS ===
    komp_names = ["Kompyuter", "Planshet", "Noutbook", "Doska"]
    prin_names = ["A4 Printer", "Printer", "scaner"]

    base_qs = Technics.objects.filter(**filter_kwargs)

    # ✅ 1 ta so‘rovda 2 ta count
    counts = (
        base_qs.values("category__name")
        .filter(category__name__in=komp_names + prin_names)
        .annotate(c=Count("id"))
    )
    komp_count = sum(x["c"] for x in counts if x["category__name"] in komp_names)
    prin_count = sum(x["c"] for x in counts if x["category__name"] in prin_names)

    texnikalar_matni = ""
    if komp_count > 0:
        texnikalar_matni += f"1.1. Biriktirilgan kompyuterlarga xizmat ko‘rsatish – {komp_count} dona.\n"
    if prin_count > 0:
        texnikalar_matni += f"1.2. Printerlarga xizmat ko‘rsatish – {prin_count} dona.\n"
    if not texnikalar_matni:
        texnikalar_matni = "Texnikalar mavjud emas."

    # === JADVAL UCHUN DATA (faqat values) ===
    kompyuterlar = list(
        base_qs.filter(category__name__in=komp_names).values("name", "serial", "inventory")
    )
    printerlar = list(
        base_qs.filter(category__name__in=prin_names).values("name", "serial")
    )

    # === SHABLON ===
    template_path = os.path.join(settings.MEDIA_ROOT, "document", "dalolatnoma.docx")
    if not os.path.exists(template_path):
        return HttpResponse("Shablon fayl topilmadi!", status=404)

    doc = Document(template_path)

    replacements = {
        "DEPARTMENT": getattr(full_obj, "name", "") or "",
        "POST": post_id,
        "FIO": fio_id,
        "DATA": formatted_date,
        "NAMBER": namber_id,
        "RIM": rim_id,
        "STYLE": getattr(full_obj, "name", "") or "",
        "TEXNIKALAR": texnikalar_matni,
    }

    # === TEXT ALMASHTIRISH ===
    bold_keys = {"STYLE", "FIO", "DATA", "NAMBER"}
    for p in doc.paragraphs:
        for run in p.runs:
            txt = run.text
            changed = False
            for old, new in replacements.items():
                if old in txt:
                    txt = txt.replace(old, new)
                    changed = True
                    if old in bold_keys:
                        run.font.bold = True
            if changed:
                run.text = txt
                run.font.name = "Times New Roman"
                run.font.size = Pt(12)

    # === TABLE joyi ===
    target_paragraph = next((p for p in doc.paragraphs if "TABLE" in p.text), None)
    if target_paragraph:
        target_paragraph.text = ""

    headers_pc = ["№", "Rusumi", "Kompyuter SR:", "Inventar raqami:"]
    headers_printer = ["№", "Rusumi", "Printer SR:"]

    heading1, table1 = create_table(
        doc,
        "Kompyuterlar (PC/Noutbuk/Planshet/Info-kiosk)",
        kompyuterlar,
        headers_pc
    )
    heading2, table2 = create_table(
        doc,
        "Printerlar (A4/A3/Skanner)",
        printerlar,
        headers_printer
    )

    if target_paragraph:
        if table1:
            target_paragraph._p.addnext(heading1._p)
            heading1._p.addnext(table1._tbl)
            if table2:
                table1._tbl.addnext(heading2._p)
                heading2._p.addnext(table2._tbl)
        elif table2:
            target_paragraph._p.addnext(heading2._p)
            heading2._p.addnext(table2._tbl)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    response["Content-Disposition"] = 'attachment; filename="dalolatnoma.docx"'
    doc.save(response)
    return response


@never_cache
@login_required
def order_sender(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if role and role.client:
        raise PermissionDenied

    orders_qs = (
        Order.objects
        .filter(sender=employee)
        .select_related("goal", "goal__topic", "technics", "receiver", "sender")
        .order_by("-id")
    )

    topics_qs = Topic.objects.only("id", "name").order_by("name")

    goals_qs = (
        Goal.objects
        .select_related("topic")
        .only("id", "name", "topic__id", "topic__name")
        .order_by("name")
    )

    technics_qs = (
        Technics.objects
        .filter(employee=employee)
        .select_related("category")
        .only("id", "name", "serial", "inventory", "category__id", "category__name")
        .order_by("name")
    )

    context = {
        "order": orders_qs,
        "topic": topics_qs,
        "goal": goals_qs,
        "technics": technics_qs,
    }
    return render(request, "main/order_sender.html", context)


@never_cache
@login_required
@require_POST
def order_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied


    goal_id = (request.POST.get("goal") or "").strip()
    technics_id = (request.POST.get("technics") or "").strip()
    body = (request.POST.get("body") or "").strip()
    type_of_work = (request.POST.get("type_of_work") or "online").strip()


    allowed_types = {"online", "offline"}
    if type_of_work not in allowed_types:
        type_of_work = "online"

    # FK larni xavfsiz olish
    goal = None
    if goal_id:
        if not goal_id.isdigit():
            messages.error(request, "Goal noto‘g‘ri")
            return redirect("order_sender")
        goal = get_object_or_404(Goal, id=int(goal_id))

    technic = None
    if technics_id:
        if not technics_id.isdigit():
            messages.error(request, "Texnika noto‘g‘ri")
            return redirect("order_sender")
        # ✅ xavfsizlik: user faqat o‘ziga biriktirilgan texnikani tanlay olsin
        technic = get_object_or_404(Technics, id=int(technics_id), employee=employee)

    Order.objects.create(
        sender=employee,
        goal=goal,
        technics=technic,
        body=body,
        type_of_work=type_of_work,
    )

    messages.success(request, "Zayavka yuborildi")
    return redirect("order_sender")


@never_cache
@login_required
def order_deed(request, pk):
    order = get_object_or_404(Order, pk=pk)

    sender = order.sender

    dep = (
        sender.division.name if sender and sender.division else
        sender.directorate.name if sender and sender.directorate else
        sender.department.name if sender and sender.department else
        sender.organization.name if sender and sender.organization else ""
    )

    emp_sen = (
        Employee.objects.filter(
            Q(organization=sender.organization) &
            Q(department=sender.department) &
            Q(directorate=sender.directorate) &
            Q(division=sender.division),
            rol__boss=True
        )
        .select_related("rank")
        .first()
    )

    sender_text = ""
    if emp_sen:
        rank = emp_sen.rank.name if emp_sen.rank else ""
        sender_text = f"{emp_sen.full_name} ({rank})" if rank else emp_sen.full_name

    doc = Document(os.path.join(settings.MEDIA_ROOT, "document", "akt.docx"))

    ORG_TEXT = {
        "IVS": "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi Axborot texnologiyalar markazining vakillari:",
        "IMV": "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi tashkiloti vakillari:",
        "GAZNA": "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi G'aznachilik qo'mitasi vakillari:",
        "PENSIYA": "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi Budjetdan tashqari pensiya jamg'armasi vakillari:",
    }

    org_type = getattr(getattr(sender, "organization", None), "org_type", None)
    org_name = ORG_TEXT.get(org_type, "")

    replace_text(doc, {
        "ID": f"№ {order.id}",
        "ORGANIZATION": org_name,
        "RECEIVER": (f"{order.receiver.full_name} ({order.receiver.rank.name})"
                        if order.receiver and order.receiver.rank
                        else (order.receiver.full_name if order.receiver else "")
                    ),
        "SENDER": sender_text,
        "SANA": date.today().strftime("%d.%m.%Y"),
        "DEPARTMENT": dep,
    })

    target = next((p for p in doc.paragraphs if "TABLE" in p.text), None)
    if not target:
        return HttpResponse("TABLE topilmadi", status=500)
    target.text = ""

    headers = ["№", "Qurilma Nomi", "Seriya", "Material", "Soni", "Birligi", "F.I.Sh.", "Lavozimi", "Narxi"]

    rows = []
    for om in order.materials.all():
        rows.append([
            order.technics.name if order.technics else "",
            order.technics.serial if order.technics else "",
            om.material.name if om.material else "",
            om.number or "",
            (om.material.unit if om.material and om.material.unit else "dona"),
            sender.full_name if sender else "",
            (sender.rank.name if sender and sender.rank else ""),
            (f"{om.material.price:,}".replace(",", " ") if om.material and om.material.price else ""),
        ])

    h, table = create_table_akt(doc, "Biriktirilgan texnika bo‘yicha dalolatnoma", rows, headers)

    target._p.addnext(h._p)
    h._p.addnext(table._tbl)

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    response["Content-Disposition"] = f'attachment; filename="order_{order.id}.docx"'
    return response


@never_cache
@login_required
def order_receiver(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if role and role.client:
        raise PermissionDenied

    is_boss = bool(role and role.boss)

    orders = (
        Order.objects
        .select_related(
            "sender", "sender__rank", "sender__region",
            "receiver", "receiver__rank",
            "goal", "goal__topic",
            "technics", "technics__category",
        )
        .order_by("-id")
    )

    if is_boss:
        # Boss: region bo‘yicha ko‘radi
        orders = orders.filter(sender__region=employee.region)
    else:
        # Oddiy: faqat o‘ziga tushganlari
        orders = orders.filter(receiver=employee)

    context = {
        "employee": (
            Employee.objects
            .filter(organization__org_type="IVS")
            .select_related("user", "rank", "organization")
            .only(
                "id", "first_name", "last_name", "father_name",
                "user__username",
                "rank__id", "rank__name",
                "organization__id", "organization__name",
            )
            .order_by("last_name", "first_name")
        ),
        "order": orders,
        "topic": Topic.objects.only("id", "name").order_by("name"),
        "goal": (
            Goal.objects
            .select_related("topic")
            .only("id", "name", "topic__id", "topic__name")
            .order_by("name")
        ),
    }
    return render(request, "main/order_receiver.html", context)


@never_cache
@login_required
def order_approved(request):
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


@never_cache
@login_required
@transaction.atomic
def ordermaterial_post(request):

    if request.method != "POST":
        return redirect("order_sender")

    employee_id = request.POST.get("employee_id")
    order_id = request.POST.get("order_id")
    technics_id = request.POST.get("technics_id")
    material_ids = request.POST.getlist("material_id[]")
    numbers = request.POST.getlist("number[]")

    order = get_object_or_404(Order, id=order_id)

    if technics_id:
        order.technics_id = technics_id

    if employee_id:
        order.receiver_id = employee_id
        order.user = request.user.employee
        order.status = "accepted"

    order.save()

    for m_id, num in zip(material_ids, numbers):
        if not m_id:
            continue

        material = Material.objects.select_for_update().filter(id=m_id).first()
        if not material:
            messages.info(request, "Material topilmadi!")

        try:
            number = int(num) if num else 1
        except ValueError:
            messages.info(request, "Material soni noto‘g‘ri kiritilgan!")
            return redirect(request.META.get("HTTP_REFERER", "/"))

        if number <= 0:
            messages.info(request, "Material soni 0 yoki manfiy bo‘lishi mumkin emas!")

        if material.number < number:
            messages.info(request, f"{material.name} yetarli emas! Omborda {material.number} dona bor.")
            return redirect(request.META.get("HTTP_REFERER", "/"))

        OrderMaterial.objects.create(order=order, material=material, number=number)

        material.number -= number
        material.save()

    messages.success(request, "Zayavka muvaffaqiyatli qabul qilindi")
    return redirect("order_receiver")


@never_cache
@login_required
def akt_get(request):

    if not hasattr(request.user, "employee"):
        raise PermissionDenied

    if request.user.employee.rol.client:
        raise PermissionDenied

    context = {
        'organizations': Organization.objects.all(),
    }
    return render(request, 'main/akt.html', context)


@never_cache
@login_required
def akt_post(request):
    if request.method != "POST":
        return redirect("akt_get")

    org_id = request.POST.get("organization") or None
    dep_id = request.POST.get("department") or None
    employee_id = request.POST.get("employee") or None

    date_id1 = request.POST.get("date1")
    date_id2 = request.POST.get("date2")

    # Sana parse
    date1 = timezone.make_aware(datetime.strptime(date_id1, "%Y-%m-%d"))
    date2 = timezone.make_aware(datetime.strptime(date_id2, "%Y-%m-%d") + timedelta(days=1))

    qs = OrderMaterial.objects.filter(
        order__date_creat__gte=date1,
        order__date_creat__lt=date2,
        order__sender__department_id=dep_id,
        order__receiver__region=request.user.employee.region,
    )

    org = Organization.objects.filter(id=org_id).first() if org_id else None
    dep = Department.objects.filter(id=dep_id).first() if dep_id else None
    sender = Employee.objects.filter(id=employee_id).first() if employee_id else None

    doc = Document(os.path.join(settings.MEDIA_ROOT, "document", "akt.docx"))

    ORG_TEXT = {
        "IVS": "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi Axborot texnologiyalar markazining vakillari:",
        "IMV": "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi tashkiloti vakillari:",
        "GAZNA": "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi G'aznachilik qo'mitasi vakillari:",
        "PENSIYA": "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi Budjetdan tashqari pensiya jamg'armasi vakillari:",
    }
    org_name = ORG_TEXT.get(org.org_type, "")

    employees = []
    seen = set()

    for q in qs:
        emp = q.order.receiver if q.order and q.order.receiver else None
        if emp and emp.id not in seen:
            seen.add(emp.id)
            rank = emp.rank.name if emp.rank else ""
            text = f"{emp.full_name} ({rank})" if rank else emp.full_name
            employees.append(text)

    receiver_text = ", ".join(employees)

    replace_text(doc, {
        "ID": f" ",
        "ORGANIZATION": org_name,
        "SANA": date.today().strftime("%d.%m.%Y"),
        "RECEIVER": receiver_text,
        "SENDER": sender.full_name if sender else "",
        "DEPARTMENT": dep.name if dep else "",
    })

    target = next((p for p in doc.paragraphs if "TABLE" in p.text), None)
    if not target:
        return HttpResponse("TABLE topilmadi", status=500)

    target.text = ""
    target.paragraph_format.space_before = Pt(0)
    target.paragraph_format.space_after = Pt(0)
    target.paragraph_format.line_spacing = 1

    headers = [
        "№",
        "Ish bajarilgan qurilma nomi",
        "Qurilma seriya raqami",
        "Sarf materiallari, ehtiyot qismlar, uskunalar va boshqalar nomi",
        "Soni",
        "O'lchov birligi",
        "F.I.Sh.",
        "Lavozimi",
        "Eslatma*",
    ]

    rows = []
    for q in qs:
        rows.append([
            q.order.technics.name if q.order.technics else "",
            q.order.technics.serial if q.order.technics else "",
            q.material.name if q.material else "",
            q.number or "",
            (q.material.unit if q.material and q.material.unit else "dona"),
            q.order.sender.full_name if q.order and q.order.sender else "",
            (q.order.sender.rank.name if q.order and q.order.sender and q.order.sender.rank else ""),
            f"{q.material.price:,}".replace(",", " ") if q.material and q.material.price else "",
        ])

    h, table = create_table_akt(
        doc,
        "Biriktirilgan texnika bo‘yicha dalolatnoma",
        rows,
        headers
    )

    target._p.addnext(h._p)
    h._p.addnext(table._tbl)

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    response["Content-Disposition"] = 'attachment; filename="order.docx"'
    return response


@never_cache
@login_required
def svod_get(request):

    if not hasattr(request.user, "employee"):
        raise PermissionDenied

    if request.user.employee.rol.client:
        raise PermissionDenied

    context = {
        'organizations': Organization.objects.all(),
        'departments': Department.objects.select_related('organization'),
        'directorate': Directorate.objects.select_related('department'),
        'division': Division.objects.select_related('directorate'),
    }
    return render(request, 'main/svod.html', context)


from collections import OrderedDict
@never_cache
@login_required
def svod_post(request):
    if request.method != "POST":
        return redirect("document_get")

    org_id = request.POST.get("organization")
    date_id1 = request.POST.get("date1")
    date_id2 = request.POST.get("date2")

    date1 = timezone.make_aware(datetime.strptime(date_id1, "%Y-%m-%d"))
    date2 = timezone.make_aware(datetime.strptime(date_id2, "%Y-%m-%d") + timedelta(days=1))

    qs = OrderMaterial.objects.filter(
        order__date_creat__gte=date1,
        order__date_creat__lt=date2,
        order__sender__organization_id=org_id,
        order__receiver__region=request.user.employee.region,
    )

    org = Organization.objects.filter(id=org_id).first() if org_id else None
    doc = Document(os.path.join(settings.MEDIA_ROOT, "document", "svod.docx"))

    ORG_TEXT = {
        "IVS": "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi Axborot texnologiyalar markazini",
        "IMV": "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi",
        "GAZNA": "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi G'aznachilik qo'mitasi",
        "PENSIYA": "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi Budjetdan tashqari pensiya jamg'armasi",
    }
    org_name = ORG_TEXT.get(getattr(org, "org_type", None), "")
    replace_text(doc, {
        "ORGANIZATION": org_name,
        "SANA": date.today().strftime("%d.%m.%Y"),
    })

    target = next((p for p in doc.paragraphs if "TABLE" in p.text), None)
    if not target:
        return HttpResponse("TABLE topilmadi", status=500)

    # TABLE paragrafini tozalaymiz
    target.text = ""
    target.paragraph_format.space_before = Pt(0)
    target.paragraph_format.space_after = Pt(0)
    target.paragraph_format.line_spacing = 1

    headers = [
        "№", "Materialning nomi", "O'lchov birligi", "Miqdori",
        "Birlik narxi", "Umumiy qiymati", "Eslatma", "Kod 1С"
    ]

    rows_map = OrderedDict()

    for q in qs:
        if not q.material:
            continue

        unit_price = q.material.price or 0
        qty = q.number or 0
        total = unit_price * qty

        code = getattr(q.material, "code", "") or ""
        unit = (q.material.unit or "dona")
        name = q.material.name or ""

        # Guruhlash kaliti: bitta material
        key = (q.material.id, name, unit, code)

        # Eslatma: Akt №ID ga DD.MM.YYYYy,
        eslatma_one = ""
        if q.order and q.order.date_creat:
            eslatma_one = f"Akt №{q.order.id} ga  {q.order.date_creat.strftime('%d.%m.%Y')} y,\n"

        if key not in rows_map:
            rows_map[key] = {
                "name": name,
                "unit": unit,
                "qty": 0,
                "unit_price": unit_price,  # material narxi (doim bir xil deb oldik)
                "total": 0,
                "notes": [],
                "code": code,
                "order_seen": set(),  # bitta order qayta yozilib qolmasin
            }

        rows_map[key]["qty"] += qty
        rows_map[key]["total"] += total

        # Eslatmada order id lar unik bo‘lsin
        if q.order_id and q.order_id not in rows_map[key]["order_seen"] and eslatma_one:
            rows_map[key]["notes"].append(eslatma_one)
            rows_map[key]["order_seen"].add(q.order_id)

    grand_total = sum(int(v.get("total") or 0) for v in rows_map.values())

    rows = []
    for _, v in rows_map.items():
        note_text = " ".join(v["notes"])  # uzun bo‘lsa: "\n".join(v["notes"]) qiling

        rows.append([
            v["name"],
            v["unit"],
            v["qty"],  # yig‘indi
            f"{v['unit_price']:,}".replace(",", " "),
            f"{v['total']:,}".replace(",", " "),
            note_text,
            v["code"],
        ])

    table = create_table_cols_svod(doc, rows, headers, grand_total=grand_total)
    target._p.addnext(table._tbl)

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    response["Content-Disposition"] = 'attachment; filename="svod.docx"'
    return response


@never_cache
@login_required
def reestr_get(request):

    if not hasattr(request.user, "employee"):
        raise PermissionDenied

    if request.user.employee.rol.client:
        raise PermissionDenied

    context = {
        'organizations': Organization.objects.all(),
        'departments': Department.objects.select_related('organization'),
        'directorate': Directorate.objects.select_related('department'),
        'division': Division.objects.select_related('directorate'),
    }
    return render(request, 'main/reestr.html', context)


@never_cache
@login_required
def reestr_post(request):
    if request.method != "POST":
        return redirect("document_get")
    user = request.user.employee

    org_id = request.POST.get("organization")
    date_id1 = request.POST.get("date1")
    date_id2 = request.POST.get("date2")

    # Sana parse
    date1 = timezone.make_aware(datetime.strptime(date_id1, "%Y-%m-%d"))
    date2 = timezone.make_aware(datetime.strptime(date_id2, "%Y-%m-%d") + timedelta(days=1))

    qs = OrderMaterial.objects.filter(
        order__date_creat__gte=date1,
        order__date_creat__lt=date2,
        order__sender__organization_id=org_id,
        order__receiver__region=request.user.employee.region,
    )

    org = Organization.objects.filter(id=org_id).first() if org_id else None
    doc = Document(os.path.join(settings.MEDIA_ROOT, "document", "reestr.docx"))

    ORG_TEXT = {
        "IVS": "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi Axborot texnologiyalar markazini",
        "IMV": "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi",
        "GAZNA": "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi G'aznachilik qo'mitasi",
        "PENSIYA": "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi Budjetdan tashqari pensiya jamg'armasi",
    }
    org_name = ORG_TEXT.get(getattr(org, "org_type", None), "")
    replace_text(doc, {
        "ORGANIZATION":org_name,
        "XUDUD": request.user.employee.region.name if request.user.employee.region else "",
    })

    target = next((p for p in doc.paragraphs if "TABLE" in p.text), None)
    if not target:
        return HttpResponse("TABLE topilmadi", status=500)

    # TABLE paragrafini tozalash
    target.text = ""
    target.paragraph_format.space_before = Pt(0)
    target.paragraph_format.space_after = Pt(0)
    target.paragraph_format.line_spacing = 1

    rows_map = OrderedDict()

    for q in qs:
        if not q.material or not q.order or not q.order.technics:
            continue

        technics = q.order.technics
        material_obj = q.material

        # Texnika
        name = technics.name or ""
        serial = getattr(technics, "serial", "") or ""

        # Material
        material_name = material_obj.name or ""
        qty = int(q.number or 0)
        unit_price = int(material_obj.price or 0)
        total = unit_price * qty
        code = getattr(material_obj, "code", "") or ""

        # Kimlar
        sender = q.order.sender.full_name if getattr(q.order, "sender", None) else ""
        rank = getattr(q.order.sender, "rank", "") if getattr(q.order, "sender", None) else ""
        department = getattr(q.order.sender, "department", "") if getattr(q.order, "sender", None) else ""
        receiver = q.order.receiver.full_name if getattr(q.order, "receiver", None) else ""

        # Sana format: 25.11.2025
        date_finished = q.order.date_finished.strftime("%d.%m.%Y") if getattr(q.order, "date_finished", None) else ""
        date_creat = q.order.date_creat.strftime("%d.%m.%Y") if getattr(q.order, "date_creat", None) else ""

        order_id = q.order.id or ""

        # ✅ Guruhlash: 1 texnika + 1 material
        key = (technics.id, material_obj.id)

        if key not in rows_map:
            rows_map[key] = {
                "name": name,
                "serial": serial,
                "material": material_name,
                "qty": 0,
                "unit_price": unit_price,
                "total": 0,
                "fio": sender,          # Qurilmadan foydalanuvchi FIO
                "lavozim": rank,        # Qurilmadan foydalanuvchi lavozim
                "tashkilot": department,# Tashkilot/bo‘lim
                "ornatgan": receiver,   # Kim tomonidan o‘rnatilgan
                "ornatish_sana": date_finished,
                "sorov_no": order_id,
                "sorov_sana": date_creat,
                "code": code,
            }

        # ✅ Yig‘indi
        rows_map[key]["qty"] += qty
        rows_map[key]["total"] += total

    # ✅ grand_total — faqat grouped natijalardan
    grand_total = sum(int(v.get("total") or 0) for v in rows_map.values())

    # ✅ Jadval data (№ ni create_table_cols_reestr o‘zi qo‘shadi)
    rows = []
    for _, v in rows_map.items():
        rows.append([
            v["name"],
            v["serial"],
            v["material"],
            v["qty"],
            f"{int(v['unit_price'] or 0):,}".replace(",", " "),
            f"{int(v['total'] or 0):,}".replace(",", " "),
            v["fio"],
            v["lavozim"],
            v["tashkilot"],
            v["ornatgan"],
            v["ornatish_sana"],
            v["sorov_no"],
            v["sorov_sana"],
            v["code"],
        ])

    # ✅ 2 qatorli headerli jadval yaratish
    table = create_table_cols_reestr(doc, rows, grand_total=grand_total)
    target._p.addnext(table._tbl)

    # Faylni qaytarish
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    response["Content-Disposition"] = 'attachment; filename="reestr.docx"'
    return response