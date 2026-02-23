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
from .html_pdf import *
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
from .models import *
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
import secrets
from django.conf import settings
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
    role = getattr(employee, "rol", None)
    if role and role.client:
        raise PermissionDenied

    deed_user = (
        Deed.objects
        .filter(user=employee)
        .select_related("sender", "receiver")
        .order_by("-id")
    )
    context = {
        "deed_user": deed_user,
    }
    return render(request, "main/contact_user.html", context)


def deed_status(request, pk):
    deed = get_object_or_404(Deed, pk=pk)
    context = {"d": deed}
    return render(request, "main/deed_status.html", context)


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


        request.session["PENDING_APPROVE"] = {
            "deed_id": deed.id,
            "role": role,          # sender/receiver
            "message": message,
            "redirect_url": back_url,
        }
        request.session.modified = True
        return redirect("sso_start_page")

    messages.error(request, "Noto‘g‘ri amal")
    return redirect(back_url)



@never_cache
@login_required
def deed_edit(request, pk):
    emp_me = getattr(request.user, "employee", None)
    if not emp_me:
        raise PermissionDenied

    role = getattr(emp_me, "rol", None)
    if role and role.client:
        raise PermissionDenied

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
        # ---------------- JSON ----------------
        try:
            body = json.loads(request.body or "{}")
        except Exception:
            return JsonResponse(
                {"status": "error", "message": "JSON noto‘g‘ri", "redirect": "/"},
                status=400
            )

        code = body.get("code")
        code_verifier = body.get("codeVerifier")
        redirect_uri = body.get("redirectUri")
        if not code or not code_verifier or not redirect_uri:
            return JsonResponse(
                {"status": "error", "message": "SSO parametrlari to'liq emas", "redirect": "/"},
                status=400
            )

        # ------------- session pending ----------
        pending = request.session.get("PENDING_APPROVE")
        if not pending:
            raise PermissionDenied("Pending yo'q")

        role = pending.get("role")
        message = (pending.get("message") or "").strip()
        redirect_url = pending.get("redirect_url") or "/"

        employee = getattr(request.user, "employee", None)
        if not employee:
            request.session.pop("PENDING_APPROVE", None)
            return JsonResponse(
                {"status": "forbidden", "message": "Employee yo'q", "redirect": redirect_url},
                status=403
            )

        # ---------------- SSO token ----------------
        token_data = exchange_code_for_token(code, code_verifier, redirect_uri)
        id_token = token_data.get("id_token")
        if not id_token:
            raise PermissionDenied("id_token yo'q")

        user_data = decode_jwt(id_token) or {}
        sso_pinfl = user_data.get("pinfl")
        employee_pinfl = getattr(employee, "pinfl", None)

        if not employee_pinfl or not sso_pinfl or employee_pinfl != sso_pinfl:
            request.session.pop("PENDING_APPROVE", None)
            return JsonResponse(
                {"status": "forbidden", "message": "PINFL mos emas", "redirect": redirect_url},
                status=403
            )

        # ==========================================================
        # ✅ sender/receiver: FINAL bo'lganda PDF qayta + QK urish
        # ==========================================================
        if role in ("sender", "receiver"):
            deed_id = pending.get("deed_id")
            if not deed_id:
                raise PermissionDenied("Deed yo'q")

            approver_name = getattr(employee, "full_name", None) or str(employee)

            # Avval transaction ichida faqat DB operatsiyalari
            with transaction.atomic():
                deed = (
                    Deed.objects
                    .select_for_update()
                    .get(pk=int(deed_id))
                )

                # Ruxsat tekshiruv
                if role == "sender" and deed.sender_id != employee.id:
                    raise PermissionDenied("Sender emassiz")
                if role == "receiver" and deed.receiver_id != employee.id:
                    raise PermissionDenied("Receiver emassiz")

                # Status update
                if role == "sender":
                    if deed.status_sender == "approved":
                        request.session.pop("PENDING_APPROVE", None)
                        request.session.modified = True
                        return JsonResponse({"status": "ok", "redirect": redirect_url})

                    deed.status_sender = "approved"
                    deed.message_sender = message or ""
                    deed.date_edit = timezone.now()
                    deed.save(update_fields=["status_sender", "message_sender", "date_edit"])

                else:  # receiver
                    if deed.status_receiver == "approved":
                        request.session.pop("PENDING_APPROVE", None)
                        request.session.modified = True
                        return JsonResponse({"status": "ok", "redirect": redirect_url})

                    deed.status_receiver = "approved"
                    deed.message_receiver = message or ""
                    deed.date_edit = timezone.now()
                    deed.save(update_fields=["status_receiver", "message_receiver", "date_edit"])

                # FINAL shartni tekshirish
                is_final = (
                    (deed.receiver_id is None and deed.status_sender == "approved")
                    or (deed.receiver_id is not None
                        and deed.status_sender == "approved"
                        and deed.status_receiver == "approved")
                )

                deed_pk = deed.pk  # transactiondan tashqarida ishlatamiz

            # Transaction tashqarisida fayl operatsiyasi
            if is_final:
                try:
                    # 🔥 deed-ni qayta chaqiramiz (fresh instance)
                    deed = Deed.objects.get(pk=deed_pk)

                    # ✅ 1) deed.body dan qayta PDF yaratamiz (watermark YO'Q)
                    pdf_bytes = deed_to_pdf_bytes(deed)

                    if deed.file:
                        deed.file.delete(save=False)

                    # ✅ 2) yangi nom bilan deed.file ga saqlaymiz
                    today_str = timezone.now().strftime("%Y%m%d")
                    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
                    random_part = ''.join(secrets.choice(alphabet) for _ in range(6))
                    pdf_name = f"deed/akt_{today_str}_{random_part}.pdf"
                    deed.file.save(pdf_name, ContentFile(pdf_bytes), save=True)

                    # ✅ 3) endi shu faylga QK/QR uramiz
                    sign_pdf_inplace(
                        pdf_path=deed.file.path,
                        request=request,
                        approver_name=approver_name,
                        deed_id=deed.pk,
                    )

                except HtmlPdfError as e:
                    return JsonResponse(
                        {"status": "error", "message": f"PDF yaratilmadi: {e}", "redirect": redirect_url},
                        status=409
                    )
                except TimeoutError as e:
                    return JsonResponse(
                        {"status": "error", "message": str(e), "redirect": redirect_url},
                        status=409
                    )
                except Exception as e:
                    print(f"PDF rebuild/sign error: {e}")
                    return JsonResponse(
                        {"status": "error", "message": "PDF imzolashda xatolik", "redirect": redirect_url},
                        status=500
                    )

            request.session.pop("PENDING_APPROVE", None)
            request.session.modified = True
            return JsonResponse({"status": "ok", "redirect": redirect_url})

        # ==========================================================
        # ✅ consent: avvalgidek
        # ==========================================================
        if role == "consent":
            consent_id = pending.get("consent_id")
            if not consent_id:
                raise PermissionDenied("consent_id yo'q")

            consent = get_object_or_404(
                DeedConsent.objects.select_related("employee__user"),
                pk=int(consent_id)
            )

            if consent.employee.user_id != request.user.id:
                raise PermissionDenied("Ruxsat yo'q")

            if consent.status != "approved":
                consent.status = "approved"
                consent.message = message or ""
                consent.date_edit = timezone.now()
                consent.save(update_fields=["status", "message", "date_edit"])

            request.session.pop("PENDING_APPROVE", None)
            request.session.modified = True
            return JsonResponse({"status": "ok", "redirect": redirect_url})

        raise PermissionDenied("Noto'g'ri pending turi")

    except PermissionDenied as e:
        return JsonResponse(
            {"status": "error", "message": str(e), "redirect": "/"},
            status=403
        )
    except Exception as e:
        print(f"SSO ERROR: {e}")
        return JsonResponse(
            {"status": "error", "message": "SSO xatolik", "redirect": "/"},
            status=500
        )



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

            "total_count": 0,
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
    total_count = qs.count()

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
        "row_start": page_obj.start_index() if total_count else 0,

        "total_count": total_count,
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
            "total_suma": 0,
        })

    qs = (
        Material.objects
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
        "row_start": page_obj.start_index() if total_count else 0,
        "total_count": total_count,
        "total_suma": total_suma,
        "unit": Unit.objects.all()
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
        "emp_bos_sender": Employee.objects.filter(id__in=[3470,3469,3468]),
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

    messages.success(request, "Akt yuborildi (PDF saqlandi)")
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
@login_required
@require_POST
def order_decide(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

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
def order_receiver(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if role and role.client:
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
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if role and role.client:
        raise PermissionDenied

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
def order_receiver_deed(request,pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if role and role.client:
        raise PermissionDenied

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
@login_required
@require_POST
def order_receiver_deed_post(request,pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if role and role.client:
        raise PermissionDenied

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

    messages.success(request, "Akt yuborildi (PDF saqlandi)")
    return redirect("contact_user")


@never_cache
@login_required
def order_receiver_activ(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if role and role.client:
        raise PermissionDenied

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
def order_receiver_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if role and role.client:
        raise PermissionDenied

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
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if role and role.client:
        raise PermissionDenied

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
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if role and role.client:
        raise PermissionDenied

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

    role = getattr(employee, "rol", None)
    if role and not role.shop:
        raise PermissionDenied

    context = {
        "organizations": Organization.objects.all().order_by("id"),
    }
    return render(request, "main/akt.html", context)



@never_cache
@login_required
@require_POST
def akt_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if role and not role.shop:
        raise PermissionDenied

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

    messages.success(request, "Akt yuborildi (PDF saqlandi)")
    return redirect("contact_user")


@never_cache
@login_required
def svod_get(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if role and not role.shop:
        raise PermissionDenied

    context = {
        "organizations": Organization.objects.all().order_by("id"),
        "emp_bos": Employee.objects.filter(id__in=[3470, 3469, 3468]).select_related("rank"),
        "employee": Employee.objects.filter(organization_id=4).select_related("rank"),
    }
    return render(request, 'main/svod.html', context)


@never_cache
@login_required
@require_POST
def svod_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if role and not role.shop:
        raise PermissionDenied

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

    messages.success(request, "Akt yuborildi (PDF saqlandi)")
    return redirect("contact_user")


@never_cache
@login_required
def reestr_get(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if role and not role.shop:
        raise PermissionDenied

    context = {
        "organizations": Organization.objects.all().order_by("id"),
        "emp_bos": Employee.objects.filter(id__in=[3470, 3469, 3468]).select_related("rank"),
        "employee": Employee.objects.filter(organization_id=4).select_related("rank"),
    }
    return render(request, 'main/reestr.html', context)


@never_cache
@login_required
def reestr_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if role and not role.shop:
        raise PermissionDenied

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

    messages.success(request, "Akt yuborildi (PDF saqlandi)")
    return redirect("contact_user")


@never_cache
@login_required
def technics_get(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied

    role = getattr(employee, "rol", None)
    if role and not role.client:
        raise PermissionDenied

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


