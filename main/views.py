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
import tempfile
from django.core.files.base import ContentFile


def global_data(request):
    return {
        "global_organizations": Organization.objects.only("id", "name").order_by("name"),
        "global_categorys": Category.objects.only("id", "name").order_by("name"),
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
    employee = getattr(request.user, "employee", None)
    if not employee or not getattr(employee, "rol", None) or employee.rol.client:
        raise PermissionDenied

    org_ids = [1, 2, 3]

    orgs = list(
        Organization.objects.filter(id__in=org_ids).only("id", "name")
    )

    cats = list(
        Category.objects.only("id", "name")
    )

    # Chart: (category, org) bo‘yicha count
    grouped = (
        Technics.objects
        .filter(organization_id__in=org_ids, category_id__in=[c.id for c in cats])
        .values("category_id", "organization_id")
        .annotate(cnt=Count("id"))
    )

    m = {(g["category_id"], g["organization_id"]): g["cnt"] for g in grouped}

    chart_data = []
    for cat in cats:
        row = {"category": cat.name}
        for org in orgs:
            row[f"org_{org.id}"] = m.get((cat.id, org.id), 0)
        chart_data.append(row)

    # Pie: org bo‘yicha count
    pie_grouped = (
        Technics.objects
        .filter(organization_id__in=org_ids)
        .values("organization_id", "organization__name")
        .annotate(cnt=Count("id"))
        .order_by("organization__name")
    )
    pie_data = [{"name": p["organization__name"], "count": p["cnt"]} for p in pie_grouped]

    organizations1 = (
        Organization.objects
        .filter(id__in=org_ids)
        .annotate(technics_count=Count("technics", distinct=True))  # related_name bo‘lmasa: "technics_set"
        .only("id", "name")
    )

    logs = (
        LogEntry.objects
        .select_related("user", "content_type")
        .order_by("-action_time")[:10]
    )

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
    deed_receiver = (
        Deed.objects
        .filter(Q(receiver=employee) | Q(sender=employee))
        .select_related("sender", "receiver")
        .order_by("-id")
    )
    context = {
        "deed_receiver": deed_receiver,
    }
    return render(request, "main/contact.html", context)


@never_cache
@login_required
def contact_agrement(request):
    employee = getattr(request.user, "employee", None)

    deed_consent = (
        Deed.objects
        .filter(deedconsent__employee=employee)
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
def contact_user(request):
    employee = getattr(request.user, "employee", None)
    deed_sender = (
        Deed.objects
        .filter(user=employee)
        .select_related("sender", "receiver")
        .order_by("-id")
    )
    senders = (
        Employee.objects.filter(rol__boss=True)
        .select_related("user", "rank", "organization", "department", "directorate", "division")
        .order_by("last_name", "first_name", "father_name")
    )
    context = {
        "deed_sender": deed_sender,
        "senders": senders,
        "organization": Organization.objects.all(),
    }
    return render(request, "main/contact_user.html", context)


def deed_status(request, pk):
    deed = get_object_or_404(Deed, pk=pk)
    context = {"d": deed}
    return render(request, "main/deed_status.html", context)


@never_cache
@login_required
@transaction.atomic
def deed_post(request):
    if request.method != "POST":
        return redirect("contact")

    employee = getattr(request.user, "employee", None)
    back_url = request.META.get("HTTP_REFERER", "/")

    sender_id = (request.POST.get("sender_id") or "").strip()      # xizmat ko'rsatuvchi vakil (majbur)
    receiver_id = (request.POST.get("receiver_id") or "").strip()  # imzolovchi org vakil (ixtiyoriy)
    message = request.POST.get("message", "").strip()
    agreements = request.POST.getlist("agreements[]")

    # ✅ Sender majburiy
    if not sender_id:
        messages.info(request, "Xizmat ko'rsatuvchi tashkilot vakili tanlang")
        return redirect(back_url)
    sender = get_object_or_404(Employee.objects.select_related("user"), id=sender_id)

    # ✅ Receiver ixtiyoriy
    receiver = None
    if receiver_id:
        receiver = get_object_or_404(Employee.objects.select_related("user"), id=receiver_id)

    upload_file = request.FILES.get("file")
    if not upload_file:
        messages.info(request, "Fayl yuklanmadi")
        return redirect(back_url)

    ext = os.path.splitext(upload_file.name)[1].lower()
    if ext not in [".docx", ".pdf"]:
        messages.info(request, "❌ Faqat Word (DOCX) yoki PDF fayl yuklash mumkin")
        return redirect(back_url)

    upload_file.name = f"deed_{uuid.uuid4().hex}{ext}"

    # ✅ Statuslar
    status_sender = "viewed"                      # sender majbur
    status_receiver = "viewed" if receiver else "not_required"  # receiver bo'lmasa 1ta QR

    deed = Deed.objects.create(
        user=employee,
        sender=sender,
        receiver=receiver,
        file=upload_file,
        message_user=message,
        status_sender=status_sender,
        status_receiver=status_receiver,
    )

    file_path = deed.file.path

    # DOCX => PDF
    if ext == ".docx":
        pdf_path, debug = convert_docx_to_pdf_libre(file_path)
        if not pdf_path or not os.path.exists(pdf_path):
            messages.info(request, "❌ DOCX → PDF konvertatsiya xatosi")
            raise Exception(f"DOCX->PDF failed: {debug}")

        try:
            os.remove(file_path)
        except Exception:
            pass

        with open(pdf_path, "rb") as f:
            deed.file.save(os.path.basename(pdf_path), File(f), save=True)

        try:
            os.remove(pdf_path)
        except Exception:
            pass

    # agreements[] -> ids
    ids = []
    for x in agreements:
        x = (x or "").strip()
        if x.isdigit():
            ids.append(int(x))
    ids = list(set(ids))

    # ✅ Exclude: sender va receiver (receiver bo'lmasa qo'shilmaydi)
    exclude_ids = set()
    exclude_ids.add(sender.id)
    if receiver:
        exclude_ids.add(receiver.id)

    ids = [i for i in ids if i not in exclude_ids]

    if ids:
        emps = Employee.objects.filter(id__in=ids).only("id")
        objs = [DeedConsent(deed=deed, employee=e, status="viewed") for e in emps]
        DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

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


@never_cache
@login_required
@transaction.atomic
def deed_update(request, pk):
    if request.method != "POST":
        return redirect(request.META.get("HTTP_REFERER", "/"))

    emp = getattr(request.user, "employee", None)
    if not emp:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")

    deed = get_object_or_404(
        Deed.objects.select_related("user", "sender", "receiver"),
        pk=pk
    )
    if getattr(deed, "user_id", None) != emp.id:
        raise PermissionDenied("Siz bu xabarni tahrirlay olmaysiz")

    sender_id = (request.POST.get("sender_id") or "").strip()
    receiver_id = (request.POST.get("receiver_id") or "").strip()
    agreements_ids = request.POST.getlist("agreements[]")
    message = (request.POST.get("message") or "").strip()
    upload_file = request.FILES.get("file")  # ixtiyoriy qilsak ham bo‘ladi

    if sender_id:
        deed.sender = get_object_or_404(Employee, pk=sender_id)
    if receiver_id:
        deed.receiver = get_object_or_404(Employee, pk=receiver_id)
    # message update
    if hasattr(deed, "message_user"):
        deed.message_user = message
    deed.date_edit = timezone.now()
    if upload_file:
        ext = os.path.splitext(upload_file.name)[1].lower()
        if ext not in [".docx", ".pdf"]:
            messages.info(request, "❌ Faqat Word (DOCX) yoki PDF fayl yuklash mumkin")
            return redirect(back_url)

        old_path = deed.file.path if deed.file else None

        if ext == ".pdf":
            deed.file = upload_file
            deed.save()
        else:
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                for chunk in upload_file.chunks():
                    tmp.write(chunk)
                tmp_docx_path = tmp.name

            pdf_path = None
            try:
                pdf_path, debug = convert_docx_to_pdf_libre(tmp_docx_path)
                if not pdf_path or not os.path.exists(pdf_path):
                    messages.info(request, "❌ DOCX → PDF konvertatsiya xatosi")
                    raise Exception(f"DOCX->PDF failed: {debug}")

                with open(pdf_path, "rb") as f:
                    deed.file.save(os.path.basename(pdf_path), File(f), save=True)

            finally:
                try:
                    os.remove(tmp_docx_path)
                except Exception:
                    pass
                if pdf_path:
                    try:
                        os.remove(pdf_path)
                    except Exception:
                        pass

        if old_path and os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass

    exclude_ids = set(
        DeedConsent.objects.filter(deed=deed).values_list("employee_id", flat=True)
    )
    if deed.sender_id:
        exclude_ids.add(deed.sender_id)
    if deed.receiver_id:
        exclude_ids.add(deed.receiver_id)

    clean_ids = []
    for x in agreements_ids:
        x = (x or "").strip()
        if x.isdigit():
            clean_ids.append(int(x))
    clean_ids = list(dict.fromkeys(clean_ids))

    new_ids = [eid for eid in clean_ids if eid not in exclude_ids]

    if new_ids:
        qs = Employee.objects.filter(id__in=new_ids)
        bulk = [DeedConsent(deed=deed, employee=e) for e in qs]
        DeedConsent.objects.bulk_create(bulk)

    deed.save()
    messages.success(request, "Xabar yangilandi")
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
    try:
        try:
            body = json.loads(request.body or "{}")
        except Exception:
            return JsonResponse({"status": "error", "message": "JSON noto‘g‘ri", "redirect": "/"}, status=400)

        code = body.get("code")
        code_verifier = body.get("codeVerifier")
        redirect_uri = body.get("redirectUri")
        if not code or not code_verifier or not redirect_uri:
            return JsonResponse({"status": "error", "message": "SSO parametrlari to‘liq emas", "redirect": "/"}, status=400)

        pending = request.session.get("PENDING_APPROVE")
        if not pending:
            raise PermissionDenied("Pending yo‘q")

        role = pending.get("role")
        message = (pending.get("message") or "").strip()
        redirect_url = pending.get("redirect_url") or "/"

        employee = getattr(request.user, "employee", None)
        if not employee:
            request.session.pop("PENDING_APPROVE", None)
            return JsonResponse({"status": "forbidden", "message": "Employee yo‘q", "redirect": redirect_url}, status=403)

        # token olish
        token_data = exchange_code_for_token(code, code_verifier, redirect_uri)
        id_token = token_data.get("id_token")
        if not id_token:
            raise PermissionDenied("id_token yo‘q")

        user_data = decode_jwt(id_token) or {}
        sso_pinfl = user_data.get("pinfl")
        employee_pinfl = getattr(employee, "pinfl", None)

        if not employee_pinfl or not sso_pinfl or employee_pinfl != sso_pinfl:
            request.session.pop("PENDING_APPROVE", None)
            return JsonResponse({"status": "forbidden", "message": "PINFL mos emas", "redirect": redirect_url}, status=403)

        # ✅ sender/receiver: AUTO QR + APPROVE
        if role in ("sender", "receiver"):
            deed_id = pending.get("deed_id")
            if not deed_id:
                raise PermissionDenied("Deed yo‘q")

            deed = get_object_or_404(Deed.objects.select_related("sender", "receiver"), pk=int(deed_id))

            # ruxsat tekshiruv
            if role == "sender" and deed.sender_id != employee.id:
                raise PermissionDenied("Sender emassiz")
            if role == "receiver" and deed.receiver_id != employee.id:
                raise PermissionDenied("Receiver emassiz")

            # qayta bosishdan himoya
            if role == "sender" and deed.status_sender == "approved":
                request.session.pop("PENDING_APPROVE", None)
                return JsonResponse({"status": "ok", "redirect": redirect_url})

            if role == "receiver" and deed.status_receiver == "approved":
                request.session.pop("PENDING_APPROVE", None)
                return JsonResponse({"status": "ok", "redirect": redirect_url})

            if not deed.file:
                raise PermissionDenied("PDF yo‘q")

            pdf_path = deed.file.path
            approver_name = employee.full_name

            # PDF sign + DB update (atomik)
            with transaction.atomic():
                sign_pdf_inplace(pdf_path=pdf_path, request=request, approver_name=approver_name,deed_id=deed.pk,)

                now = timezone.now()
                if role == "sender":
                    Deed.objects.filter(pk=deed.pk).update(
                        status_sender="approved",
                        message_sender=message or "",
                        date_edit=now,
                    )
                else:
                    Deed.objects.filter(pk=deed.pk).update(
                        status_receiver="approved",
                        message_receiver=message or "",
                        date_edit=now,
                    )

            request.session.pop("PENDING_APPROVE", None)
            request.session.modified = True
            return JsonResponse({"status": "ok", "redirect": redirect_url})

        # ✅ consent bo‘lsa avvalgidek
        if role == "consent":
            consent_id = pending.get("consent_id")
            if not consent_id:
                raise PermissionDenied("consent_id yo‘q")

            consent = get_object_or_404(DeedConsent.objects.select_related("employee__user"), pk=int(consent_id))
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
    except TimeoutError:
        return JsonResponse({"status": "error", "message": "PDF band, qayta urinib ko‘ring", "redirect": "/"}, status=409)
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

    r = requests.post(
        settings.SSO_TOKEN_URL,
        data=data,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=10,
    )

    if r.status_code != 200:
        raise PermissionDenied(f"SSO token olinmadi: {r.text}")

    return r.json()


@never_cache
@login_required
@require_POST
def deedconsent_action(request, pk):
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
    if not role or not role.technics:
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
    if not role or not role.technics:
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
    if not role or not role.technics_edit:   # faqat omborchi o‘chirishi mumkin
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
    if not role or not role.technics_edit:  # faqat omborchi o‘chirishi mumkin
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
    if not role or not role.technics_edit:  # faqat omborchi o‘chirishi mumkin
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
    if not role or not role.material:
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
    if not role or not role.material:  # faqat omborchi o‘chirishi mumkin
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
    if not role or not role.material_edit:  # faqat omborchi o‘chirishi mumkin
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
    if not role or not role.material_edit:  # faqat omborchi o‘chirishi mumkin
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
    if not role or not role.material_edit:  # faqat omborchi o‘chirishi mumkin
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

    tech_prefetch = Prefetch(
        "technics_set",
        queryset=(
            Technics.objects
            .select_related("category")
            .only("id", "name", "serial", "inventory", "year", "category__id", "category__name")
        ),
        to_attr="tech_list"
    )

    # 🔷 ORG
    org = get_object_or_404(
        Organization.objects
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
        ),
        slug=slug
    )

    # 🟡 DEPARTMENTS (pagination qilinadigan qism)
    departments_qs = (
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
        .order_by("id")  # ✅ barqaror pagination
    )

    page_number = request.GET.get("page", 1)
    paginator = Paginator(departments_qs, 1)  # xohlasangiz 10/20 qiling
    page_obj = paginator.get_page(page_number)

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
        "organization": org,          # nomini ham to'g'rilab qo'ydim (organizations emas)
        "departments": page_obj,      # ✅ template’da for loop: departments
        "page_obj": page_obj,         # ✅ pagination blok ishlashi uchun
        "paginator": paginator,
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
        "organizations": Organization.objects.only("id", "name", "slug").order_by("name"),
        "emp_bos": Employee.objects.filter(id__in=[3470,3469,3468,1]),
    }
    return render(request, "main/document.html", context)


@never_cache
@login_required
@require_POST
def document_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    org_id = (request.POST.get("organization") or "").strip()
    dep_id = (request.POST.get("department") or "").strip()

    sender_id = (request.POST.get("sender") or "").strip() or None
    receiver_id = (request.POST.get("receiver") or "").strip() or None  # agar formda bo'lsa
    message = (request.POST.get("message") or "").strip() or None

    # ✅ agreements list
    agreements = request.POST.getlist("agreements[]")  # <select name="agreements[]">

    org = Organization.objects.filter(id=org_id).first() if org_id else None
    dep = Department.objects.filter(id=dep_id).first() if dep_id else None
    if not dep:
        return HttpResponse("Department topilmadi!", status=404)

    sender = Employee.objects.filter(id=sender_id).first() if sender_id else None
    receiver = Employee.objects.filter(id=receiver_id).first() if receiver_id else None

    # === TEXNIKA QS ===
    komp_names = ["Kompyuter", "Planshet", "Noutbook", "Doska"]
    prin_names = ["A4 Printer", "Printer", "scaner"]

    # ✅ Technics modelingizga mos (department bor)
    base_qs = (
        Technics.objects.filter(department_id=dep_id)
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

    texnikalar_matni = ""
    if komp_count > 0:
        texnikalar_matni += f"1.1. Biriktirilgan kompyuterlarga xizmat ko‘rsatish – {komp_count} dona.\n"
    if prin_count > 0:
        texnikalar_matni += f"1.2. Printerlarga xizmat ko‘rsatish – {prin_count} dona.\n"
    if not texnikalar_matni:
        texnikalar_matni = "Texnikalar mavjud emas."

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
        "DEPARTMENT": dep.name or "",
        "FIO": employee.full_name or "",
        "DATA": date.today().strftime("%d.%m.%Y"),
        "CONTRACT": getattr(org, "contract", "") or "",
        "RIM": (request.POST.get("rim_id") or "1"),      # formdan olsa bo'ladi
        "TEXNIKALAR": texnikalar_matni,
    }

    bold_keys = {"FIO", "DATA"}

    # ⚠️ Sizdagi usul run-split bo'lsa ba'zan ishlamaydi, lekin hozircha qoldiryapman.
    # (xohlasangiz keyin 100% replace funksiyasini qo'yib beraman)
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

    # === DOCX -> PDF ===
    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = os.path.join(tmpdir, "dalolatnoma.docx")
        doc.save(docx_path)

        pdf_path, debug = convert_docx_to_pdf_libre(docx_path)
        if not pdf_path:
            return HttpResponse("DOCX -> PDF convert xato!\n\n" + (debug or ""), content_type="text/plain", status=500)

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

    # === Deed yaratish ===
    deed = Deed.objects.create(
        sender=sender,
        receiver=receiver,        # ✅ receiver alohida
        user=employee,
        message_user=message,
    )
    deed.file.save("dalolatnoma.pdf", ContentFile(pdf_bytes), save=True)

    # === agreements tozalash ===
    ids = []
    for x in agreements:
        x = (x or "").strip()
        if x.isdigit():
            ids.append(int(x))
    ids = list(set(ids))

    # sender, receiver, user(employee) ni exclude qilish
    exclude_ids = set()
    if sender:
        exclude_ids.add(sender.id)
    if receiver:
        exclude_ids.add(receiver.id)
    exclude_ids.add(employee.id)

    ids = [i for i in ids if i not in exclude_ids]

    if ids:
        emps = Employee.objects.filter(id__in=ids).only("id")
        objs = [DeedConsent(deed=deed, employee=e, status="viewed") for e in emps]
        DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

    messages.success(request, "Dalolatnoma yuborildi")
    return redirect("contact_user")


# yangi arizalar
@never_cache
@login_required
def order_sender(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    orders_qs = (
        Order.objects
        .filter(sender=employee,status__in=["viewed", "accepted", "finished"],)
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
    return render(request, "main/order_sender.html", context)


# arizani tasdiqlash yoki bekor qilish
@never_cache
@login_required
@require_POST
def order_decide(request, pk):
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
        raise PermissionDenied

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
@login_required
@require_POST
def order_post(request):
    employee = getattr(request.user, "employee", None)
    back_url = request.META.get("HTTP_REFERER", "/")

    if not employee:
        raise PermissionDenied

    goal_id = (request.POST.get("goal") or "").strip()
    body = (request.POST.get("body") or "").strip()

    if not goal_id.isdigit():
        messages.error(request, "Ariza turi tanlanmadi yoki noto‘g‘ri.")
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
@login_required
@require_POST
def order_accepted(request, pk):
    employee = getattr(request.user, "employee", None)
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
def order_receiver_activ(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    orders_qs = (
        Order.objects
        .filter(sender__region=employee.region,status__in=["accepted", "finished"],)
        .select_related("goal", "technics", "receiver", "sender")
        .order_by("-id")
    )
    technics = Technics.objects.all()
    materials = Material.objects.all()

    # ✅ PAGINATION
    page_number = request.GET.get("page", 1)
    paginator = Paginator(orders_qs, 50)   # har sahifada 4 ta
    page_obj = paginator.get_page(page_number)

    context = {
        "order": page_obj,          # ✅ for loop shu orqali yuradi
        "page_obj": page_obj,       # ✅ pagination uchun
        "paginator": paginator,     # ✅ pagination uchun
        'technics': technics,
        'materials': materials,
    }
    return render(request, "main/order_receiver_activ.html", context)


@never_cache
@login_required
def order_receiver_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    orders_qs = (
        Order.objects
        .filter(sender__region=employee.region,status__in=["approved", "rejected",],)
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
@login_required
@require_POST
@transaction.atomic
def ordermaterial_post(request):
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
def akt_get(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    context = {
        "organizations": Organization.objects.all(),
    }
    return render(request, "main/akt.html", context)


@never_cache
@login_required
@require_POST
def akt_post(request):
    if request.method != "POST":
        return redirect("akt_get")

    employee = getattr(request.user, "employee", None)
    org_id = request.POST.get("organization") or None
    dep_id = request.POST.get("department") or None
    sender_id = request.POST.get("sender") or None
    message = request.POST.get("message", "").strip() or None
    agreements = request.POST.getlist("agreements[]")

    date_id1 = request.POST.get("date1")
    date_id2 = request.POST.get("date2")

    # Sana parse
    date1 = timezone.make_aware(datetime.strptime(date_id1, "%Y-%m-%d"))
    date2 = timezone.make_aware(datetime.strptime(date_id2, "%Y-%m-%d") + timedelta(days=1))

    qs = OrderMaterial.objects.filter(
        order__date_finished__gte=date1,
        order__date_finished__lt=date2,
        order__sender__department_id=dep_id,
        order__receiver__region=request.user.employee.region,
    )

    org = Organization.objects.filter(id=org_id).first() if org_id else None
    dep = Department.objects.filter(id=dep_id).first() if dep_id else None
    sender = Employee.objects.filter(id=sender_id).first() if sender_id else None

    doc = Document(os.path.join(settings.MEDIA_ROOT, "document", "akt.docx"))

    ORG_TEXT = {
        4: "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi Axborot texnologiyalar markazining vakillari:",
        1: "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi tashkiloti vakillari:",
        2: "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi G'aznachilik qo'mitasi vakillari:",
        3: "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi Budjetdan tashqari pensiya jamg'armasi vakillari:",
    }
    org_name = ORG_TEXT.get(org.id, "") if org else ""

    replace_text(doc, {
        "ORGANIZATION": org_name,
        "SANA": date.today().strftime("%d.%m.%Y"),
        "RECEIVER": str(employee),
        "SENDER": sender.full_name if sender else "",
        "DEPARTMENT": dep.name if dep else "",
        "CONTRACT": str(org.contract) if org else "",
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
        "So'rovnoma №",
        "Materiallarni O'rnatish sanasi",
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
            q.order.id if q.id else "",
            q.order.date_creat.strftime("%d.%m.%Y") if q.order and q.order.date_creat else "",
        ])

    h, table = create_table_akt_all(
        doc,
        "Biriktirilgan texnika bo‘yicha dalolatnoma",
        rows,
        headers
    )

    target._p.addnext(h._p)
    h._p.addnext(table._tbl)

    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = os.path.join(tmpdir, "order.docx")
        doc.save(docx_path)

        pdf_path, debug = convert_docx_to_pdf_libre(docx_path)
        if not pdf_path:
            return HttpResponse(
                "DOCX -> PDF convert xato!\n\n" + debug,
                content_type="text/plain",
                status=500
            )

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

    deed = Deed.objects.create(
        sender=sender,  # ✅ obyekt
        user=employee,
        message_user=message,
    )
    # ✅ FileField ga saqlash
    deed.file.save("akt.pdf", ContentFile(pdf_bytes), save=True)

    # ✅ agreements id larini tozalash
    agreements = agreements or []  # ✅ ekstra xavfsizlik

    ids = []
    for x in agreements:
        x = (x or "").strip()
        if x.isdigit():
            ids.append(int(x))
    ids = list(set(ids))

    # ✅ sender va receiver(employee) ni exclude qilish
    exclude_ids = set()
    if sender:
        exclude_ids.add(sender.id)
    exclude_ids.add(employee.id)

    ids = [i for i in ids if i not in exclude_ids]

    if ids:
        emps = Employee.objects.filter(id__in=ids).only("id")
        objs = [DeedConsent(deed=deed, employee=e, status="viewed") for e in emps]
        DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

    messages.success(request, "Ariza yuborildi")
    return redirect("contact_user")


@never_cache
@login_required
def svod_get(request):

    if not hasattr(request.user, "employee"):
        raise PermissionDenied

    if request.user.employee.rol.client:
        raise PermissionDenied

    context = {
        "organizations": Organization.objects.all().order_by("id"),
        "emp_bos": Employee.objects.filter(id__in=[3470, 3469, 3468]).select_related("rank"),
        "employee": Employee.objects.filter(organization_id=4).select_related("rank"),
    }
    return render(request, 'main/svod.html', context)


from collections import OrderedDict
@never_cache
@login_required
def svod_post(request):
    if request.method != "POST":
        return redirect("document_get")

    employee = getattr(request.user, "employee", None)
    org_id = request.POST.get("organization") or None
    sender_id = request.POST.get("sender") or None
    message = request.POST.get("message", "").strip() or None
    agreements = request.POST.getlist("agreements[]")

    date_id1 = request.POST.get("date1")
    date_id2 = request.POST.get("date2")

    date1 = timezone.make_aware(datetime.strptime(date_id1, "%Y-%m-%d"))
    date2 = timezone.make_aware(datetime.strptime(date_id2, "%Y-%m-%d") + timedelta(days=1))

    qs = OrderMaterial.objects.filter(
        order__date_finished__gte=date1,
        order__date_finished__lt=date2,
        order__sender__organization_id=org_id,
        order__receiver__region=request.user.employee.region,
    )

    org = Organization.objects.filter(id=org_id).first() if org_id else None
    sender = Employee.objects.filter(id=sender_id).first() if sender_id else None
    doc = Document(os.path.join(settings.MEDIA_ROOT, "document", "svod.docx"))

    ORG_TEXT = {
        4: "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi Axborot texnologiyalar markazining vakillari:",
        1: "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi tashkiloti vakillari:",
        2: "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi G'aznachilik qo'mitasi vakillari:",
        3: "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi Budjetdan tashqari pensiya jamg'armasi vakillari:",
    }
    org_name = ORG_TEXT.get(org.id, "") if org else ""

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

    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = os.path.join(tmpdir, "order.docx")
        doc.save(docx_path)

        pdf_path, debug = convert_docx_to_pdf_libre(docx_path)
        if not pdf_path:
            return HttpResponse(
                "DOCX -> PDF convert xato!\n\n" + debug,
                content_type="text/plain",
                status=500
            )

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

    deed = Deed.objects.create(
        sender=sender,  # ✅ obyekt
        user=employee,
        message_user=message,
    )
    # ✅ FileField ga saqlash
    deed.file.save("akt.pdf", ContentFile(pdf_bytes), save=True)

    # ✅ agreements id larini tozalash
    agreements = agreements or []  # ✅ ekstra xavfsizlik

    ids = []
    for x in agreements:
        x = (x or "").strip()
        if x.isdigit():
            ids.append(int(x))
    ids = list(set(ids))

    # ✅ sender va receiver(employee) ni exclude qilish
    exclude_ids = set()
    if sender:
        exclude_ids.add(sender.id)
    exclude_ids.add(employee.id)

    ids = [i for i in ids if i not in exclude_ids]

    if ids:
        emps = Employee.objects.filter(id__in=ids).only("id")
        objs = [DeedConsent(deed=deed, employee=e, status="viewed") for e in emps]
        DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

    messages.success(request, "Ariza yuborildi")
    return redirect("contact_user")


@never_cache
@login_required
def reestr_get(request):

    if not hasattr(request.user, "employee"):
        raise PermissionDenied

    if request.user.employee.rol.client:
        raise PermissionDenied

    context = {
        'organizations': Organization.objects.all(),
        "emp_bos": Employee.objects.filter(id__in=[3470, 3469, 3468]),
        "employee": Employee.objects.filter(id=4),
    }
    return render(request, 'main/reestr.html', context)


@never_cache
@login_required
def reestr_post(request):
    if request.method != "POST":
        return redirect("document_get")

    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    # formdan keladiganlar
    org_id = request.POST.get("organization") or None
    date_id1 = request.POST.get("date1") or ""
    date_id2 = request.POST.get("date2") or ""

    # agar siz deed yaratishda ishlatsangiz (sizning oldingi akt_post uslubingizga mos)
    sender_id = request.POST.get("sender") or None
    message = (request.POST.get("message") or "").strip() or None
    agreements = request.POST.getlist("agreements[]")  # select2 bo'lsa

    if not org_id or not date_id1 or not date_id2:
        return HttpResponse("organization/date1/date2 shart", status=400)

    # sana parse
    try:
        date1 = timezone.make_aware(datetime.strptime(date_id1, "%Y-%m-%d"))
        date2 = timezone.make_aware(datetime.strptime(date_id2, "%Y-%m-%d") + timedelta(days=1))
    except ValueError:
        return HttpResponse("Sana formati noto'g'ri (YYYY-MM-DD)", status=400)

    org = Organization.objects.filter(id=org_id).first()

    # ✅ N+1 oldini olish
    qs = (
        OrderMaterial.objects.filter(
            order__date_finished__gte=date1,
            order__date_finished__lt=date2,
            order__sender__organization_id=org_id,
            order__receiver__region=employee.region,
        )
        .select_related(
            "order",
            "order__technics",
            "order__sender",
            "order__sender__rank",
            "order__sender__department",
            "order__receiver",
            "material",
        )
    )

    # ✅ rows va grand_total
    rows = []
    grand_total = Decimal("0")

    for q in qs:
        technics = q.order.technics if (q.order and q.order.technics) else None
        material = q.material

        # xavfsiz Decimal
        price = Decimal(str(material.price)) if (material and material.price is not None) else Decimal("0")
        number = Decimal(str(q.number)) if q.number is not None else Decimal("0")
        total = price * number
        grand_total += total

        sender_emp = q.order.sender if q.order else None
        receiver_emp = q.order.receiver if q.order else None

        rows.append([
            technics.name if technics else "",
            technics.serial if technics else "",
            material.name if material else "",
            str(number),                    # soni
            str(price),                     # birlik narx
            str(total),                     # umumiy
            (sender_emp.full_name if sender_emp else ""),
            (sender_emp.rank.name if (sender_emp and sender_emp.rank) else ""),
            (sender_emp.department.name if (sender_emp and sender_emp.department) else ""),
            (receiver_emp.full_name if receiver_emp else ""),
            (q.order.date_creat.strftime("%d.%m.%Y") if (q.order and q.order.date_creat) else ""),
            (str(q.order.id) if q.order else ""),
            (q.order.date_finished.strftime("%d.%m.%Y") if (q.order and q.order.date_finished) else ""),
            (material.code if (material and material.code) else ""),
        ])

    # ✅ DOCX template
    template_path = os.path.join(settings.MEDIA_ROOT, "document", "reestr.docx")
    if not os.path.exists(template_path):
        return HttpResponse(f"Template topilmadi: {template_path}", status=500)

    doc = Document(template_path)

    ORG_TEXT = {
        "IVS": "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi Axborot texnologiyalar markazini",
        "IMV": "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi",
        "GAZNA": "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi G'aznachilik qo'mitasi",
        "PENSIYA": "O'zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi Budjetdan tashqari pensiya jamg'armasi",
    }
    org_name = ORG_TEXT.get(getattr(org, "org_type", None), "")

    replace_text(doc, {
        "ORGANIZATION": org_name,
        "XUDUD": employee.region.name if employee.region else "",
    })

    # TABLE placeholder paragrafini topamiz
    target = next((p for p in doc.paragraphs if "TABLE" in p.text), None)
    if not target:
        return HttpResponse("DOCX ichidan TABLE placeholder topilmadi", status=500)

    # TABLE paragrafini tozalash
    target.text = ""
    target.paragraph_format.space_before = Pt(0)
    target.paragraph_format.space_after = Pt(0)
    target.paragraph_format.line_spacing = 1

    # ✅ jadval yaratish + qo'shish
    table = create_table_cols_reestr(doc, rows, grand_total=grand_total)
    target._p.addnext(table._tbl)

    # ✅ docx -> pdf
    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = os.path.join(tmpdir, "reestr.docx")
        doc.save(docx_path)

        pdf_path, debug = convert_docx_to_pdf_libre(docx_path)
        if not pdf_path:
            return HttpResponse(
                "DOCX -> PDF convert xato!\n\n" + (debug or ""),
                content_type="text/plain",
                status=500
            )

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

    # ✅ sender aniqlash (bo'lmasa employee)
    sender = Employee.objects.filter(id=sender_id).first() if sender_id else None
    if not sender:
        sender = employee

    # ✅ Deed yaratish va PDF saqlash
    deed = Deed.objects.create(
        sender=sender,
        user=employee,
        message_user=message,
    )
    deed.file.save("reestr.pdf", ContentFile(pdf_bytes), save=True)

    # ✅ agreements larni tozalash
    agreements = agreements or []
    ids = []
    for x in agreements:
        x = (x or "").strip()
        if x.isdigit():
            ids.append(int(x))
    ids = list(set(ids))

    # sender va employee ni consentdan chiqaramiz
    exclude_ids = {employee.id}
    if sender:
        exclude_ids.add(sender.id)
    ids = [i for i in ids if i not in exclude_ids]

    if ids:
        emps = Employee.objects.filter(id__in=ids).only("id")
        objs = [DeedConsent(deed=deed, employee=e, status="viewed") for e in emps]
        DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

    messages.success(request, "Reestr yuborildi")
    return redirect("contact_user")


@never_cache
@login_required
def technics_get(request):
    if not hasattr(request.user, "employee"):
        raise PermissionDenied

    employee = getattr(request.user, "employee", None)
    technics = Technics.objects.filter(employee=employee)

    context = {
        'technics': technics,
    }
    return render(request, 'main/technics_get.html', context)
