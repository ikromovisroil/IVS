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
import os
import requests
from PyPDF2 import PdfReader
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Prefetch
from django.core.exceptions import PermissionDenied
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required

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
    if request.user.is_authenticated:
        context = {
            'employee': request.user.employee,
        }
        return render(request, 'main/profil.html', context)
    else:
        raise PermissionDenied


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
        'employee': Employee.objects.select_related('user')
        .exclude(user=request.user)
        .select_related("rank","organization","department","directorate","division")
    }
    return render(request, 'main/contact.html', context)


@never_cache
@login_required
def deed_post(request):
    if request.method != "POST":
        return redirect("contact")

    message = request.POST.get("message", "").strip()
    receiver_id = request.POST.get("receiver_id")
    agreements = request.POST.getlist("agreements")

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
        status="viewed"
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


@never_cache
@login_required
def deed_action(request, pk):
    deed = get_object_or_404(Deed, pk=pk)

    if request.method != "POST":
        return redirect(request.META.get("HTTP_REFERER", "/"))

    if deed.receiver.user != request.user:
        messages.info(request, "Sizga ruxsat yo‘q")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    action = request.POST.get("action")
    message_receiver = (request.POST.get("message_receiver") or "").strip()

    # ❌ Reject
    if action == "reject":
        deed.status = "rejected"
        deed.message_receiver = message_receiver
        deed.save()
        messages.info(request, "Dalolatnoma rad etildi")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    # ✅ Approve → SSO
    if action == "approve":
        file_path = deed.file.path

        if not os.path.exists(file_path):
            messages.info(request, "PDF topilmadi")
            return redirect(request.META.get("HTTP_REFERER", "/"))

        if not file_path.lower().endswith(".pdf"):
            messages.info(request, "PDF noto‘g‘ri")
            return redirect(request.META.get("HTTP_REFERER", "/"))

        if os.path.getsize(file_path) < 1024:
            messages.info(request, "PDF buzilgan")
            return redirect(request.META.get("HTTP_REFERER", "/"))

        try:
            PdfReader(file_path)
        except Exception:
            messages.info(request, "PDF o‘qilmadi")
            return redirect(request.META.get("HTTP_REFERER", "/"))

        # 🔐 SSO uchun session
        request.session["PENDING_DEED_APPROVE"] = {
            "deed_id": deed.id,
            "message_receiver": message_receiver,
            "redirect_url": request.META.get("HTTP_REFERER", "/"),
        }
        request.session.modified = True

        return redirect("sso_start_page")

    messages.error(request, "Noto‘g‘ri amal")
    return redirect("/")


@login_required
@never_cache
def sso_start_page(request):
    if "PENDING_DEED_APPROVE" not in request.session:
        messages.error(request, "Tasdiqlash topilmadi")
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
    try:
        body = json.loads(request.body or "{}")

        # 1️⃣ Token olish
        token_data = exchange_code_for_token(
            body.get("code"),
            body.get("codeVerifier"),
            body.get("redirectUri"),
        )

        user_data = decode_jwt(token_data["id_token"])

        pending = request.session.get("PENDING_DEED_APPROVE")
        if not pending:
            raise PermissionDenied("Pending yo‘q")

        deed = get_object_or_404(Deed, pk=pending["deed_id"])
        message_receiver = pending.get("message_receiver", "")
        redirect_url = pending.get("redirect_url", "/")

        # ❌ Begona foydalanuvchi bosolmaydi
        if deed.receiver.user != request.user:
            raise PermissionDenied("Ruxsat yo‘q")

        # 2️⃣ PINFL tekshiruv
        employee_pinfl = getattr(request.user.employee, "pinfl", None)
        sso_pinfl = user_data.get("pinfl")

        if not employee_pinfl or employee_pinfl != sso_pinfl:
            messages.error(
                request,
                "SSO kalit egasi va foydalanuvchi mos kelmadi!"
            )
            return JsonResponse({
                "status": "forbidden",
                "redirect": redirect_url
            }, status=403)

        # 3️⃣ Qayta imzolamaslik
        if deed.status == "approved":
            return JsonResponse({
                "status": "ok",
                "redirect": redirect_url
            })

        # 4️⃣ PDF ni imzolash (nomi o‘zgarmaydi)
        ok = sign_pdf(
            pdf_path=deed.file.path,
            request=request,
            approver_name=request.user.employee.full_name,
        )

        if not ok:
            raise Exception("Imzo xatosi")

        # 5️⃣ Statusni yangilash
        deed.status = "approved"
        deed.message_receiver = message_receiver
        deed.save()

        # 6️⃣ Session tozalash
        request.session.pop("PENDING_DEED_APPROVE", None)

        messages.success(request, "✅ Dalolatnoma tasdiqlandi")

        return JsonResponse({
            "status": "ok",
            "redirect": redirect_url
        })

    except Exception as e:
        print("SSO ERROR:", e)
        return JsonResponse({
            "status": "error",
            "message": "SSO xatolik"
        }, status=500)


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

    # ❌ Begona odam bosolmaydi
    if consent.employee.user != request.user:
        messages.error(request, "Sizga ruxsat yo‘q")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    # ❌ Qayta bosishni bloklaymiz
    if consent.status != "viewed":
        messages.info(request, "Bu kelishuv allaqachon ko‘rib chiqilgan")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    action = request.POST.get("action")
    message = request.POST.get("message", "").strip()

    if action == "approve":
        consent.status = "approved"
        consent.message = message
        messages.success(request, "Tasdiqlandi!")

    elif action == "reject":
        consent.status = "rejected"
        consent.message = message
        messages.warning(request, "Rad etildi!")

    else:
        return redirect(request.META.get("HTTP_REFERER", "/"))

    consent.save()
    return redirect(request.META.get("HTTP_REFERER", "/"))


@never_cache
@login_required
def barn(request):
    employees_boss = Employee.objects.filter(organization__org_type='IVS',is_boss=True)

    # GET'dan kelgan xodim ID (select2 dan)
    emp_id = request.GET.get("employee", "").strip()
    if emp_id:
        technics_qs = Technics.objects.filter(employee__id=emp_id)
        material_qs = Material.objects.filter(employee__id=emp_id)
    else:
        technics_qs = Technics.objects.filter(status='free')
        material_qs = Material.objects.filter(status='free')

    context = {
        "employees_boss": employees_boss,  # select uchun
        "technics": technics_qs,  # jadval
        "material": material_qs,  # jadval
    }

    return render(request, 'main/barn.html', context)


@never_cache
@login_required
def technics(request, slug=None):

    # 🔒 Worker bo‘lmagan foydalanuvchi kira olmaydi
    emp = getattr(request.user, "employee", None)
    if not emp or emp.status != "worker":
        raise PermissionDenied


    # 1️⃣ CATEGORY FILTER
    category = None
    if slug:
        category = get_object_or_404(Category, slug=slug)

    technics_qs = (
        Technics.objects
        .select_related("category", "employee", "employee__user", "employee__rank")
    )

    if category:
        technics_qs = technics_qs.filter(category=category)


    # 2️⃣ FILTER PARAMETRLAR
    org_id = request.GET.get("organization")
    dep_id = request.GET.get("department")
    dir_id = request.GET.get("directorate")
    div_id = request.GET.get("division")


    # 3️⃣ FILTERLASH (safe — employee None bo‘lsa ham xato bermaydi)
    if org_id:
        technics_qs = technics_qs.filter(employee__organization_id=org_id)

    if dep_id:
        technics_qs = technics_qs.filter(employee__department_id=dep_id)

    if dir_id:
        technics_qs = technics_qs.filter(employee__directorate_id=dir_id)

    if div_id:
        technics_qs = technics_qs.filter(employee__division_id=div_id)


    # 4️⃣ TEXNIKALAR SONI
    total_count = technics_qs.count()


    # 5️⃣ XODIM BO‘YICHA GURUHLASH (⚡ juda tez)
    grouped = defaultdict(list)

    for t in technics_qs.order_by(
        "employee__last_name",
        "employee__first_name",
        "category__name",
        "name"
    ):
        if t.employee:   # ⚠️ xodimsiz texnika bo‘lsa xato bermaydi
            grouped[t.employee].append(t)
        else:
            grouped[None].append(t)  # “biriktirilmagan texnika” guruhi


    # 6️⃣ FILTER SELECTLAR — OPTIMALLASHTIRILGAN
    organizations = Organization.objects.only("id", "name")

    departments = Department.objects.select_related("organization").only(
        "id", "name", "organization_id"
    )

    directorates = Directorate.objects.select_related("department").only(
        "id", "name", "department_id"
    )

    divisions = Division.objects.select_related("directorate").only(
        "id", "name", "directorate_id"
    )


    # 7️⃣ CONTEXT
    context = {
        "category": category,
        "grouped_technics": grouped.items(),
        "total_count": total_count,

        # Filter selectlar uchun
        "organizations": organizations,
        "departments": departments,
        "directorates": directorates,
        "divisions": divisions,

        # Selected qiymatlar
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


from django.db import transaction
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
        'employees': Employee.objects.all(),
        'organizations': Organization.objects.all(),
        'departments': Department.objects.select_related('organization'),
        'directorate': Directorate.objects.select_related('department'),
        'division': Division.objects.select_related('directorate'),
    }
    return render(request, 'main/akt.html', context)

from datetime import datetime, timedelta
@never_cache
@login_required
def akt_post(request):

    if request.method != "POST":
        return redirect("document_get")

    org_id = request.POST.get("organizator")

    date_id1 = request.POST.get("date1")
    date_id2 = request.POST.get("date2")

    date1_naive = datetime.strptime(date_id1, "%Y-%m-%d")
    date2_naive = datetime.strptime(date_id2, "%Y-%m-%d")+ timedelta(days=1)

    date1 = timezone.make_aware(date1_naive)
    date2 = timezone.make_aware(date2_naive)

    qs = OrderMaterial.objects.filter(
        order__sender__organization_id=org_id,
        order__date_creat__gte=date1,
        order__date_creat__lt=date2
    )
    print(qs)

    doc = Document(os.path.join(settings.MEDIA_ROOT, "document", "svod.docx"))

    replace_text(doc, {
        "RECEIVER": request.user.employee.full_name or "",
    })

    target = next((p for p in doc.paragraphs if "TABLE" in p.text), None)
    if not target:
        return HttpResponse("TABLE topilmadi", status=500)

    target.text = ""

    headers = [
        "№", "Materialning nomi", "O'lchov birligi", "Miqdori",
        "Birlik narxi", "Umumiy qiymati", "Eslatma", "Kod 1С"
    ]

    rows = []
    for q in qs:
        rows.append([
            q.order.technics.name if q.order.technics else "",
            q.order.technics.serial if q.order.technics else "",
            q.material.name,
            q.number,
            q.material.unit or "dona",
            q.order.sender.full_name,
            q.order.sender.rank.name if q.order.sender.rank else "",
            f"{q.material.price:,}".replace(",", " ") if q.material.price else ""
        ])

    h, table = create_table_cols_svod(
        doc,
        "",
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
    response["Content-Disposition"] = f'attachment; filename="order.docx"'
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

    org_id = request.POST.get("organizator")
    date_id1 = request.POST.get("date1")
    date_id2 = request.POST.get("date2")

    date1 = timezone.make_aware(datetime.strptime(date_id1, "%Y-%m-%d"))
    date2 = timezone.make_aware(datetime.strptime(date_id2, "%Y-%m-%d") + timedelta(days=1))

    qs = (
        OrderMaterial.objects
        .select_related("material", "order", "order__sender")
        .all()
        .order_by("material_id", "order_id", "id")
    )

    # org bo‘yicha filter kerak bo‘lsa
    if org_id:
        qs = qs.filter(order__sender__organization_id=org_id)

    doc = Document(os.path.join(settings.MEDIA_ROOT, "document", "svod.docx"))

    replace_text(doc, {"RECEIVER": request.user.employee.full_name or ""})

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
    grand_total = 0

    for q in qs:
        if not q.material:
            continue

        unit_price = q.material.price or 0
        qty = q.number or 0
        total = unit_price * qty
        grand_total += total

        code = getattr(q.material, "code", "") or ""
        unit = (q.material.unit or "dona")
        name = q.material.name or ""

        # Guruhlash kaliti: bitta material
        key = (q.material.id, name, unit, code)

        # Eslatma: Akt №ID ga DD.MM.YYYYy,
        eslatma_one = ""
        if q.order and q.order.date_creat:
            eslatma_one = f"\nAkt №{q.order.id} ga  {q.order.date_creat.strftime('%d.%m.%Y')} y,"

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
    return render(request, 'main/svod.html', context)

@never_cache
@login_required
def reestr_post(request):

    if request.method != "POST":
        return redirect("document_get")

    dep_id = request.POST.get("department")
    employee_id = request.POST.get("employee")

    date_id1 = request.POST.get("date1")
    date_id2 = request.POST.get("date2")

    date1_naive = datetime.strptime(date_id1, "%Y-%m-%d")
    date2_naive = datetime.strptime(date_id2, "%Y-%m-%d")+ timedelta(days=1)

    date1 = timezone.make_aware(date1_naive)
    date2 = timezone.make_aware(date2_naive)
    print(date1, date2)

    qs = OrderMaterial.objects.filter(
        order__date_creat__gte=date1,
        order__date_creat__lt=date2
    )

    print(qs)
    dep = Department.objects.filter(id=dep_id).first() if dep_id else None
    emp = Employee.objects.filter(id=employee_id).first() if employee_id else None
    doc = Document(os.path.join(settings.MEDIA_ROOT, "document", "akt.docx"))

    replace_text(doc, {
        "ID": str(12),
        "RECEIVER": request.user.employee.full_name or "",
        "SENDER": emp.full_name or "",
        "DEPARTMENT": dep.name if dep else "",
    })

    target = next((p for p in doc.paragraphs if "TABLE" in p.text), None)
    if not target:
        return HttpResponse("TABLE topilmadi", status=500)

    target.text = ""

    headers = [
        "№", "Qurilma Nomi", "Seriya", "Material",
        "Soni", "Birligi", "F.I.Sh.", "Lavozimi", "Narxi"
    ]

    rows = []
    for q in qs:
        rows.append([
            q.order.technics.name if q.order.technics else "",
            q.order.technics.serial if q.order.technics else "",
            q.material.name,
            q.number,
            q.material.unit or "dona",
            q.order.sender.full_name,
            q.order.sender.rank.name if q.order.sender.rank else "",
            f"{q.material.price:,}".replace(",", " ") if q.material.price else ""
        ])

    h, table = create_table_10cols(
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
    response["Content-Disposition"] = f'attachment; filename="order.docx"'
    return response

