import base64
import binascii
import logging
import os
import re
import secrets
import shutil
import tempfile
import unicodedata
import zipfile
from datetime import datetime, timedelta
from PyPDF2 import PdfReader
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.contrib.auth import get_user_model
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Count, Q
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from .push_views import notify_deed_sender, notify_deed_watchers
from .html_pdf import HtmlPdfError, add_text_watermark_pdf_bytes, deed_to_pdf_bytes
from .models import (
    Deed, DeedConsent, DeedFiles, Department, Directorate, Division, Employee, Goal, Material, MaterialMovement,
    MaterialUser, Order, OrderMaterial, Organization, Technics,
)
from .sanitizers import sanitize_deed_body
from .tasks import _resolve_position
from .validators import validate_attachment_extension

User = get_user_model()
logger = logging.getLogger(__name__)

MAX_DEED_ATTACHMENTS = 10

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
    return redirect(settings.SPA_URL)  # yangi interfeys kirishni o'zi ko'rsatadi


def spa_redirect(request, *args, **kwargs):
    """
    Eski sahifa manzillari (xatcho'plar, eski havolalar) yangi interfeysga o'tkazadi. Manzil nomlari (`reverse`)
    saqlanadi: SPA ishlatadigan POST funksiyalari muvaffaqiyatdan keyin shu nomlarga redirect qiladi.
    """
    return redirect(settings.SPA_URL)


@require_GET
def deed_status(request, code, pk):
    deed = get_object_or_404(Deed, pk=pk, code=code)
    context = {"d": deed}
    return render(request, "main/deed_status.html", context)


def validate_pdf_file(file_field):
    if not file_field:
        return False, "PDF yo'q"

    try:
        file_path = file_field.path
    except Exception:
        return False, "PDF yo'li topilmadi"

    if not file_path or not os.path.exists(file_path):
        return False, "PDF topilmadi"

    if not file_path.lower().endswith(".pdf"):
        return False, "PDF noto'g'ri"

    if os.path.getsize(file_path) < 1024:
        return False, "PDF buzilgan"

    try:
        PdfReader(file_path)
    except Exception:
        return False, "PDF o'qilmadi"

    return True, None


def _deed_consents_open(deed):
    """Kelishuvchilarni o'zgartirish mumkinmi: hujjat rad etilmagan va imzolash tugamagan bo'lsa."""
    if deed.status_sender == "rejected" or deed.status_receiver == "rejected":
        return False
    signed = deed.status_sender == "approved" and (
        not deed.receiver_id or deed.status_receiver == "approved"
    )
    return not signed


def _deed_consent_org_ids(deed, employee):
    """deed_edit dagi bilan bir xil: imzolovchi, qabul qiluvchi va yuboruvchi tashkilotlari."""
    ids = {employee.organization_id}
    if deed.sender_id:
        ids.add(deed.sender.organization_id)
    if deed.receiver_id:
        ids.add(deed.receiver.organization_id)
    return [i for i in ids if i]


def _can_add_consents(deed, employee):
    """Yaratuvchi yoki (yaratuvchi ruxsat bergan, hali javob bermagan) imzolovchi qo'sha oladi."""
    if deed.user_id == employee.id:
        return True
    if deed.sender_id == employee.id:
        return deed.sender_can_add_consent and deed.status_sender == "viewed"
    if deed.receiver_id == employee.id:
        return deed.receiver_can_add_consent and deed.status_receiver == "viewed"
    return False


def _employee_has_full_scope(request):
    """organization va region bo'yicha to'liq ko'rish huquqi bormi."""
    return (
        request.user.has_perm("main.all_organization"),
        request.user.has_perm("main.all_region"),
    )


def _check_technics_scope(request, employee, tex):
    """
    Ro'yxatdagi bilan BIR XIL org/region cheklovi — amal (delete/attach/
    update/download) funksiyalarida qayta tekshiriladi. Aks holda global
    Django ruxsatiga ega xodim, ro'yxatda ko'rmasa ham, boshqa tashkilot/
    hududga tegishli texnikani pk orqali topib o'zgartira olar edi.
    """
    has_full_org, has_full_region = _employee_has_full_scope(request)
    if not has_full_org and tex.organization_id != employee.organization_id:
        raise PermissionDenied("Bu texnika sizning tashkilotingizga tegishli emas")
    if not has_full_region and tex.region_id != employee.region_id:
        raise PermissionDenied("Bu texnika sizning hududingizga tegishli emas")


# ═══════════════════════════════════════════════════════════════════
# TECHNICS (asosiy uskunalar)
# ═══════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════
# EXTRA_TEX (qo'shimcha qurilmalar / Structure)
# ═══════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════
# MATERIAL (ombor materiallari)
# ═══════════════════════════════════════════════════════════════════


from datetime import datetime


@never_cache
@require_POST
@login_required
@permission_required("main.all_material_employee", raise_exception=True)
@transaction.atomic
def mat_arxiv_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    back_url = request.META.get("HTTP_REFERER", "/")

    emp_id = (request.POST.get("employe") or "").strip()
    body = (request.POST.get("body") or "").strip()

    if not emp_id or not emp_id.isdigit():
        messages.error(request, "Xodim tanlanmadi")
        return redirect(back_url)

    get_employee = get_object_or_404(
        Employee, pk=int(emp_id), organization=employee.organization
    )

    cart_qs = (
        MaterialMovement.objects
        .filter(user=employee, employee__isnull=True)
        .select_for_update()
    )

    if not cart_qs.exists():
        messages.error(request, "Biriktiriladigan material topilmadi")
        return redirect(back_url)

    moved_count = 0

    for movement in cart_qs:
        mat = Material.objects.select_for_update(of=("self",)).get(pk=movement.material_id)
        outcome = movement.outcome or 0

        if outcome <= 0:
            continue

        if not mat.is_active:
            messages.error(request, f"'{mat.name}' o'chirilgan, biriktirib bo'lmaydi")
            continue

        if mat.employee_id and mat.employee_id == get_employee.id:
            messages.error(request, f"'{mat.name}' allaqachon shu xodimga tegishli")
            continue

        if outcome > mat.number:
            messages.error(
                request,
                f"'{mat.name}' uchun omborda yetarli emas (bor: {mat.number}, kerak: {outcome})"
            )
            continue

        giver = mat.employee

        mat.number -= outcome
        mat.save(update_fields=["number"])

        dst_filter = {"employee_id": get_employee.id}
        if (mat.code or "").strip():
            dst_filter["code"] = mat.code
        else:
            dst_filter["name"] = mat.name

        dst = Material.objects.select_for_update(of=("self",)).filter(**dst_filter).first()

        if dst:
            dst.number = (dst.number or 0) + outcome
            if (dst.price in [None, 0, "0"]) and mat.price not in [None, 0, "0"]:
                dst.price = mat.price
            if not dst.unit_id and mat.unit_id:
                dst.unit = mat.unit
            dst.is_active = True
            fields = ["number", "price", "unit", "is_active"]
            # Kategoriya/rasm bo'sh bo'lsa — beruvchining materialidan to'ldiriladi
            if not dst.category_id and mat.category_id:
                dst.category_id = mat.category_id
                fields.append("category")
            if not dst.image and mat.image:
                dst.image = mat.image
                fields.append("image")
            dst.save(update_fields=fields)
            dst_material = dst
        else:
            dst_material = Material.objects.create(
                organization=get_employee.organization,
                employee=get_employee,
                category_id=mat.category_id,
                name=mat.name,
                code=mat.code,
                number=outcome,
                unit=mat.unit,
                price=mat.price,
                year=mat.year,
                image=mat.image,
            )

        movement.user = giver
        movement.employee = get_employee
        if body:
            movement.body = body
        movement.save(update_fields=["user", "employee", "body"])

        MaterialMovement.objects.create(
            user=giver,
            employee=get_employee,
            material=dst_material,
            status="assigned",
            income=outcome,
        )

        moved_count += 1

    if moved_count:
        messages.success(request, f"{moved_count} ta material {get_employee.full_name}ga biriktirildi")
    else:
        messages.error(request, "Hech qanday material biriktirilmadi")

    return redirect(back_url)


@never_cache
@require_POST
@login_required
@transaction.atomic
def mat_arxiv_delete(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")
    back_url = request.META.get("HTTP_REFERER", "/")

    material = get_object_or_404(MaterialMovement, pk=pk)

    if material.user_id != employee.id:
        raise PermissionDenied("Sizga ruxsat yo'q")

    material.delete()

    messages.success(request, "Material savatdan o'chirildi")
    return redirect(back_url)


@never_cache
@require_POST
@login_required
@permission_required("main.all_material_employee", raise_exception=True)
@transaction.atomic
def mat_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    back_url = request.META.get("HTTP_REFERER", "/")

    mat_id = (request.POST.get("material_id") or "").strip()
    number_raw = (request.POST.get("number") or "").strip()

    if not mat_id.isdigit():
        messages.error(request, "Material tanlanmadi")
        return redirect(back_url)

    try:
        number = int(number_raw)
        if number <= 0:
            raise ValueError
    except (TypeError, ValueError):
        messages.error(request, "Soni noto'g'ri kiritildi")
        return redirect(back_url)

    mat = get_object_or_404(
        Material.objects.select_for_update(of=("self",)),
        pk=int(mat_id),
        is_active=True,
        organization=employee.organization,
    )
    MaterialMovement.objects.create(
        material=mat,
        user=employee,
        employee=None,
        status="assigned",
        outcome=number,
    )

    messages.success(request, "Material savatga saqlandi")
    return redirect(back_url)


def _decode_body(request):
    """Base64 orqali kelgan (WAF chetlab o'tilgan) body ni dekodlab,
    MAJBURIY sanitizatsiya qiladi. Bo'sh yoki xato bo'lsa "" qaytaradi."""
    body_encoded = (request.POST.get("body_encoded") or "").strip()
    if not body_encoded:
        return ""
    try:
        body = base64.b64decode(body_encoded).decode("utf-8").strip()
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return ""
    return sanitize_deed_body(body) if body else ""


def _save_deed_pdf(deed):
    """PDF yaratib, deed.file ga saqlaydi. Chaqiruvchi buni
    transaction.atomic() ICHIDA chaqirishi shart — aks holda xato
    bo'lganda Deed faylsiz qolib ketishi mumkin."""
    pdf_bytes = deed_to_pdf_bytes(deed)
    pdf_bytes = add_text_watermark_pdf_bytes(pdf_bytes, "TASDIQLANMAGAN")
    pdf_name = f"akt_{timezone.now().strftime('%Y%m%d')}_{secrets.token_urlsafe(6)}.pdf"
    deed.file.save(pdf_name, ContentFile(pdf_bytes), save=True)


@never_cache
@require_POST
@login_required
def document_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.organization, "type", None) != "worker":
        raise PermissionDenied("Ruxsat yo'q")

    if not employee.can_make_document:
        raise PermissionDenied("Ruxsat yo'q")

    org_id = (request.POST.get("organization") or "").strip()
    sender_id = (request.POST.get("sender") or "").strip()
    receiver_id = (request.POST.get("receiver") or "").strip()
    message = (request.POST.get("message") or "").strip() or None
    agreements = request.POST.getlist("agreements[]")

    body = _decode_body(request)

    org = Organization.objects.filter(id=org_id).first() if org_id.isdigit() else None
    if not org:
        messages.error(request, "Tashkilot topilmadi")
        return redirect("document_get")

    allowed_sender_qs = Employee.objects.filter(
        Q(department_id=283) | Q(department_id=298, region=employee.region)
    )
    sender = allowed_sender_qs.filter(id=sender_id).first() if sender_id.isdigit() else None

    if not sender:
        messages.error(request, "Imzolovchi xodim tanlanmadi yoki ruxsat etilmagan")
        return redirect("document_get")

    receiver = Employee.objects.filter(id=receiver_id).first() if receiver_id.isdigit() else None

    if not body:
        messages.error(request, "Hujjat matni bo'sh bo'lmasin")
        return redirect("document_get")

    attachments = request.FILES.getlist("attachments")
    if len(attachments) > MAX_DEED_ATTACHMENTS:
        messages.error(request, f"Ilova fayllari {MAX_DEED_ATTACHMENTS} tadan ko'p bo'lmasligi kerak")
        return redirect("document_get")
    for att in attachments:
        try:
            validate_attachment_extension(att)
        except ValidationError as e:
            messages.error(request, f"{att.name}: {' '.join(e.messages)}")
            return redirect("document_get")

    exclude_ids = {sender.id}
    if receiver:
        exclude_ids.add(receiver.id)

    raw_ids = list({int(x) for x in agreements if (x or "").strip().isdigit()})
    raw_ids = [i for i in raw_ids if i not in exclude_ids]

    try:
        with transaction.atomic():
            deed = Deed.objects.create(
                organization=org,
                sender=sender,
                receiver=receiver,
                user=employee,
                message_user=message,
                body=body,
                status='document',
            )

            emps = Employee.objects.filter(id__in=raw_ids).only("id") if raw_ids else Employee.objects.none()
            if raw_ids:
                objs = [DeedConsent(deed=deed, employee=e, status="viewed") for e in emps]
                DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

            for att in attachments:
                DeedFiles.objects.create(deed=deed, file=att)

            _save_deed_pdf(deed)

    except HtmlPdfError as e:
        messages.error(request, f"Hujjat yaratilmadi: {e}. Qayta urinib ko'ring")
        return redirect("document_get")
    except DatabaseError:
        messages.error(request, "Xatolik yuz berdi. Qayta urinib ko'ring")
        return redirect("document_get")

    notify_deed_sender(deed)
    if raw_ids:
        notify_deed_watchers(deed, emps)

    messages.success(request, "Imzolashga yuborildi")
    return redirect("contact_user")


@never_cache
@require_POST
@login_required
@permission_required("main.change_order", raise_exception=True)
def akt_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    org_id = (request.POST.get("organization") or "").strip()
    dep_id = (request.POST.get("department") or "").strip()
    region_id = (request.POST.get("region") or "").strip()
    sender_id = (request.POST.get("sender") or "").strip()
    message = (request.POST.get("message") or "").strip() or None
    d1 = (request.POST.get("date1") or "").strip()
    d2 = (request.POST.get("date2") or "").strip()

    body = _decode_body(request)

    org = Organization.objects.filter(id=org_id).first() if org_id.isdigit() else None
    if not org:
        messages.error(request, "Tashkilot topilmadi")
        return redirect("akt_get")

    has_full_region = request.user.has_perm("main.all_region")
    if has_full_region:
        region_filter_id = int(region_id) if region_id.isdigit() else None
    else:
        region_filter_id = employee.region_id
        if not region_filter_id:
            messages.error(request, "Hudud aniqlanmadi")
            return redirect("akt_get")

    sender = Employee.objects.filter(id=sender_id, organization_id=org.id).first() if sender_id.isdigit() else None
    if not sender:
        messages.error(request, "Imzolovchi xodim tanlanmadi yoki bu tashkilotga tegishli emas")
        return redirect("akt_get")

    if not body:
        messages.error(request, "Hujjat matni bo'sh bo'lmasin")
        return redirect("akt_get")

    if not d1 or not d2:
        messages.error(request, "Sana oralig'i tanlanmagan")
        return redirect("akt_get")

    try:
        date1 = timezone.make_aware(datetime.strptime(d1, "%Y-%m-%d"))
        date2 = timezone.make_aware(datetime.strptime(d2, "%Y-%m-%d") + timedelta(days=1))
    except ValueError:
        messages.error(request, "Sana formati noto'g'ri")
        return redirect("akt_get")

    # ── Materiallarni AVTOMATIK aniqlaymiz ──
    sender_ids_material = MaterialUser.objects.filter(
        receiver=employee
    ).values_list("sender_id", flat=True)

    auto_qs = OrderMaterial.objects.filter(
        order__date_finished__gte=date1,
        order__date_finished__lt=date2,
        order__sender_organization_id=org.id,
    )

    # ajax_akt_materials bilan bir xil qoida: barcha hududlarni ko'ra oladigan
    # xodimda MaterialUser bo'yicha cheklov yo'q.
    if not has_full_region:
        auto_qs = auto_qs.filter(material__employee_id__in=sender_ids_material)

    if region_filter_id:
        auto_qs = auto_qs.filter(order__receiver_region_id=region_filter_id)

    if dep_id.isdigit():
        auto_qs = auto_qs.filter(order__sender_department_id=dep_id)

    order_ids = set(auto_qs.exclude(order__isnull=True).values_list("order_id", flat=True).distinct())

    orders_qs = Order.objects.filter(id__in=order_ids).select_related("sender", "receiver")

    sender_ids = set(orders_qs.exclude(sender__isnull=True).values_list("sender_id", flat=True))
    receiver_ids = set(orders_qs.exclude(receiver__isnull=True).values_list("receiver_id", flat=True))

    auto_agreement_ids = (sender_ids | receiver_ids)
    auto_agreement_ids.discard(sender.id)

    try:
        with transaction.atomic():
            deed = Deed.objects.create(
                organization=org,
                sender=sender,
                user=employee,
                message_user=message,
                body=body,
                status='act',
            )

            if order_ids:
                deed.orders.set(order_ids)

            emps = (
                Employee.objects.filter(id__in=auto_agreement_ids).only("id")
                if auto_agreement_ids else Employee.objects.none()
            )
            if auto_agreement_ids:
                objs = [
                    DeedConsent(deed=deed, employee=e, status="approved")
                    for e in emps
                ]
                DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

            _save_deed_pdf(deed)

    except HtmlPdfError as e:
        messages.error(request, f"Hujjat yaratilmadi: {e}. Qayta urinib ko'ring")
        return redirect("akt_get")
    except DatabaseError:
        messages.error(request, "Xatolik yuz berdi. Qayta urinib ko'ring")
        return redirect("akt_get")

    notify_deed_sender(deed)
    if auto_agreement_ids:
        notify_deed_watchers(deed, emps)

    messages.success(request, "Imzolashga yuborildi")
    return redirect("contact_user")


@never_cache
@require_POST
@login_required
def svod_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if not (request.user.has_perm("main.shop_employee") or request.user.has_perm("main.report_employee")):
        raise PermissionDenied("Ruxsat yo'q")

    org_ids = [i for i in request.POST.getlist("organizations[]") if i.isdigit()]
    sender_id = (request.POST.get("sender") or "").strip()
    message = (request.POST.get("message") or "").strip() or None
    agreements = request.POST.getlist("agreements[]")

    body = _decode_body(request)

    if not org_ids:
        messages.error(request, "Kamida bitta tashkilot tanlang")
        return redirect("svod_get")

    orgs = Organization.objects.filter(id__in=org_ids).exclude(type="worker")
    if not orgs.exists():
        messages.error(request, "Tashkilotlar topilmadi")
        return redirect("svod_get")

    sender = Employee.objects.filter(
        Q(id=sender_id) & (Q(department_id=283) | Q(organization_id=4))
    ).first() if sender_id.isdigit() else None

    if not sender:
        messages.error(request, "Imzolovchi xodim tanlanmadi yoki ruxsat etilmagan")
        return redirect("svod_get")

    if not body:
        messages.error(request, "Hujjat matni bo'sh bo'lmasin")
        return redirect("svod_get")

    raw_ids = list({int(x) for x in agreements if (x or "").strip().isdigit()})
    raw_ids = [i for i in raw_ids if i != sender.id]

    # Deed.organization — bitta FK. Bir nechta tashkilot tanlanganda
    # birinchisini asosiy tashkilot sifatida yozamiz; barcha tashkilotlar
    # hujjat matnida (body) allaqachon ko'rinadi.
    primary_org = orgs.first()

    try:
        with transaction.atomic():
            deed = Deed.objects.create(
                organization=primary_org,
                sender=sender,
                user=employee,
                message_user=message,
                body=body,
                status='svod',
            )

            emps = (
                Employee.objects.filter(
                    Q(id__in=raw_ids) & (Q(department_id=283) | Q(organization_id=4))
                ).only("id")
                if raw_ids else Employee.objects.none()
            )
            if raw_ids:
                objs = [DeedConsent(deed=deed, employee=e, status="viewed") for e in emps]
                DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

            _save_deed_pdf(deed)

    except HtmlPdfError as e:
        messages.error(request, f"Hujjat yaratilmadi: {e}. Qayta urinib ko'ring")
        return redirect("svod_get")
    except DatabaseError:
        messages.error(request, "Xatolik yuz berdi. Qayta urinib ko'ring")
        return redirect("svod_get")

    notify_deed_sender(deed)
    if raw_ids:
        notify_deed_watchers(deed, emps)

    messages.success(request, "Imzolashga yuborildi")
    return redirect("contact_user")


@never_cache
@require_POST
@login_required
def reest_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if not (request.user.has_perm("main.shop_employee") or request.user.has_perm("main.report_employee")):
        raise PermissionDenied("Ruxsat yo'q")

    org_id = (request.POST.get("organization") or "").strip()
    sender_id = (request.POST.get("sender") or "").strip()
    message = (request.POST.get("message") or "").strip() or None
    agreements = request.POST.getlist("agreements[]")

    body = _decode_body(request)

    org = Organization.objects.filter(id=org_id).first() if org_id.isdigit() else None
    if not org:
        messages.error(request, "Tashkilot topilmadi")
        return redirect("reestr_get")

    # reestr_get dagi bilan BIR XIL: employee.organization_id ga
    # tegishli xodimlargina sender bo'la oladi.
    sender = Employee.objects.filter(
        id=sender_id, organization_id=employee.organization_id
    ).first() if sender_id.isdigit() else None

    if not sender:
        messages.error(request, "Imzolovchi xodim tanlanmadi yoki ruxsat etilmagan")
        return redirect("reestr_get")

    if not body:
        messages.error(request, "Hujjat matni bo'sh bo'lmasin")
        return redirect("reestr_get")

    raw_ids = list({int(x) for x in agreements if (x or "").strip().isdigit()})
    raw_ids = [i for i in raw_ids if i != sender.id]

    try:
        with transaction.atomic():
            deed = Deed.objects.create(
                organization=org,
                sender=sender,
                user=employee,
                message_user=message,
                body=body,
                status='reestr',
            )

            emps = (
                Employee.objects.filter(
                    id__in=raw_ids, organization_id=employee.organization_id
                ).only("id")
                if raw_ids else Employee.objects.none()
            )
            if raw_ids:
                objs = [DeedConsent(deed=deed, employee=e, status="viewed") for e in emps]
                DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

            _save_deed_pdf(deed)

    except HtmlPdfError as e:
        messages.error(request, f"Hujjat yaratilmadi: {e}. Qayta urinib ko'ring")
        return redirect("reestr_get")
    except DatabaseError:
        messages.error(request, "Xatolik yuz berdi. Qayta urinib ko'ring")
        return redirect("reestr_get")

    notify_deed_sender(deed)
    if raw_ids:
        notify_deed_watchers(deed, emps)

    messages.success(request, "Imzolashga yuborildi")
    return redirect("contact_user")


# ═══════════════════════════════════════════════════════════════════
# SERVISE
# ═══════════════════════════════════════════════════════════════════
def quarter_roman(month):
    """Oy raqami (1-12) -> chorak: yanvar-mart I, aprel-iyun II, iyul-sentyabr III, oktyabr-dekabr IV."""
    return ["I", "II", "III", "IV"][(int(month) - 1) // 3]


@never_cache
@require_POST
@login_required
@permission_required("main.material_service", raise_exception=True)
def service_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.organization, "type", None) != "worker":
        raise PermissionDenied("Ruxsat yo'q")

    employe_id = (request.POST.get("sender") or "").strip()
    message = (request.POST.get("message") or "").strip() or None
    agreements = request.POST.getlist("agreements[]")

    body = _decode_body(request)


    if not employe_id:
        messages.error(request, "Imzolovchi xodim tanlanmadi yoki ruxsat etilmagan")
        return redirect("service_get")

    sender = Employee.objects.filter(id=employe_id).first() if employe_id.isdigit() else None

    if not sender:
        messages.error(request, "Imzolovchi xodim topilmadi")
        return redirect("service_get")

    if not body:
        messages.error(request, "Hujjat matni bo'sh bo'lmasin")
        return redirect("service_get")

    attachments = request.FILES.getlist("attachments")
    if len(attachments) > MAX_DEED_ATTACHMENTS:
        messages.error(request, f"Ilova fayllari {MAX_DEED_ATTACHMENTS} tadan ko'p bo'lmasligi kerak")
        return redirect("service_get")
    for att in attachments:
        try:
            validate_attachment_extension(att)
        except ValidationError as e:
            messages.error(request, f"{att.name}: {' '.join(e.messages)}")
            return redirect("service_get")

    exclude_ids = {sender.id}

    raw_ids = list({int(x) for x in agreements if (x or "").strip().isdigit()})
    raw_ids = [i for i in raw_ids if i not in exclude_ids]

    try:
        with transaction.atomic():
            deed = Deed.objects.create(
                organization=employee.organization,
                sender=sender,
                user=employee,
                message_user=message,
                body=body,
                status='service',
            )

            emps = Employee.objects.filter(id__in=raw_ids).only("id") if raw_ids else Employee.objects.none()
            if raw_ids:
                objs = [DeedConsent(deed=deed, employee=e, status="viewed") for e in emps]
                DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

            for att in attachments:
                DeedFiles.objects.create(deed=deed, file=att)

            _save_deed_pdf(deed)

    except HtmlPdfError as e:
        messages.error(request, f"Hujjat yaratilmadi: {e}. Qayta urinib ko'ring")
        return redirect("service_get")
    except DatabaseError:
        messages.error(request, "Xatolik yuz berdi. Qayta urinib ko'ring")
        return redirect("service_get")

    notify_deed_sender(deed)
    if raw_ids:
        notify_deed_watchers(deed, emps)

    messages.success(request, "Imzolashga yuborildi")
    return redirect("contact_user")


# ═══════════════════════════════════════════════════════════════════
# STATISTIKA: TASHKILOTLAR (tanlangan tuzilmadagi xodimlar va ularning arizalari)
# ═══════════════════════════════════════════════════════════════════
ORG_STATUS_PAGE_SIZE = 20


def _status_goal_type(employee):
    """Statistika uchun ariza turi: ATM (worker) xodimiga - ATMga yuborilganlar, boshqalarga - omborxonaga."""
    is_atm = getattr(employee.organization, "type", None) == "worker"
    return ("worker", "ATMga") if is_atm else ("client", "Omborxonaga")


@never_cache
@require_GET
@login_required
@permission_required("main.status_employee", raise_exception=True)
def org_status_employee(request, pk):
    """
    Modal uchun: xodimning (sana oralig'ida) ariza kategoriyalari bo'yicha yuborgan arizalari soni.
    Jadvalda turning BARCHA kategoriyalari chiqadi (ariza berilmaganlari 0 bilan): ATM xodimi uchun ATM
    kategoriyalari, ATM bo'lmagan xodim uchun xodim tashkilotining omborxona kategoriyalari.
    Tashkilot doirasi `org_status` bilan bir xil: `all_organization` bo'lmasa faqat o'z tashkilotining xodimi.
    """
    viewer = getattr(request.user, "employee", None)
    if not viewer:
        raise PermissionDenied("Employee yo'q")

    targets = Employee.objects.select_related("rank", "department", "directorate", "division", "organization").filter(
        user__is_active=True,
    )
    if not request.user.has_perm("main.all_organization"):
        targets = targets.filter(organization_id=viewer.organization_id)
    if not request.user.has_perm("main.all_region"):
        targets = targets.filter(region_id=viewer.region_id) if viewer.region_id else targets.none()
    target = get_object_or_404(targets, pk=pk)

    goal_type, kind_label = _status_goal_type(viewer)
    date1_raw = (request.GET.get("date1") or "").strip()
    date2_raw = (request.GET.get("date2") or "").strip()
    date1 = parse_date(date1_raw) if date1_raw else None
    date2 = parse_date(date2_raw) if date2_raw else None

    orders = Order.objects.filter(sender=target, goal__organization__type=goal_type)
    if date1:
        orders = orders.filter(date_creat__date__gte=date1)
    if date2:
        orders = orders.filter(date_creat__date__lte=date2)

    counts = {row["goal_id"]: row["n"] for row in orders.values("goal_id").annotate(n=Count("id"))}
    goals = Goal.objects.filter(organization__type=goal_type)
    if goal_type == "client":
        goals = goals.filter(organization_id=target.organization_id)
    names = {goal.id: goal.name for goal in goals}
    for goal in Goal.objects.filter(pk__in=set(counts) - set(names)):       # ro'yxatda yo'q, lekin ariza berilgan kategoriya
        names[goal.id] = goal.name
    items = sorted(
        ({"goal_id": gid, "goal": name or "—", "count": counts.get(gid, 0)} for gid, name in names.items()),
        key=lambda item: (-item["count"], item["goal"].lower()),
    )
    return JsonResponse({
        "employee": {
            "id": target.id,
            "full_name": target.full_name,
            "rank": target.rank.name if target.rank_id else "",
            "organization": target.organization.name if target.organization_id else "",
            "department": target.department.name if target.department_id else "",
            "directorate": target.directorate.name if target.directorate_id else "",
            "division": target.division.name if target.division_id else "",
        },
        "kind": kind_label,
        "date1": date1.isoformat() if date1 else "",
        "date2": date2.isoformat() if date2 else "",
        "items": items,
        "total": sum(item["count"] for item in items),
    })


TEX_GROUP_ICONS = ("bi-pc-display", "bi-printer", "bi-hdd-network", "bi-phone", "bi-camera-video", "bi-cpu", "bi-display", "bi-box-seam")
# Guruh nomidagi kalit so'zga qarab ikonka (birinchi mos kelgani); topilmasa tartib bo'yicha
TEX_GROUP_ICON_KEYWORDS = (
    (("tarmoq", "network", "router", "switch"), "bi-hdd-network"),
    (("transport", "mashina", "avto", "avtomobil", "car"), "bi-car-front"),
    (("printer", "chop"), "bi-printer"),
    (("telefon", "phone", "mobil"), "bi-phone"),
    (("kamera", "video", "kuzatuv"), "bi-camera-video"),
    (("kompyuter", "texnika", "noutbuk", "computer"), "bi-pc-display"),
    (("monitor", "ekran", "display"), "bi-display"),
    (("server", "protsessor"), "bi-cpu"),
)


def tex_group_icon(name, position):
    lowered = (name or "").lower()
    for keywords, icon in TEX_GROUP_ICON_KEYWORDS:
        if any(word in lowered for word in keywords):
            return icon
    return TEX_GROUP_ICONS[position % len(TEX_GROUP_ICONS)]


@never_cache
@require_GET
def technics_detail(request, pk):
    technics = get_object_or_404(Technics, pk=pk, is_active=True)
    return render(request, "main/technics_detail.html", {"technics": technics})


@never_cache
@require_GET
@login_required
def deed_attachments(request, pk):
    """Hujjatning ilova fayllarini (Word/Excel/PDF) yuklab oladi:
    bitta bo'lsa o'zini, bir nechta bo'lsa ZIP arxiv qilib."""
    if not getattr(request.user, "employee", None):
        raise PermissionDenied("Employee yo'q")

    deed = get_object_or_404(Deed, pk=pk)

    items = []
    for item in deed.deedfiles_set.order_by("id"):
        try:
            if item.file and item.file.storage.exists(item.file.name):
                items.append(item)
        except Exception:
            logger.exception("DeedFiles #%s faylini tekshirishda xatolik", item.pk)

    if not items:
        messages.error(request, "Bu hujjatga ilova fayllar topilmadi")
        return redirect(request.META.get("HTTP_REFERER") or "files")

    if len(items) == 1:
        item = items[0]
        return FileResponse(
            item.file.open("rb"),
            as_attachment=True,
            filename=os.path.basename(item.file.name),
        )

    tmp = tempfile.SpooledTemporaryFile(max_size=20 * 1024 * 1024)
    used = set()
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in items:
            base = os.path.basename(item.file.name)
            name, i = base, 1
            while name in used:
                name = f"{i}_{base}"
                i += 1
            used.add(name)
            with item.file.open("rb") as src, zf.open(name, "w") as dst:
                shutil.copyfileobj(src, dst)
    tmp.seek(0)
    return FileResponse(
        tmp,
        as_attachment=True,
        filename=f"ilovalar_{deed.code or deed.pk}.zip",
        content_type="application/zip",
    )


@login_required
@require_POST
@permission_required("main.add_employee", raise_exception=True)
def employe_create(request):

    from .gateway import GatewayClient, GatewayError

    pinfl = request.POST.get("pinfl", "").strip()

    if not pinfl:
        messages.info(request, "PINFL kiritilmadi")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    if Employee.objects.filter(pinfl=pinfl).exists():
        messages.info(request, "Bu PINFL allaqachon ro'yxatda bor")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    try:
        gateway_data = GatewayClient.current_citizen(pinfl)
    except GatewayError:
        logger.exception("Gateway bilan aloqa xatosi (pinfl=%s)", pinfl)
        messages.info(
            request,
            "Tashqi tizim (Gateway) bilan aloqada vaqtinchalik xatolik yuz berdi. "
            "Birozdan keyin qayta urinib ko'ring."
        )
        return redirect(request.META.get("HTTP_REFERER", "/"))

    result = gateway_data.get("result") or {}
    positions = result.get("positions") or []

    if not positions:
        messages.info(request, "Gatewayda ish joyi topilmadi")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    assigned_data = _resolve_position(pinfl, positions)

    if not assigned_data:
        messages.info(request, "Tizimda tashkilot topilmadi")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    try:
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
                from .ranks import get_or_create_rank
                assigned_data["rank"], _ = get_or_create_rank(
                    assigned_data["_position_id"],
                    assigned_data["_position"] or f"Lavozim-{assigned_data['_position_id']}",
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


# =========================================================================
# RUXSATLAR (PERMISSIONS)
# =========================================================================

PERM_CODENAMES = {
    # Ariza
    "add_order": "main.add_order",
    "change_order": "main.change_order",
    "confirm_order": "main.confirm_order",
    # Hujjat (Dalolatnoma)
    "add_deed": "main.add_deed",
    "change_deed": "main.change_deed",
    # Ko'rish doirasi
    "all_organization": "main.all_organization",
    "all_region": "main.all_region",
    # Texnika
    "view_technics": "main.view_technics",
    "add_technics": "main.add_technics",
    "change_technics": "main.change_technics",
    "delete_technics": "main.delete_technics",
    # Material
    "view_material": "main.view_material",
    "add_material": "main.add_material",
    "change_material": "main.change_material",
    "delete_material": "main.delete_material",
    "material_service": "main.material_service",
    "all_material_employee": "main.all_material_employee",
    # Maxsus
    "boss_employee": "main.boss_employee",
    "shop_employee": "main.shop_employee",
    "status_employee": "main.status_employee",
    "permission_employee": "main.permission_employee",   # YANGI
    "report_employee": "main.report_employee",
    # Uchrashuvlar (Zoom): ko'rish (hammaning), qo'shish, o'chirish. Amallar faqat yaratgan xodimda
    "view_meeting": "chat.view_meeting",
    "add_meeting": "chat.add_meeting",
    "delete_meeting": "chat.delete_meeting",
    # Xodimlar
    "add_employee": "main.add_employee",
    "view_employee": "main.view_employee",
    "change_employee": "main.change_employee",
    "delete_employee": "main.delete_employee",
}

DEPENDENT_PERMS = {
    "view_technics": ["add_technics", "change_technics", "delete_technics"],
    "view_material": ["add_material", "change_material", "delete_material", "material_service", "all_material_employee"],
    "view_employee": ["add_employee", "change_employee", "delete_employee"],   # YANGI
    "view_meeting": ["add_meeting", "delete_meeting"],
}

SUPER_PERMS = {"all_organization", "all_region", "permission_employee", "all_material_employee"}


def _visible_perm_fields(target_employee, current_employee):

    target_org_type = (
        target_employee.organization.type
        if target_employee.organization_id else None
    )
    current_org_type = (
        current_employee.organization.type
        if current_employee.organization_id else None
    )

    visible = set(PERM_CODENAMES.keys())

    # "Ariza yaratish" - faqat target worker bo'lsa ko'rinadi
    if target_org_type != "worker":
        visible.discard("add_order")

    # "Arizani tasdiqlash" - faqat target worker BO'LMASA ko'rinadi
    if target_org_type == "worker":
        visible.discard("confirm_order")

    # "Hujjatlar" bo'limi - faqat target worker bo'lsa
    if target_org_type != "worker":
        visible.discard("add_deed")
        visible.discard("change_deed")

    # "Ko'rish doirasi" - faqat target worker bo'lsa
    if target_org_type != "worker":
        visible.discard("all_organization")
        visible.discard("all_region")

    if current_org_type != "worker":
        visible.discard("boss_employee")
        visible.discard("shop_employee")
        visible.discard("status_employee")
        visible.discard("permission_employee")   # YANGI

    # "Hisobotlarni ko'rish" va shartnoma biriktirish - faqat xizmat
    # ko'rsatuvchi (worker) tashkilot xodimlariga beriladi; buni kim
    # berayotgani (o'z tashkiloti turi) emas, NISHON xodim belgilaydi.
    if target_org_type != "worker":
        visible.discard("report_employee")

    # Mijoz (worker bo'lmagan tashkilot) xodimiga materialni sarflash va Zoom (uchrashuv) ruxsatlari berilmaydi
    if target_org_type != "worker":
        visible.discard("material_service")
        visible.discard("view_meeting")
        visible.discard("add_meeting")
        visible.discard("delete_meeting")

    return visible


def _generate_username(pinfl, first_name, last_name):

    def _clean(value):
        value = (value or "").strip().lower()
        value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
        value = re.sub(r"[^a-z0-9]", "", value)
        return value

    first = _clean(first_name)
    last = _clean(last_name)
    base = f"{first}.{last}".strip(".") or "employee"

    username = base
    if User.objects.filter(username=username).exists():
        tail = (pinfl or "")[-4:] or "1"
        username = f"{base}{tail}"

    suffix_len = 4
    while User.objects.filter(username=username).exists():
        suffix_len += 1
        tail = (pinfl or "")[-suffix_len:] or str(suffix_len)
        username = f"{base}{tail}"

    return username


# =========================================================================
# RO'YXAT SAHIFASI
# =========================================================================


# =========================================================================
# RUXSATLARNI SAQLASH
# =========================================================================


def _employee_structure_error(organization, department_id, directorate_id, division_id):
    """
    Bo'lim/boshqarma/bo'linma zanjiri mosligini va xodim tashkilotiga tegishliligini tekshiradi.
    Employee.save() bo'limga qarab tashkilotni o'zi almashtirib yuboradi — tekshiruvsiz boshqa tashkilot bo'limini
    tanlab, xodimni o'sha tashkilotga o'tkazib yuborish mumkin edi. Xato bo'lsa matn, aks holda None.
    """
    def _obj(model, raw):
        raw = (raw or "").strip()
        if not raw:
            return None
        if not raw.isdigit():
            return False
        return model.objects.filter(pk=int(raw)).first() or False

    dep = _obj(Department, department_id)
    drt = _obj(Directorate, directorate_id)
    div = _obj(Division, division_id)
    if dep is False or drt is False or div is False:
        return "Bo'lim, boshqarma yoki bo'linma topilmadi"
    if div and drt and div.directorate_id != drt.id:
        return "Bo'linma tanlangan boshqarmaga tegishli emas"
    if drt and dep and drt.department_id != dep.id:
        return "Boshqarma tanlangan bo'limga tegishli emas"
    if div and not drt:
        drt = div.directorate
    if drt and not dep:
        dep = drt.department
    if dep and organization and dep.organization_id and dep.organization_id != organization.id:
        return "Bo'lim xodimning tashkilotiga tegishli emas"
    return None


# =========================================================================
# TAHRIRLASH (asosiy ma'lumotlar)
# =========================================================================


