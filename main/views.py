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
    employee = request.user.employee
    user = request.user

    emp_form = EmployeeProfileForm(instance=employee)
    email_form = UserEmailForm(instance=user)
    pwd_form = StyledPasswordChangeForm(user=user)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "edit_profile":
            emp_form = EmployeeProfileForm(request.POST, instance=employee)
            email_form = UserEmailForm(request.POST, instance=user)

            if emp_form.is_valid() and email_form.is_valid():
                emp_form.save()
                email_form.save()
                messages.success(request, "Profil muvaffaqiyatli yangilandi")
                return redirect("profil")
            else:
                messages.info(request, "Maydonlarda xatolik bor. Qayta tekshiring")
        elif action == "change_password":
            pwd_form = StyledPasswordChangeForm(user=user, data=request.POST)

            if pwd_form.is_valid():
                pwd_form.save()
                # foydalanuvchi sessiyasi saqlanib qolsin
                update_session_auth_hash(request, pwd_form.user)

                messages.success(request, "Parol muvaffaqiyatli o‘zgartirildi")
                return redirect("profil")
            else:
                messages.info(request, "Parolni o‘zgartirishda xatolik")

        else:
            messages.info(request, "Noto‘g‘ri so‘rov")
            return redirect("profil")
    context = {
        "employee": employee,
        "emp_form": emp_form,
        "email_form": email_form,
        "pwd_form": pwd_form,
    }
    return render(request, "main/profil.html", context)


@never_cache
@login_required
def index(request):
    # 🔒 Employee tekshiruvi
    if not hasattr(request.user, "employee"):
        raise PermissionDenied

    if request.user.employee.status != "worker":
        raise PermissionDenied

    organizations = Organization.objects.filter(
        org_type__in=['IMV', 'PENSIYA', 'GAZNA']
    )
    categorys = Category.objects.all()

    chart_data = []

    for cat in categorys:
        row = {
            "category": cat.name,   # x o‘qi uchun
        }
        for org in organizations:
            count = Technics.objects.filter(
                employee__organization=org,
                category=cat,
            ).count()
            # JS uchun field: org_1, org_2 ...
            row[f"org_{org.id}"] = count
        chart_data.append(row)

    pie_data = []

    for org in organizations:
        total = Technics.objects.filter(
            employee__organization=org
        ).count()

        pie_data.append({
            "name": org.name,
            "count": total
        })
    organizations1 = Organization.objects.filter(org_type__in=['IMV', 'PENSIYA', 'GAZNA']
                                                 ).annotate(
        technics_count=Count('employee__technics', distinct=True)
    )
    logs = LogEntry.objects.select_related('user', 'content_type').order_by('-action_time')[:10]

    context = {
        "logs": logs,
        "organizations1": organizations1,
        "organizations": organizations,
        "categorys": categorys,
        "chart_data": json.dumps(chart_data, cls=DjangoJSONEncoder),
        "pie_data": json.dumps(pie_data, cls=DjangoJSONEncoder),

    }
    return render(request, "main/index.html", context)


@never_cache
@login_required
def contact(request):
    context = {
        'deed_sender': Deed.objects.filter(sender=request.user.employee),
        'deed_receiver': Deed.objects.filter(receiver=request.user.employee),
        "deed_consent": Deed.objects.filter(deedconsent__employee=request.user.employee),
        'employee': Employee.objects
        .select_related("user", "rank","organization","department","directorate","division")
        .exclude(user=request.user)
    }
    return render(request, 'main/contact.html', context)


@never_cache
@login_required
def deed_post(request):
    if request.method != "POST":
        return redirect("contact")

    message = request.POST.get("message", "").strip()
    receiver_id = request.POST.get("receiver_id")
    agreements = request.POST.getlist("agreements[]")

    sender = Employee.objects.filter(user=request.user).first()

    # 🔴 1. AVVAL receiver_id ni tekshiramiz
    if not receiver_id:
        messages.info(request, "Qabul qiluvchi tanlanmadi")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    # 🔴 2. Keyin bazadan qidiramiz
    receiver = Employee.objects.filter(id=receiver_id).first()

    if not sender or not receiver:
        messages.info(request, "Xodimlar noto‘g‘ri tanlandi")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    upload_file = request.FILES.get("file")
    if not upload_file:
        messages.info(request, "Fayl yuklanmadi")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    # faqat DOCX va PDF ruxsat
    ext = os.path.splitext(upload_file.name)[1].lower()
    if ext not in [".docx", ".pdf"]:
        messages.info(request, "❌ Faqat Word (DOCX) yoki PDF fayl yuklash mumkin")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    # =============================
    # 1️⃣ FAYLNI SAQLAYMIZ
    # =============================
    deed = Deed.objects.create(
        sender=sender,
        receiver=receiver,
        message_sender=message,
        file=upload_file,
        status_sender="viewed",
        status_receiver="viewed",
    )

    file_path = deed.file.path

    # =============================
    # 2️⃣ AGAR DOCX BO‘LSA → PDF
    # =============================
    if ext == ".docx":
        pdf_path, debug = convert_docx_to_pdf_libre(file_path)

        if not pdf_path or not os.path.exists(pdf_path):
            print(debug)
            messages.info(request, "❌ DOCX → PDF konvertatsiya xatosi")
            deed.delete()
            return redirect(request.META.get("HTTP_REFERER", "/"))

        # eski DOCX o‘chadi
        try:
            os.remove(file_path)
        except:
            pass

        # PDF ni qayta saqlaymiz
        with open(pdf_path, "rb") as f:
            deed.file.save(os.path.basename(pdf_path), File(f), save=True)

        try:
            os.remove(pdf_path)
        except:
            pass
    # =============================
    # 4️⃣ KELISHUVCHILAR
    # =============================
    objs = []
    for emp_id in agreements:
        emp = Employee.objects.filter(id=emp_id).first()
        if emp:
            objs.append(Deedconsent(
                deed=deed,
                employee=emp,
                status="viewed"
            ))
    Deedconsent.objects.bulk_create(objs)

    messages.success(request, "✅ Dalolatnoma yuborildi")
    return redirect(request.META.get("HTTP_REFERER", "/"))


def deed_action(request, pk):
    deed = get_object_or_404(Deed, pk=pk)
    emp = getattr(request.user, "employee", None)

    if request.method != "POST":
        return redirect(request.META.get("HTTP_REFERER", "/"))

    if not emp:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")
    action = (request.POST.get("action") or "").strip()

    # Kim bosdi? + to'g'ri textarea'dan message olish
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
        if role == "receiver":
            deed.status_receiver = "rejected"
            deed.message_receiver = message
        else:
            deed.status_sender = "rejected"
            deed.message_sender = message
        deed.date_edit = now
        deed.save(update_fields=[
            "status_receiver", "message_receiver",
            "status_sender", "message_sender",
            "date_edit"
        ])
        messages.info(request, "Dalolatnoma rad etildi")
        return redirect(back_url)

    # ✅ Approve → SSO → Viewer
    if action == "approve":
        if not deed.file:
            messages.info(request, "PDF yo‘q")
            return redirect(back_url)

        file_path = deed.file.path

        if not os.path.exists(file_path):
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

        # SSO tugagandan keyin qayerga boramiz? -> PDF viewer
        after_sso_url = reverse("deed_pdf_view", args=[deed.id]) + f"?next={back_url}"

        # SSO callback tugagach qaysi statusni update qilish uchun role+message saqlaymiz
        request.session["PENDING_APPROVE"] = {
            "deed_id": deed.id,
            "role": role,          # sender / receiver
            "message": message,    # shu odam yozgan izoh
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
def sso_exchange_and_finish(request):
    """
    callback.html fetch qilib shu endpointga code+verifier yuboradi.
    Biz esa token olib PINFL tekshiramiz va SSO_OK ni sessionga yozamiz.
    """
    try:
        body = json.loads(request.body or "{}")

        code = body.get("code")
        code_verifier = body.get("codeVerifier")
        redirect_uri = body.get("redirectUri")

        if not code or not code_verifier or not redirect_uri:
            return JsonResponse(
                {"status": "error", "message": "SSO parametrlari to‘liq emas", "redirect": "/"},
                status=400
            )

        token_data = exchange_code_for_token(code, code_verifier, redirect_uri)
        user_data = decode_jwt(token_data["id_token"])

        pending = request.session.get("PENDING_APPROVE")
        if not pending:
            raise PermissionDenied("Pending yo‘q")

        role = pending.get("role")  # sender/receiver/consent
        message = pending.get("message", "")
        redirect_url = pending.get("redirect_url", "/")
        after_sso_url = pending.get("after_sso_url") or redirect_url

        # PINFL tekshiruv
        employee_pinfl = getattr(getattr(request.user, "employee", None), "pinfl", None)
        sso_pinfl = user_data.get("pinfl")

        if not employee_pinfl or employee_pinfl != sso_pinfl:
            request.session.pop("PENDING_APPROVE", None)
            messages.error(request, "SSO kalit egasi va foydalanuvchi mos kelmadi!")
            return JsonResponse(
                {"status": "forbidden", "message": "PINFL mos emas", "redirect": redirect_url},
                status=403
            )

        # Deed approve oqimi (sender/receiver)
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

        # Consent (ixtiyoriy)
        if role == "consent":
            consent = get_object_or_404(Deedconsent, pk=pending["consent_id"])
            if consent.employee.user != request.user:
                raise PermissionDenied("Ruxsat yo‘q")

            if consent.status != "approved":
                consent.status = "approved"
                consent.message = pending.get("message", "")
                consent.save(update_fields=["status", "message", "date_edit"])

            request.session.pop("PENDING_APPROVE", None)
            messages.success(request, "✅ Kelishuv tasdiqlandi")
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
def deedconsent_action(request, pk):
    consent = get_object_or_404(Deedconsent, pk=pk)

    if request.method != "POST":
        return redirect(request.META.get("HTTP_REFERER", "/"))

    if consent.employee.user != request.user:
        messages.info(request, "Sizga ruxsat yo‘q")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    if consent.status != "viewed":
        messages.info(request, "Bu kelishuv allaqachon ko‘rib chiqilgan")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    action = request.POST.get("action")
    message = (request.POST.get("message") or "").strip()
    redirect_url = request.META.get("HTTP_REFERER", "/")

    # ❌ reject — SSO shart emas (xohlasangiz SSO qildirsa ham bo'ladi)
    if action == "reject":
        consent.status = "rejected"
        consent.message = message
        consent.save()
        messages.warning(request, "Rad etildi!")
        return redirect(redirect_url)

    # ✅ approve — SSO orqali (lekin QR qo'ymaydi)
    if action == "approve":
        request.session["PENDING_APPROVE"] = {
            "role": "consent",
            "consent_id": consent.id,
            "message": message,
            "redirect_url": redirect_url,
        }
        request.session.modified = True
        return redirect("sso_start_page")

    messages.error(request, "Noto‘g‘ri amal")
    return redirect(redirect_url)


@never_cache
@login_required
def barn_tex(request):
    status = (request.GET.get("status") or "").strip()
    organization_id = (request.GET.get("organization") or "").strip()
    category_id = (request.GET.get("category") or "").strip()
    name = (request.GET.get("name") or "").strip()
    page_number = request.GET.get("page", 1)

    total_count = Technics.objects.count()

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

    # ✅ nomi bo‘yicha qidiruv
    if name:
        qs = qs.filter(
            Q(name__icontains=name) |
            Q(inventory__icontains=name) |
            Q(serial__icontains=name) |
            Q(year__icontains=name)
        )

    filtered_count = qs.count()

    # ✅ filter bo‘lmasa bo‘sh ko‘rsatish (name ham kiritildi)
    if not (status or organization_id or category_id or name):
        qs = Technics.objects.none()
        filtered_count = 0

    paginator = Paginator(qs, 100)
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)
    qs_params = params.urlencode()

    context = {
        "organizations": Organization.objects.all(),
        "categories": Category.objects.all(),
        "technics_form": TechnicsForm(),

        "page_obj": page_obj,
        "technics": page_obj.object_list,
        "qs_params": qs_params,
        "row_start": page_obj.start_index() if filtered_count else 0,

        "total_count": total_count,
        "filtered_count": filtered_count,
    }
    return render(request, "main/barn_tex.html", context)


@login_required
def technics_create(request):
    form = TechnicsForm(request.POST)

    if form.is_valid():
        form.save()

    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
def technics_delete(request):
    if request.method != "POST":
        return redirect(request.META.get("HTTP_REFERER", "/"))

    tex_id = request.POST.get("texnika_id")
    if not tex_id:
        messages.error(request, "Texnika topilmadi")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    tex = get_object_or_404(Technics, id=tex_id)
    tex.delete()

    messages.success(request, "Texnika o‘chirildi")
    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@transaction.atomic
def technics_attach(request):
    if request.method != "POST":
        return redirect(request.META.get("HTTP_REFERER", "/"))

    tex_id = request.POST.get("texnika_id")
    employee_id = (request.POST.get("employee_id") or "").strip()

    tex = get_object_or_404(Technics, id=tex_id)

    if employee_id:
        # 🔗 Biriktirish
        emp = get_object_or_404(Employee, id=employee_id)
        tex.employee = emp
        tex.status = "active"
        messages.success(request, "Texnika xodimga biriktirildi")
    else:
        # 🔓 Bo‘shatish
        tex.employee = None
        tex.status = "free"
        messages.success(request, "Texnika bo‘shatildi")

    tex.save()
    return redirect(request.META.get("HTTP_REFERER", "/"))



@login_required
@transaction.atomic
def technics_update(request, pk):
    tex = get_object_or_404(Technics, pk=pk)

    if request.method != "POST":
        return redirect(request.META.get("HTTP_REFERER", "/"))

    category_id = (request.POST.get("category") or "").strip()
    organization_id = (request.POST.get("organization") or "").strip()

    if category_id:
        tex.category = get_object_or_404(Category, pk=category_id)
    else:
        tex.category = None

    if organization_id:
        tex.organization = get_object_or_404(Organization, pk=organization_id)
    else:
        tex.organization = None

    tex.name = (request.POST.get("name") or "").strip()
    tex.parametr = (request.POST.get("parametr") or "").strip()
    tex.inventory = (request.POST.get("inventory") or "").strip()
    tex.serial = (request.POST.get("serial") or "").strip()
    tex.mac = (request.POST.get("mac") or "").strip()
    tex.ip = (request.POST.get("ip") or "").strip()
    tex.year = (request.POST.get("year") or "").strip()
    tex.price = request.POST.get("price") or 0
    tex.save()
    messages.success(request, "Texnika tahrirlandi!")
    return redirect(request.META.get("HTTP_REFERER", "/"))

@never_cache
@login_required
def barn_mat(request):
    emp_id = (request.GET.get("employee") or "").strip()
    status = (request.GET.get("status") or "").strip()
    name = (request.GET.get("name") or "").strip()
    page_number = request.GET.get("page", 1)

    total_count = Material.objects.count()

    qs = (
        Material.objects
        .select_related("employee")
        .order_by("-id")
    )

    if status:
        qs = qs.filter(status=status)

    if emp_id:
        qs = qs.filter(employee_id=emp_id)

    if name:
        qs = qs.filter(
            Q(name__icontains=name) |
            Q(code__icontains=name)
        )

    filtered_count = qs.count()

    if not (emp_id or status or name):
        qs = Material.objects.none()
        filtered_count = 0

    paginator = Paginator(qs, 100)
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)
    qs_params = params.urlencode()

    context = {
        "employees_boss": Employee.objects.filter(organization__org_type="IVS", is_boss=True),
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
def material_create(request):
    form = MaterialForm(request.POST)

    if form.is_valid():
        form.save()

    messages.info(request, "Material qo'shildi!")
    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
def material_update(request, pk):
    mat = get_object_or_404(Material, pk=pk)
    if request.method == "POST":
        mat.name = request.POST.get("name", "").strip()
        mat.number = request.POST.get("number") or 0
        mat.price = request.POST.get("price") or 0
        mat.code = request.POST.get("code", "").strip()
        mat.unit = request.POST.get("unit", "").strip()
        mat.save()
        messages.info(request, "Material taxrirlandi!")
    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@transaction.atomic
def material_attach(request):
    if request.method != "POST":
        return redirect(request.META.get("HTTP_REFERER", "/"))

    material_id = request.POST.get("material_id")
    employee_id = request.POST.get("employee_id")
    give_number = request.POST.get("give_number")

    # validatsiya
    try:
        give_number = int(give_number)
    except (TypeError, ValueError):
        messages.info(request, "Soni noto‘g‘ri kiritildi")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    if give_number <= 0:
        messages.info(request, "Soni 1 dan katta bo‘lishi kerak")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    # Ombordagi material (berilayotgan)
    src = get_object_or_404(Material, id=material_id)
    emp = get_object_or_404(Employee, id=employee_id)

    # omborda yetarlimi?
    if (src.number or 0) < give_number:
        messages.info(request, "Omborda yetarli material yo‘q")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    q = Material.objects.filter(employee=emp)

    if src.code:
        q = q.filter(code=src.code)
    else:
        q = q.filter(name=src.name)

    dst = q.first()

    if dst:
        # ✅ bor → ustiga qo‘shamiz
        dst.number = (dst.number or 0) + give_number

        # narx/unit bo‘sh bo‘lsa, src dan to‘ldirib yuborish (ixtiyoriy)
        if not dst.price and src.price:
            dst.price = src.price
        if not dst.unit and src.unit:
            dst.unit = src.unit

        dst.save()
    else:
        # ✅ yo‘q → yaratamiz
        Material.objects.create(
            employee=emp,
            status="active",          # sizdagi status qiymatiga moslang
            name=src.name,
            code=src.code,
            number=give_number,
            unit=src.unit,
            price=src.price,
            year=src.year,
        )

    # ✅ Ombordan ayiramiz
    src.number = (src.number or 0) - give_number
    src.save()

    messages.success(request, "Material biriktirildi")
    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
def material_delete(request):
    if request.method != "POST":
        return redirect(request.META.get("HTTP_REFERER", "/"))

    material_id = request.POST.get("material_id")

    if not material_id:
        messages.info(request, "Material topilmadi")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    mat = get_object_or_404(Material, id=material_id)

    mat.delete()
    messages.success(request, "Material o‘chirildi")

    return redirect(request.META.get("HTTP_REFERER", "/"))


@never_cache
@login_required
def technics(request, slug=None):
    emp = getattr(request.user, "employee", None)
    if not emp or emp.status != "worker":
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

    total_count = Technics.objects.count()

    technics_qs = (
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
        technics_qs = technics_qs.filter(category=category)

    if org_id:
        technics_qs = technics_qs.filter(employee__organization_id=org_id)
    if dep_id:
        technics_qs = technics_qs.filter(employee__department_id=dep_id)
    if dir_id:
        technics_qs = technics_qs.filter(employee__directorate_id=dir_id)
    if div_id:
        technics_qs = technics_qs.filter(employee__division_id=div_id)

    filtered_count = technics_qs.count()

    grouped = defaultdict(list)
    ordered_qs = technics_qs.order_by(
        "employee__last_name",
        "employee__first_name",
        "category__name",
        "name"
    )
    for t in ordered_qs:
        grouped[t.employee].append(t)

    grouped_items = list(grouped.items())
    paginator = Paginator(grouped_items, 100)
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)
    qs_params = params.urlencode()

    context = {
        "category": category,  # xohlasangiz template'da ko'rsatasiz
        "organizations": organizations,

        "page_obj": page_obj,
        "grouped_technics": page_obj.object_list,
        "qs_params": qs_params,

        "total_count": total_count,
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

    # 🔒 Foydalanuvchi Worker bo‘lishi shart
    emp = getattr(request.user, "employee", None)
    if not emp or emp.status != "worker":
        raise PermissionDenied
    # ⚡ Technics ni oldindan yuklab qo‘yamiz
    tech_prefetch = Prefetch(
        "technics_set",
        queryset=Technics.objects.select_related("category"),
        to_attr="tech_list"
    )
    # 🟢 ORGANIZATION (asosiy obyekt)
    organization = (
        Organization.objects
        .annotate(
            technics_count=Count("employee__technics", distinct=True)
        )
        .prefetch_related(
            Prefetch("employee_set", queryset=Employee.objects.prefetch_related(tech_prefetch))
        )
        .get(slug=slug)
    )
    # 🟡 DEPARTMENTS
    departments = (
        Department.objects
        .filter(organization=organization)
        .select_related("organization")
        .annotate(
            technics_count=Count("employee__technics", distinct=True)
        )
        .prefetch_related(
            Prefetch("employee_set",
                     queryset=Employee.objects
                     .select_related("rank", "user")
                     .prefetch_related(tech_prefetch))
        )
    )
    # 🔵 DIRECTORATES
    directorates = (
        Directorate.objects
        .filter(department__organization=organization)
        .select_related("department")
        .annotate(
            technics_count=Count("employee__technics", distinct=True)
        )
        .prefetch_related(
            Prefetch("employee_set",
                     queryset=Employee.objects
                     .select_related("rank", "user")
                     .prefetch_related(tech_prefetch))
        )
    )
    # 🟣 DIVISIONS
    divisions = (
        Division.objects
        .filter(directorate__department__organization=organization)
        .select_related("directorate")
        .annotate(
            technics_count=Count("employee__technics", distinct=True)
        )
        .prefetch_related(
            Prefetch("employee_set",
                     queryset=Employee.objects
                     .select_related("rank", "user")
                     .prefetch_related(tech_prefetch))
        )
    )

    context = {
        'organizations': organization,
        'departments': departments,
        'directorates': directorates,
        'divisions': divisions,
    }
    return render(request, 'main/organization.html', context)


@never_cache
@login_required
def document_get(request):
    # 🔒 Employee tekshiruvi
    if not hasattr(request.user, "employee"):
        raise PermissionDenied

    if request.user.employee.status != "worker":
        raise PermissionDenied
    """GET so‘rovi uchun sahifani ko‘rsatish"""
    context = {
        'organizations': Organization.objects.all(),
        'departments': Department.objects.select_related('organization'),
        'directorate': Directorate.objects.select_related('department'),
        'division': Division.objects.select_related('directorate'),
    }
    return render(request, 'main/document.html', context)


@never_cache
@login_required
def document_post(request):
    """POST so‘rovi uchun dalolatnoma yaratish"""
    oylar = [
        "yanvarda", "fevralda", "martda", "aprelda", "mayda", "iyunda",
        "iyulda", "avgustda", "sentabrda", "oktabrda", "noyabrda", "dekabrda"
    ]

    if request.method != 'POST':
        return redirect('document_get')

    # === FORM MA'LUMOTLARI ===
    org_id = request.POST.get('organization')
    dep_id = request.POST.get('department')
    dir_id = request.POST.get('directorate')
    div_id = request.POST.get('division')
    post_id = request.POST.get('post_id')
    fio_id = request.POST.get('fio_id')
    date_id = request.POST.get('date_id')
    namber_id = request.POST.get('namber_id')
    rim_id = request.POST.get('rim_id')

    # === OBYEKTLARNI OLISH ===
    org = Organization.objects.filter(id=org_id).first() if org_id else None
    dep = Department.objects.filter(id=dep_id).first() if dep_id else None
    dir = Directorate.objects.filter(id=dir_id).first() if dir_id else None
    div = Division.objects.filter(id=div_id).first() if div_id else None

    # === SANANI FORMATLASH ===
    formatted_date = ''
    if date_id:
        try:
            dt = datetime.strptime(date_id.strip(), "%Y-%m-%d").date()
            oy_nomi = oylar[dt.month - 1]
            formatted_date = f"{dt.year} yil {dt.day}-{oy_nomi}"
        except Exception:
            formatted_date = date_id

    # === QAYSI BO‘LIM TANLANGANINI ANIQLASH ===
    if div:
        full_name = div
        filter_kwargs = {"employee__division": div}
    elif dir:
        full_name = dir
        filter_kwargs = {"employee__directorate": dir}
    elif dep:
        full_name = dep
        filter_kwargs = {"employee__department": dep}
    elif org:
        full_name = org
        filter_kwargs = {"employee__organization": org}
    else:
        return HttpResponse("Tashkilot / bo‘lim tanlanmagan!", status=400)

    # === TEXNIKALAR SONI (matn uchun) ===
    komp_qs = Technics.objects.filter(
        category__name__in=['Kompyuter', 'Planshet', 'Noutbook', 'Doska'],
        **filter_kwargs
    )

    # 🔥 Printer kategoriyalarini yuqoridagi get_technics_count bilan bir xil qilamiz
    prin_qs = Technics.objects.filter(
        category__name__in=['A4 Printer', 'Printer', 'scaner'],
        **filter_kwargs
    )

    komp_count = komp_qs.count()
    prin_count = prin_qs.count()

    # === TEXNIKALAR MATNI ===
    texnikalar_matni = ""
    if komp_count > 0:
        texnikalar_matni += (
            f"1.1. Biriktirilgan kompyuterlarga xizmat ko‘rsatish – {komp_count} dona.\n"
        )
    if prin_count > 0:
        texnikalar_matni += (
            f"1.2. Printerlarga xizmat ko‘rsatish – {prin_count} dona.\n"
        )
    if not texnikalar_matni:
        texnikalar_matni = "Texnikalar mavjud emas."

    # === JADVAL UCHUN REAL RO‘YXAT ===
    kompyuterlar = list(
        komp_qs.values(
            'name',      # Rusumi
            'serial',    # Seriya raqami
            'inventory'  # Inventar raqami
        )
    )

    printerlar = list(
        prin_qs.values(
            'name',      # Rusumi
            'serial'     # Seriya raqami
        )
    )

    # === SHABLONNI OCHISH ===
    template_path = os.path.join(settings.MEDIA_ROOT, 'document', 'dalolatnoma.docx')
    if not os.path.exists(template_path):
        return HttpResponse("Shablon fayl topilmadi!", status=404)

    doc = Document(template_path)

    # === ALMASHTIRILADIGAN MATNLAR ===
    replacements = {
        'DEPARTMENT': full_name.name,
        'POST': post_id or '',
        'FIO': fio_id or '',
        'DATA': formatted_date or '',
        'NAMBER': namber_id or '',
        'RIM': rim_id or '',
        'STYLE': full_name.name,
        'TEXNIKALAR': texnikalar_matni,
    }

    # === TEXT ALMASHTIRISH ===
    for p in doc.paragraphs:
        for run in p.runs:
            for old, new in replacements.items():
                if old in run.text:
                    run.text = run.text.replace(old, new)
                    run.font.name = 'Times New Roman'
                    run.font.size = Pt(12)
                    if old in ['STYLE', 'FIO', 'DATA', 'NAMBER']:
                        run.font.bold = True

    # === TABLE JOYINI TOPISH ===
    target_paragraph = None
    for p in doc.paragraphs:
        if 'TABLE' in p.text:
            target_paragraph = p
            p.text = ''
            break

    # === JADVALLAR Sarlavhalari ===
    headers_pc = ['№', 'Rusumi', 'Kompyuter SR:', 'Inventar raqami:']
    headers_printer = ['№', 'Rusumi', 'Printer SR:']

    # === JADVALLARNI YARATISH ===
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

    # === JOYLASHTIRISH ===
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

    # === FAYLNI YUKLATISH ===
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = 'attachment; filename=\"dalolatnoma.docx\"'
    doc.save(response)
    return response


@never_cache
@login_required
def order_sender(request):

    context = {
        "order": Order.objects.filter(sender=request.user.employee).order_by('-id'),
        "topic": Topic.objects.all(),
        "goal": Goal.objects.select_related('topic'),
        "technics": Technics.objects.filter(employee=request.user.employee),
    }
    return render(request, 'main/order_sender.html', context)


@never_cache
@login_required
def order_post(request):

    if request.method != 'POST':
        return redirect('order_sender')

    # 🔥 Kirgan userning employee obyektini olamiz
    employee = request.user.employee

    goal_id = request.POST.get("goal")
    technics_id = request.POST.get("technics")
    body = request.POST.get("body")
    type_of_work = request.POST.get("type_of_work", "online")

    # 🔥 Ma'lumotlarni bazadan olamiz
    goal = Goal.objects.filter(id=goal_id).first() if goal_id else None
    technic = Technics.objects.filter(id=technics_id).first() if technics_id else None

    # 🔥 Yangi Order yaratamiz
    Order.objects.create(
        sender=employee,
        goal=goal,
        technics=technic,
        body=body,
        type_of_work=type_of_work,
    )
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
            is_boss=True
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
    employee = request.user.employee

    if employee.is_boss:
        orders = Order.objects.filter(sender__region=employee.region).order_by('-id')
    else:
        orders = Order.objects.filter(receiver=employee).order_by('-id')

    context = {
        "employee": Employee.objects.filter(organization__org_type="IVS"),
        "order": orders,
        "topic": Topic.objects.all(),
        "goal": Goal.objects.select_related('topic'),
    }
    return render(request, 'main/order_receiver.html', context)


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

    if request.user.employee.status != "worker":
        raise PermissionDenied

    context = {
        'organizations': Organization.objects.all(),
    }
    return render(request, 'main/akt.html', context)

from datetime import date
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

    if request.user.employee.status != "worker":
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

    if request.user.employee.status != "worker":
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