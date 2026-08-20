import base64
import binascii
import secrets
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db import transaction, DatabaseError
from django.db.models import F, Prefetch
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from bot.notify import send_telegram_message, rating_markup, barn_approved_markup
from .html_pdf import (
    _create_deed_for_order, deed_to_pdf_bytes, add_text_watermark_pdf_bytes, HtmlPdfError,
)
from .models import (
    Order, Goal, Employee, Organization, OrderGoal, OrderMaterial,
    Material, MaterialEmployee, MaterialUser, Technics, Deed, DeedConsent,
)
from .push_views import notify_order_status_change, notify_eligible_employees_new_order, notify_deed_sender
from .sanitizers import sanitize_deed_body

FULL_SENDER_RECEIVER_RELATED = (
    "goal", "technics", "user", "receiver", "sender",
    "sender__rank", "sender__organization", "sender__department",
    "sender__directorate", "sender__division",
    "receiver__rank", "receiver__organization", "receiver__department",
    "receiver__directorate", "receiver__division",
)

MATERIALS_PREFETCH = Prefetch(
    "materials", queryset=OrderMaterial.objects.select_related("material")
)

DEED_PREFETCH = Prefetch("order", queryset=Deed.objects.only("id", "file", "order"))


# ═══════════════════════════════════════════════════════════════════
# SENDER (worker) — ariza yuboruvchi
# ═══════════════════════════════════════════════════════════════════

@never_cache
@require_GET
@login_required
def order_sender(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Order.objects
        .filter(
            sender=employee, goal__organization__type="worker",
            status__in=["viewed", "process", "finished"],
        )
        .select_related(*FULL_SENDER_RECEIVER_RELATED)
        .prefetch_related(MATERIALS_PREFETCH)
        .order_by("-id")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
        "goal": Goal.objects.filter(organization__type="worker").order_by("id"),
    }
    return render(request, "main/order_sender.html", context)


@never_cache
@require_POST
@login_required
def order_decide(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    back_url = request.META.get("HTTP_REFERER", "/")
    action = (request.POST.get("action") or "").strip()

    if action not in {"accepted", "canceled"}:
        messages.error(request, "Noma'lum amal")
        return redirect(back_url)

    rating = None
    if action == "accepted":
        rating_raw = (request.POST.get("rating") or "").strip()
        try:
            rating = int(rating_raw)
        except (TypeError, ValueError):
            messages.error(request, "Baho noto'g'ri")
            return redirect(back_url)

        if rating not in {1, 2, 3, 4, 5}:
            messages.error(request, "Baho 1 dan 5 gacha bo'lishi kerak")
            return redirect(back_url)

    try:
        with transaction.atomic():
            try:
                order = Order.objects.select_for_update().get(pk=pk)
            except Order.DoesNotExist:
                messages.error(request, "Ariza topilmadi")
                return redirect(back_url)

            if order.sender_id != employee.id and order.user_id != employee.id:
                raise PermissionDenied("Sizda bu arizani o'zgartirish huquqi yo'q")

            update_fields = ["status"]
            order.status = action
            if rating is not None:
                order.rating = rating
                update_fields.append("rating")

            order.save(update_fields=update_fields)

    except DatabaseError:
        messages.error(request, "Xatolik yuz berdi. Qayta urinib ko'ring")
        return redirect(back_url)

    notify_order_status_change(order)

    if action == "canceled":
        messages.success(request, "Ariza bekor qilindi")
    else:
        messages.success(request, "Ariza qabul qilindi")

    return redirect(back_url)


@never_cache
@require_GET
@login_required
def order_sender_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Order.objects
        .filter(
            sender=employee, goal__organization__type="worker",
            status__in=["approved", "accepted", "canceled", "rejected"],
        )
        .select_related(*FULL_SENDER_RECEIVER_RELATED)
        .prefetch_related(MATERIALS_PREFETCH)
        .order_by("-id")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
    }
    return render(request, "main/order_sender_arxiv.html", context)


@never_cache
@require_POST
@login_required
def order_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    back_url = request.META.get("HTTP_REFERER", "/")
    goal_id = (request.POST.get("goal") or "").strip()
    body = (request.POST.get("body") or "").strip() or None

    if not goal_id.isdigit():
        messages.error(request, "Ariza turi tanlanmadi")
        return redirect(back_url)

    goal = get_object_or_404(Goal, pk=int(goal_id), organization__type="worker")

    order = Order.objects.create(
        sender_id=employee.id,
        goal=goal,
        message_sender=body,
        status="viewed",
    )

    notify_eligible_employees_new_order(order)
    messages.success(request, "Ariza Yaratish")
    return redirect(back_url)


@never_cache
@require_GET
@login_required
@permission_required("main.add_order", raise_exception=True)
def order_sender_user(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Order.objects
        .filter(user=employee, goal__organization__type="worker")
        .select_related(*FULL_SENDER_RECEIVER_RELATED)
        .prefetch_related(MATERIALS_PREFETCH)
        .order_by("-id")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
        "goal": Goal.objects.filter(organization__type="worker").order_by("id"),
        "organizations": Organization.objects.only("id", "name").order_by("id"),
    }
    return render(request, "main/order_sender_user.html", context)


@never_cache
@require_POST
@login_required
@permission_required("main.add_order", raise_exception=True)
def order_user_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    back_url = request.META.get("HTTP_REFERER", "/")
    goal_id = (request.POST.get("goal") or "").strip()
    emp_id = (request.POST.get("employee") or "").strip()
    body = (request.POST.get("body") or "").strip() or None

    if not goal_id.isdigit():
        messages.error(request, "Ariza turi tanlanmadi")
        return redirect(back_url)

    if not emp_id.isdigit():
        messages.error(request, "Xodim tanlanmadi")
        return redirect(back_url)

    goal = get_object_or_404(Goal, pk=int(goal_id), organization__type="worker")
    emp = get_object_or_404(Employee, pk=int(emp_id))

    Order.objects.create(
        sender_id=emp.id,
        user_id=employee.id,
        goal=goal,
        message_sender=body,
        status="viewed",
    )

    messages.success(request, "Ariza yuborildi")
    return redirect(back_url)


# ═══════════════════════════════════════════════════════════════════
# RECEIVER (worker) — ariza qabul qiluvchi/bajaruvchi
# ═══════════════════════════════════════════════════════════════════

@never_cache
@require_GET
@login_required
@permission_required("main.change_order", raise_exception=True)
def order_receiver(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if employee.organization.type == "client":
        raise PermissionDenied("Sizga ruxsat yo'q")

    order_goal_ids = OrderGoal.objects.filter(
        employee=employee
    ).values_list("goal_id", flat=True)

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Order.objects
        .filter(
            sender__region=employee.region,
            goal_id__in=order_goal_ids,
            goal__organization__type="worker",
            status="viewed"
        )
        .select_related(*FULL_SENDER_RECEIVER_RELATED)
        .order_by("-id")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
    }

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "main/partials/order_receiver_rows.html", context)

    return render(request, "main/order_receiver.html", context)


@never_cache
@require_POST
@login_required
@permission_required("main.change_order", raise_exception=True)
def order_accepted(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if employee.organization.type == "client":
        raise PermissionDenied("Sizga ruxsat yo'q")

    back_url = request.META.get("HTTP_REFERER") or "/"

    order_goal_ids = set(
        OrderGoal.objects.filter(employee=employee).values_list("goal_id", flat=True)
    )

    def is_order_eligible(order):
        return (
            order.status == "viewed"
            and order.receiver_id is None
            and order.goal_id in order_goal_ids
            and order.goal.organization.type == "worker"
            and order.sender_id is not None
            and order.sender.region_id == employee.region_id
        )

    order = get_object_or_404(Order.objects.select_related("goal__organization", "sender"), pk=pk)

    if not is_order_eligible(order):
        messages.error(request, "Bu arizani qabul qilish huquqingiz yo'q yoki u allaqachon qabul qilingan")
        return redirect(back_url)

    try:
        with transaction.atomic():
            order = (
                Order.objects
                .select_for_update(of=("self",))
                .select_related("goal__organization", "sender")
                .get(pk=pk)
            )

            if not is_order_eligible(order):
                messages.error(request, "Bu arizani qabul qilish huquqingiz yo'q yoki u allaqachon qabul qilingan")
                return redirect(back_url)

            order.status = "process"
            order.receiver = employee
            order.save(update_fields=["status", "receiver"])

    except DatabaseError:
        messages.error(request, "Xatolik yuz berdi. Qayta urinib ko'ring")
        return redirect(back_url)

    notify_order_status_change(order)

    if order.sender_id and order.sender.telegram_chat:
        send_telegram_message(
            order.sender.telegram_chat,
            f"<b>🔔 Yangi bildirishnoma</b>\n\n"
            f"✅ ATMga yuborgan #{order.id} - arizangiz qabul qilindi.\n"
            f"👤 <b>Bajaruvchi:</b> {employee.full_name}\n\n"
            f"📅 <b>Vaqt:</b> {timezone.localtime(timezone.now()).strftime('%Y.%m.%d %H:%M:%S')}",
        )

    messages.success(request, "Ariza muvaffaqiyatli qabul qilindi")
    return redirect("order_receiver_activ")


@never_cache
@require_GET
@login_required
@permission_required("main.change_order", raise_exception=True)
def order_receiver_activ(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.organization, "type", None) == "client":
        raise PermissionDenied("Sizga ruxsat yo'q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Order.objects
        .filter(receiver=employee,
                goal__organization__type="worker",
                goal__organization=employee.organization,
                status__in=["process", "finished"], )
        .select_related(*FULL_SENDER_RECEIVER_RELATED)
        .prefetch_related(MATERIALS_PREFETCH)
        .order_by("-id")
    )

    materials = (
        Material.objects
        .filter(
            employee__in=MaterialUser.objects.filter(
                receiver=employee
            ).values("sender"),
            is_active=True,
        )
        .select_related("unit", "employee")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
        "materials": materials,
    }
    return render(request, "main/order_receiver_activ.html", context)


@never_cache
@require_POST
@login_required
@permission_required("main.change_order", raise_exception=True)
def order_material_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.organization, "type", None) == "client":
        raise PermissionDenied("Sizga ruxsat yo'q")

    back_url = request.META.get("HTTP_REFERER") or "/"
    order_id = (request.POST.get("order_id") or "").strip()
    technics_id = (request.POST.get("technics_id") or "").strip()
    material_ids = request.POST.getlist("material_id[]")
    numbers = request.POST.getlist("number[]")

    if not order_id.isdigit():
        messages.error(request, "Ariza ID topilmadi")
        return redirect(back_url)

    if technics_id and not technics_id.isdigit():
        messages.error(request, "Texnika ID noto'g'ri")
        return redirect(back_url)

    if technics_id:
        if not Technics.objects.filter(pk=int(technics_id)).exists():
            messages.error(request, "Texnika topilmadi")
            return redirect(back_url)

    try:
        with transaction.atomic():
            order = get_object_or_404(
                Order.objects.select_for_update(),
                id=int(order_id)
            )

            if not order.receiver_id:
                messages.error(request, "Ariza hali hech kimga biriktirilmagan")
                return redirect(back_url)

            if order.receiver_id != employee.id:
                messages.error(request, "Bu arizani faqat uni qabul qilgan xodim yakunlay oladi")
                return redirect(back_url)

            if order.status not in ["process", "finished"]:
                messages.error(request, "Bu ariza yakunlanishi mumkin emas")
                return redirect(back_url)

            if technics_id:
                order.technics_id = int(technics_id)

            pairs = []
            seen = set()

            for m_id, num in zip(material_ids, numbers):
                if not m_id:
                    continue
                try:
                    m_id = int(m_id)
                    n = int(num or 1)
                except (ValueError, TypeError):
                    messages.error(request, "Material yoki son noto'g'ri kiritilgan")
                    return redirect(back_url)

                if n <= 0:
                    messages.error(request, "Material soni 0 yoki manfiy bo'lishi mumkin emas")
                    return redirect(back_url)

                if m_id in seen:
                    messages.error(request, "Bir xil materialni bir necha marta kiritmang")
                    return redirect(back_url)

                seen.add(m_id)
                pairs.append((m_id, n))

            if pairs:
                materials = list(
                    Material.objects
                    .select_for_update()
                    .filter(id__in=[m for m, _ in pairs], is_active=True)
                    .order_by("id")
                )
                materials_map = {m.id: m for m in materials}

                for m_id, n in pairs:
                    mat = materials_map.get(m_id)
                    if not mat:
                        messages.error(request, "Material topilmadi yoki faol emas")
                        return redirect(back_url)
                    if (mat.number or 0) < n:
                        messages.error(request, f'"{mat.name}" yetarli emas. Omborda {mat.number} dona bor')
                        return redirect(back_url)

                order_materials = []
                for m_id, n in pairs:
                    mat = materials_map[m_id]
                    order_materials.append(OrderMaterial(order=order, material=mat, number=n))
                    Material.objects.filter(pk=mat.pk).update(number=F("number") - n)

                OrderMaterial.objects.bulk_create(order_materials)

            order.status = "finished"
            order.save(update_fields=["status", "technics_id"])

    except DatabaseError:
        messages.error(request, "Xatolik yuz berdi. Qayta urinib ko'ring")
        return redirect(back_url)

    notify_order_status_change(order)

    if order.sender_id and order.sender.telegram_chat:
        send_telegram_message(
            order.sender.telegram_chat,
            f"<b>🔔 Yangi bildirishnoma</b>\n\n"
            f"✅ ATMga yuborgan #{order.id} - arizangiz bajarildi.\n"
            f"👤 <b>Bajaruvchi:</b> {employee.full_name}\n\n"
            f"📅 <b>Vaqt:</b> {timezone.localtime(timezone.now()).strftime('%Y.%m.%d %H:%M:%S')}\n\n"
            f"⭐ <b>Iltimos, xizmat sifatini baholang:</b>",
            reply_markup=rating_markup(order.id),
        )

    messages.success(request, "Ariza muvaffaqiyatli yakunlandi")
    return redirect(back_url)


@never_cache
@require_GET
@login_required
@permission_required("main.change_order", raise_exception=True)
def order_receiver_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.organization, "type", None) == "client":
        raise PermissionDenied("Sizga ruxsat yo'q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Order.objects
        .filter(receiver=employee, goal__organization__type="worker",
                status__in=["approved", "accepted", "canceled", "rejected"], )
        .select_related(*FULL_SENDER_RECEIVER_RELATED)
        .prefetch_related(MATERIALS_PREFETCH, DEED_PREFETCH)
        .order_by("-date_edit")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
    }
    return render(request, "main/order_receiver_arxiv.html", context)


# ═══════════════════════════════════════════════════════════════════
# RECEIVER — hujjat (deed) imzolashga yuborish
# ═══════════════════════════════════════════════════════════════════

@never_cache
@require_GET
@login_required
@permission_required("main.change_order", raise_exception=True)
def order_receiver_deed(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if not employee.organization or employee.organization.type == "client":
        raise PermissionDenied("Sizga ruxsat yo'q")

    order = get_object_or_404(
        Order.objects.select_related(
            "sender", "sender__organization",
            "sender__department", "receiver", "receiver__rank",
            "technics",
        ).prefetch_related(
            Prefetch("materials", queryset=OrderMaterial.objects.select_related("material", "material__unit"))
        ),
        pk=pk,
    )

    if order.receiver_id != employee.id:
        raise PermissionDenied("Sizga ruxsat yo'q")

    if not order.sender_id:
        raise PermissionDenied("Ariza jo'natuvchisi yo'q")

    employees = (
        Employee.objects
        .filter(organization=order.sender.organization)
        .select_related("organization", "rank")
    )

    context = {
        "order": order,
        "employees": employees,
        "today": timezone.now(),
    }
    return render(request, "main/order_receiver_deed.html", context)


@never_cache
@require_POST
@login_required
@permission_required("main.change_order", raise_exception=True)
def order_receiver_deed_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if not employee.organization or employee.organization.type == "client":
        raise PermissionDenied("Sizga ruxsat yo'q")

    back_url = request.META.get("HTTP_REFERER") or "/"
    order_id = (request.POST.get("order") or "").strip()
    sender_id = (request.POST.get("sender") or "").strip()
    message = (request.POST.get("message") or "").strip() or None

    body_encoded = (request.POST.get("body_encoded") or "").strip()
    body = ""
    if body_encoded:
        try:
            body = base64.b64decode(body_encoded).decode("utf-8").strip()
        except (binascii.Error, UnicodeDecodeError, ValueError):
            body = ""

    if body:
        body = sanitize_deed_body(body)

    order = (
        Order.objects
        .filter(id=order_id)
        .select_related("sender", "sender__organization", "receiver")
        .first()
        if order_id.isdigit() else None
    )
    if not order:
        messages.error(request, "Ariza topilmadi")
        return redirect(back_url)

    if order.receiver_id != employee.id:
        raise PermissionDenied("Sizga ruxsat yo'q")

    if not order.sender_id:
        messages.error(request, "Ariza jo'natuvchisi yo'q")
        return redirect(back_url)

    sender = (
        Employee.objects
        .filter(id=sender_id, organization=order.sender.organization)
        .first()
        if sender_id.isdigit() else None
    )
    if not sender:
        messages.error(request, "Imzolovchi xodim tanlanmadi")
        return redirect(back_url)

    if not body:
        messages.error(request, "Hujjat matni bo'sh bo'lmasin")
        return redirect(back_url)

    try:
        with transaction.atomic():
            deed = Deed.objects.create(
                organization=order.sender.organization,
                sender_id=sender.id,
                user_id=employee.id,
                order_id=order.id,
                message_user=message,
                body=body,
                status='act',
            )

            if order.sender_id != sender.id:
                sender_consent = DeedConsent.objects.create(
                    deed=deed, employee=order.sender, status="approved",
                )
                if order.date_approved:
                    DeedConsent.objects.filter(pk=sender_consent.pk).update(
                        date_creat=order.date_approved
                    )
            if order.receiver_id != sender.id:
                receiver_consent = DeedConsent.objects.create(
                    deed=deed, employee=order.receiver, status="approved",
                )
                if order.date_finished:
                    DeedConsent.objects.filter(pk=receiver_consent.pk).update(
                        date_creat=order.date_finished
                    )

            pdf_bytes = deed_to_pdf_bytes(deed)
            pdf_bytes = add_text_watermark_pdf_bytes(pdf_bytes, "TASDIQLANMAGAN")
            pdf_name = f"akt_{timezone.now().strftime('%Y%m%d')}_{secrets.token_urlsafe(6)}.pdf"
            deed.file.save(pdf_name, ContentFile(pdf_bytes), save=True)

    except HtmlPdfError as e:
        messages.error(request, f"Hujjat yaratilmadi: {e}. Qayta urinib ko'ring")
        return redirect(back_url)

    notify_deed_sender(deed)

    messages.success(request, "Imzolashga yuborildi")
    return redirect("contact_user")


# ═══════════════════════════════════════════════════════════════════
# SENDER (client) — "barn"
# ═══════════════════════════════════════════════════════════════════

@never_cache
@require_GET
@login_required
def order_sender_barn(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.organization, "type", None) == "worker":
        raise PermissionDenied("Sizga ruxsat yo'q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Order.objects
        .filter(
            sender=employee,
            goal__organization__type="client",
            status__in=["viewed", "process", "finished", "approved"],
        )
        .select_related(*FULL_SENDER_RECEIVER_RELATED)
        .prefetch_related(MATERIALS_PREFETCH)
        .order_by("-id")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
    }
    return render(request, "main/order_sender_barn.html", context)


@never_cache
@require_POST
@login_required
def order_decide_barn(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.organization, "type", None) == "worker":
        raise PermissionDenied("Sizga ruxsat yo'q")

    back_url = request.META.get("HTTP_REFERER", "/")
    action = (request.POST.get("action") or "").strip()

    if action not in {"canceled", "accepted"}:
        messages.error(request, "Noma'lum amal")
        return redirect(back_url)

    order = get_object_or_404(Order, pk=pk)

    if order.sender_id != employee.id:
        messages.error(request, "Ariza sizga tegishli emas")
        return redirect(back_url)

    if action == "canceled" and order.status in {"accepted", "approved", "canceled", "rejected"}:
        messages.error(request, "Bu ariza bo'yicha amal bajarilgan")
        return redirect(back_url)

    if action == "accepted" and order.status != "approved":
        messages.error(request, "Bu ariza hozir qabul qilinmaydi")
        return redirect(back_url)

    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=pk)

            if action == "canceled" and order.status in {"accepted", "approved", "canceled", "rejected"}:
                messages.error(request, "Bu ariza bo'yicha amal bajarilgan")
                return redirect(back_url)

            if action == "accepted" and order.status != "approved":
                messages.error(request, "Bu ariza hozir qabul qilinmaydi")
                return redirect(back_url)

            order.status = action
            order.save(update_fields=["status"])

    except DatabaseError:
        messages.error(request, "Xatolik yuz berdi. Qayta urinib ko'ring")
        return redirect(back_url)

    if action == "accepted" and order.materials.exists():
        try:
            _create_deed_for_order(order, request)
        except HtmlPdfError:
            messages.warning(
                request,
                "Ariza qabul qilindi, lekin hujjat yaratilmadi. "
                "Hujjatni keyinroq qayta yaratishga urinib ko'ring."
            )
        except Exception:
            messages.warning(
                request,
                "Ariza qabul qilindi, lekin hujjatga imzo/QR urishda xatolik yuz berdi. "
                "Hujjatni keyinroq tekshiring."
            )

    notify_order_status_change(order)

    if action == "canceled":
        messages.success(request, "Ariza bekor qilindi")
    else:
        messages.success(request, "Ariza yakunlandi")

    return redirect(back_url)


@never_cache
@require_GET
@login_required
def order_sender_arxiv_barn(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.organization, "type", None) == "worker":
        raise PermissionDenied("Sizga ruxsat yo'q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Order.objects
        .filter(
            sender=employee,
            goal__organization__type="client",
            status__in=["accepted", "canceled", "rejected"],
        )
        .select_related(*FULL_SENDER_RECEIVER_RELATED)
        .prefetch_related(MATERIALS_PREFETCH, DEED_PREFETCH)
        .order_by("-id")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
    }
    return render(request, "main/order_sender_arxiv_barn.html", context)


@never_cache
@require_GET
@login_required
def order_sender_material_barn(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.organization, "type", None) == "worker":
        raise PermissionDenied("Sizga ruxsat yo'q")

    name = request.GET.get("name", "").strip()
    page_number = request.GET.get("page", 1)

    category_ids = MaterialEmployee.objects.filter(
        employee=employee
    ).values_list("category_id", flat=True)

    orders_qs = (
        Material.objects
        .filter(organization=employee.organization, is_active=True)
        .filter(category_id__in=category_ids)
        .select_related("organization", "unit")
        .order_by("-id")
    )

    if name:
        orders_qs = orders_qs.filter(name__icontains=name)

    cart_material_ids = set(
        OrderMaterial.objects.filter(
            order__isnull=True, user=employee, material__isnull=False,
        ).values_list("material_id", flat=True)
    )

    paginator = Paginator(orders_qs, 20)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
        "cart_material_ids": cart_material_ids,
    }
    return render(request, "main/order_sender_material_barn.html", context)


@never_cache
@require_GET
@login_required
def order_sender_basket_barn(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.organization, "type", None) == "worker":
        raise PermissionDenied("Sizga ruxsat yo'q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        OrderMaterial.objects
        .filter(order__isnull=True, user=employee, material__isnull=False)
        .select_related("order", "user", "material", "material__unit")
        .order_by("-id")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
        "goal": Goal.objects.filter(organization__type="client").order_by("id"),
    }
    return render(request, "main/order_sender_basket_barn.html", context)


@never_cache
@require_POST
@login_required
def create_order_sender_from(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.organization, "type", None) == "worker":
        raise PermissionDenied("Sizga ruxsat yo'q")

    back_url = request.META.get("HTTP_REFERER", "/")
    body = (request.POST.get("body") or "").strip() or None
    goal_id = (request.POST.get("goal") or "").strip()

    if not goal_id.isdigit():
        messages.error(request, "Ariza turi tanlanmadi")
        return redirect(back_url)

    goal = get_object_or_404(Goal, pk=int(goal_id), organization__type="client")

    with transaction.atomic():
        cart_items = list(
            OrderMaterial.objects
            .select_for_update(of=("self",))
            .filter(user=employee, order__isnull=True, material__isnull=False)
            .select_related("material")
        )

        if not cart_items:
            messages.error(request, "Savat bo'sh — ariza yaratib bo'lmaydi")
            return redirect(back_url)

        order = Order.objects.create(
            goal=goal, sender=employee, message_sender=body, status="viewed",
        )

        for item in cart_items:
            number = request.POST.get(f"number_{item.id}")
            if number and number.isdigit():
                item.number = max(int(number), 1)
            item.order = order

        OrderMaterial.objects.bulk_update(cart_items, ["number", "order"])

    notify_eligible_employees_new_order(order)

    messages.success(request, "Ariza yuborildi")
    return redirect("order_sender_barn")


# ═══════════════════════════════════════════════════════════════════
# RECEIVER — "barn"
# ═══════════════════════════════════════════════════════════════════

@never_cache
@require_GET
@login_required
@permission_required("main.change_order", raise_exception=True)
def order_receiver_barn(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.organization, "type", None) == "worker":
        raise PermissionDenied("Sizga ruxsat yo'q")

    order_goal_ids = OrderGoal.objects.filter(
        employee=employee
    ).values_list("goal_id", flat=True)

    page_number = request.GET.get("page", 1)

    if employee.region_id:
        orders_qs = (
            Order.objects
            .filter(
                goal__organization__type="client",
                goal__organization=employee.organization,
                goal_id__in=order_goal_ids,
                sender__region_id=employee.region_id,
                status="viewed",
            )
            .select_related(*FULL_SENDER_RECEIVER_RELATED)
            .order_by("-id")
        )
    else:
        orders_qs = Order.objects.none()

    paginator = Paginator(orders_qs, 20)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
    }

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "main/partials/order_receiver_barn_rows.html", context)

    return render(request, "main/order_receiver_barn.html", context)


@never_cache
@require_POST
@login_required
@permission_required("main.change_order", raise_exception=True)
def order_accepted_barn(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.organization, "type", None) == "worker":
        raise PermissionDenied("Sizga ruxsat yo'q")

    back_url = request.META.get("HTTP_REFERER") or "/"
    action = (request.POST.get("action") or "").strip()

    if action not in {"process", "rejected"}:
        messages.error(request, "Noto'g'ri amal tanlandi")
        return redirect(back_url)

    order_goal_ids = set(
        OrderGoal.objects.filter(employee=employee).values_list("goal_id", flat=True)
    )

    def is_order_eligible(order):
        return (
            order.status == "viewed"
            and order.goal_id in order_goal_ids
            and order.goal.organization_id == employee.organization_id
            and order.goal.organization.type == "client"
            and order.sender_id is not None
            and order.sender.region_id == employee.region_id
        )

    order = get_object_or_404(
        Order.objects.select_related("goal__organization", "sender"), pk=pk
    )

    if not is_order_eligible(order):
        messages.error(request, "Ariza topilmadi yoki allaqachon ko'rib chiqilgan")
        return redirect(back_url)

    try:
        with transaction.atomic():
            order = (
                Order.objects
                .select_for_update(of=("self",))
                .select_related("goal__organization", "sender")
                .get(pk=pk)
            )

            if not is_order_eligible(order):
                messages.error(request, "Ariza allaqachon ko'rib chiqilgan")
                return redirect(back_url)

            order.receiver = employee
            order.status = action
            order.save(update_fields=["status", "receiver"])

    except DatabaseError:
        messages.error(request, "Xatolik yuz berdi. Qayta urinib ko'ring")
        return redirect(back_url)

    notify_order_status_change(order)

    if order.sender_id and order.sender.telegram_chat:
        if action == "process":
            send_telegram_message(
                order.sender.telegram_chat,
                f"<b>🔔 Yangi bildirishnoma</b>\n\n"
                f"✅ Omborxonaga yuborilgan #{order.id} - arizangiz qabul qilindi.\n"
                f"👤 <b>Bajaruvchi:</b> {employee.full_name}\n\n"
                f"📅 <b>Vaqt:</b> {timezone.localtime(timezone.now()).strftime('%Y.%m.%d %H:%M:%S')}",
            )
        else:
            send_telegram_message(
                order.sender.telegram_chat,
                f"<b>🔔 Yangi bildirishnoma</b>\n\n"
                f"❌ Omborxonaga yuborilgan #{order.id} - arizangiz rad etildi.\n"
                f"👤 <b>Ko'rib chiqdi:</b> {employee.full_name}\n\n"
                f"📅 <b>Vaqt:</b> {timezone.localtime(timezone.now()).strftime('%Y.%m.%d %H:%M:%S')}",
            )

    if action == "process":
        messages.success(request, "Ariza qabul qilindi")
        return redirect("order_receiver_activ_barn")

    messages.success(request, "Ariza rad etildi")
    return redirect(back_url)


@never_cache
@require_GET
@login_required
@permission_required("main.change_order", raise_exception=True)
def order_receiver_activ_barn(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.organization, "type", None) == "worker":
        raise PermissionDenied("Sizga ruxsat yo'q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Order.objects
        .filter(
            goal__organization__type="client",
            receiver=employee,
            status__in=["process", "finished"],
        )
        .select_related(*FULL_SENDER_RECEIVER_RELATED)
        .prefetch_related(MATERIALS_PREFETCH)
        .order_by("-id")
    )

    materials = (
        Material.objects
        .filter(organization=employee.organization, is_active=True)
        .select_related("unit")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
        "materials": materials,
    }
    return render(request, "main/order_receiver_activ_barn.html", context)


@never_cache
@require_POST
@login_required
@permission_required("main.change_order", raise_exception=True)
def order_material_barn(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.organization, "type", None) == "worker":
        raise PermissionDenied("Sizga ruxsat yo'q")

    back_url = request.META.get("HTTP_REFERER", "/")
    order_id = (request.POST.get("order_id") or "").strip()
    date = (request.POST.get("date") or "").strip()
    ordermaterial_ids = request.POST.getlist("ordermaterial_id[]")
    givens = request.POST.getlist("given[]")

    if not order_id.isdigit():
        messages.error(request, "Ariza ID noto'g'ri")
        return redirect(back_url)

    if len(ordermaterial_ids) != len(givens):
        messages.error(request, "Yuborilgan ma'lumotlar mos emas")
        return redirect(back_url)

    if len(ordermaterial_ids) != len(set(ordermaterial_ids)):
        messages.error(request, "Takroriy materiallar yuborildi")
        return redirect(back_url)

    date_display = ""
    if date:
        try:
            parsed_dt = datetime.strptime(date, "%Y-%m-%dT%H:%M")
            date_display = parsed_dt.strftime("%d.%m.%Y %H:%M")
        except ValueError:
            messages.error(request, "Sana formati noto'g'ri")
            return redirect(back_url)

    if date_display:
        body = f"Materiallarni ombordan {date_display} da qabul qilib olishingiz mumkin"
    else:
        body = "Materiallarni ombordan qabul qilib olishingiz mumkin"

    try:
        with transaction.atomic():
            order = get_object_or_404(
                Order.objects.select_for_update(of=("self",)).select_related("goal__organization"),
                pk=int(order_id)
            )

            if order.receiver_id != employee.id:
                messages.error(request, "Bu arizani faqat uni qabul qilgan xodim yakunlay oladi")
                return redirect(back_url)

            if not order.goal or order.goal.organization_id != employee.organization_id:
                messages.error(request, "Bu ariza sizning tashkilotingizga tegishli emas")
                return redirect(back_url)

            if order.status not in ["process", "finished"]:
                messages.error(request, "Bu ariza yakunlanishi mumkin emas")
                return redirect(back_url)

            order_materials = list(
                OrderMaterial.objects
                .select_for_update()
                .filter(order=order, id__in=ordermaterial_ids)
            )

            om_map = {str(item.id): item for item in order_materials}

            if len(om_map) != len(ordermaterial_ids):
                messages.error(request, "Ba'zi materiallar topilmadi")
                return redirect(back_url)

            material_ids = [om.material_id for om in order_materials if om.material_id]
            if len(material_ids) != len(order_materials):
                messages.error(request, "Ba'zi materiallarga bog'lanish topilmadi")
                return redirect(back_url)

            materials = list(Material.objects.select_for_update().filter(id__in=material_ids))
            material_map = {m.id: m for m in materials}

            if len(material_map) != len(set(material_ids)):
                messages.error(request, "Ba'zi materiallar bazada topilmadi")
                return redirect(back_url)

            ordermaterial_to_update = []
            material_changed_ids = set()

            for om_id, given_value in zip(ordermaterial_ids, givens):
                om = om_map.get(str(om_id))
                if not om:
                    messages.error(request, f"Arizadagi material topilmadi: {om_id}")
                    return redirect(back_url)

                material = material_map.get(om.material_id)
                if not material:
                    messages.error(request, "Material topilmadi")
                    return redirect(back_url)

                try:
                    given = int(given_value)
                except (TypeError, ValueError):
                    messages.error(request, f"{material.name} uchun beriladigan son noto'g'ri")
                    return redirect(back_url)

                if given <= 0:
                    messages.error(request, f"{material.name} uchun beriladigan son manfiy bo'lishi mumkin emas")
                    return redirect(back_url)

                old_given = om.given or 0
                delta = given - old_given

                if delta > 0 and material.number < delta:
                    messages.error(
                        request,
                        f"{material.name} omborda yetarli emas. Omborda: {material.number}, kerak: {delta}"
                    )
                    return redirect(back_url)

                material.number -= delta
                material_changed_ids.add(material.id)
                om.given = given
                ordermaterial_to_update.append(om)

            for mid in material_changed_ids:
                if material_map[mid].number < 0:
                    messages.error(request, f"{material_map[mid].name} uchun qoldiq manfiy bo'lib qoldi")
                    return redirect(back_url)

            if ordermaterial_to_update:
                OrderMaterial.objects.bulk_update(ordermaterial_to_update, ["given"])

            changed_materials = [material_map[mid] for mid in material_changed_ids]
            if changed_materials:
                Material.objects.bulk_update(changed_materials, ["number"])

            order.status = "finished"
            order.message_receiver = body
            order.save(update_fields=["status", "message_receiver"])

    except DatabaseError:
        messages.error(request, "Xatolik yuz berdi. Qayta urinib ko'ring")
        return redirect(back_url)

    notify_order_status_change(order)

    if order.sender_id and order.sender.telegram_chat:
        send_telegram_message(
            order.sender.telegram_chat,
            f"<b>🔔 Yangi bildirishnoma</b>\n\n"
            f"✅ Omborxonaga yuborilgan #{order.id} - arizangiz bajarildi.\n"
            f"👤 <b>Bajaruvchi:</b> {employee.full_name}\n\n"
            f"📅 <b>Vaqt:</b> {timezone.localtime(timezone.now()).strftime('%Y.%m.%d %H:%M:%S')}",
        )

    messages.success(request, "Ariza tasdiqlandi")
    return redirect(back_url)


@never_cache
@require_GET
@login_required
@permission_required("main.change_order", raise_exception=True)
def order_receiver_arxiv_barn(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.organization, "type", None) == "worker":
        raise PermissionDenied("Sizga ruxsat yo'q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Order.objects
        .filter(
            goal__organization__type="client",
            receiver=employee,
            status__in=["approved", "accepted", "canceled", "rejected"],
        )
        .select_related(*FULL_SENDER_RECEIVER_RELATED)
        .prefetch_related(MATERIALS_PREFETCH, DEED_PREFETCH)
        .order_by("-id")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
    }
    return render(request, "main/order_receiver_arxiv_barn.html", context)


# ═══════════════════════════════════════════════════════════════════
# AGREMENT — tasdiqlovchi
# ═══════════════════════════════════════════════════════════════════

@never_cache
@require_GET
@login_required
@permission_required("main.confirm_order", raise_exception=True)
def order_agrement(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.organization, "type", None) == "worker":
        raise PermissionDenied("Sizga ruxsat yo'q")

    page_number = request.GET.get("page", 1)

    if employee.region_id:
        orders_qs = (
            Order.objects
            .filter(
                goal__organization__type="client",
                goal__organization=employee.organization,
                receiver__region_id=employee.region_id,
                status="finished",
            )
            .select_related(*FULL_SENDER_RECEIVER_RELATED)
            .prefetch_related(MATERIALS_PREFETCH)
            .order_by("-id")
        )
    else:
        orders_qs = Order.objects.none()

    paginator = Paginator(orders_qs, 20)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
    }
    return render(request, "main/order_agrement.html", context)


@never_cache
@require_POST
@login_required
@permission_required("main.confirm_order", raise_exception=True)
def order_agrement_material(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.organization, "type", None) == "worker":
        raise PermissionDenied("Sizga ruxsat yo'q")

    back_url = request.META.get("HTTP_REFERER", "/")
    order_id = (request.POST.get("order_id") or "").strip()
    action = (request.POST.get("action") or "").strip()
    ordermaterial_ids = request.POST.getlist("ordermaterial_id[]")
    givens = request.POST.getlist("given[]")

    if not order_id.isdigit():
        messages.error(request, "Ariza ID noto'g'ri")
        return redirect(back_url)

    if action not in ["approved", "rejected"]:
        messages.error(request, "Amal noto'g'ri")
        return redirect(back_url)

    if action == "approved":
        if len(ordermaterial_ids) != len(givens):
            messages.error(request, "Yuborilgan ma'lumotlar mos emas")
            return redirect(back_url)
        if len(ordermaterial_ids) != len(set(ordermaterial_ids)):
            messages.error(request, "Takroriy materiallar yuborildi")
            return redirect(back_url)
        if not all(str(x).isdigit() for x in ordermaterial_ids):
            messages.error(request, "Material ID noto'g'ri")
            return redirect(back_url)

    try:
        with transaction.atomic():
            order = get_object_or_404(
                Order.objects.select_for_update(of=("self",)).select_related("goal__organization", "receiver"),
                pk=int(order_id)
            )

            if not order.goal or order.goal.organization_id != employee.organization_id:
                messages.error(request, "Bu ariza sizning tashkilotingizga tegishli emas")
                return redirect(back_url)

            if not order.receiver or order.receiver.region_id != employee.region_id:
                messages.error(request, "Bu ariza sizning hududingizga tegishli emas")
                return redirect(back_url)

            if order.status != "finished":
                messages.error(request, "Bu arizani tasdiqlash yoki rad etish mumkin emas")
                return redirect(back_url)

            if action == "rejected":
                order_materials = list(
                    OrderMaterial.objects
                    .select_for_update(of=("self",))
                    .filter(order=order)
                    .select_related("material")
                )

                material_ids = [
                    om.material_id for om in order_materials
                    if om.material_id and (om.given or 0) > 0
                ]
                materials = list(Material.objects.select_for_update().filter(id__in=material_ids))
                material_map = {m.id: m for m in materials}

                changed_materials = []
                changed_order_materials = []

                for om in order_materials:
                    old_given = om.given or 0
                    if old_given > 0:
                        mat = material_map.get(om.material_id)
                        if mat:
                            mat.number = (mat.number or 0) + old_given
                            changed_materials.append(mat)
                        om.given = 0
                        changed_order_materials.append(om)

                if changed_materials:
                    Material.objects.bulk_update(changed_materials, ["number"])
                if changed_order_materials:
                    OrderMaterial.objects.bulk_update(changed_order_materials, ["given"])

                order.status = "rejected"
                order.user = employee
                order.save(update_fields=["status", "user"])

            else:
                order_materials = list(
                    OrderMaterial.objects
                    .select_for_update(of=("self",))
                    .filter(order=order, id__in=ordermaterial_ids)
                    .select_related("material")
                )
                om_map = {str(item.id): item for item in order_materials}

                if len(om_map) != len(ordermaterial_ids):
                    messages.error(request, "Ba'zi materiallar topilmadi")
                    return redirect(back_url)

                material_ids = [om.material_id for om in order_materials if om.material_id]
                if len(material_ids) != len(order_materials):
                    messages.error(request, "Ba'zi materiallarga bog'lanish topilmadi")
                    return redirect(back_url)

                materials = list(Material.objects.select_for_update().filter(id__in=material_ids))
                material_map = {m.id: m for m in materials}

                if len(material_map) != len(set(material_ids)):
                    messages.error(request, "Ba'zi materiallar bazada topilmadi")
                    return redirect(back_url)

                ordermaterial_to_update = []
                material_changed_ids = set()

                for om_id, given_value in zip(ordermaterial_ids, givens):
                    om = om_map.get(str(om_id))
                    material = material_map.get(om.material_id)

                    try:
                        given = int(given_value)
                    except (TypeError, ValueError):
                        messages.error(request, f"{material.name} uchun beriladigan son noto'g'ri")
                        return redirect(back_url)

                    if given < 0:
                        messages.error(request, f"{material.name} uchun beriladigan son manfiy bo'lishi mumkin emas")
                        return redirect(back_url)

                    old_given = om.given or 0
                    delta = given - old_given

                    if delta > 0 and (material.number or 0) < delta:
                        messages.error(
                            request,
                            f"{material.name} omborda yetarli emas. Omborda: {material.number}, kerak: {delta}"
                        )
                        return redirect(back_url)

                    material.number = (material.number or 0) - delta
                    material_changed_ids.add(material.id)
                    om.given = given
                    ordermaterial_to_update.append(om)

                for mid in material_changed_ids:
                    if material_map[mid].number < 0:
                        messages.error(request, f"{material_map[mid].name} uchun qoldiq manfiy bo'lib qoldi")
                        return redirect(back_url)

                if ordermaterial_to_update:
                    OrderMaterial.objects.bulk_update(ordermaterial_to_update, ["given"])

                changed_materials = [material_map[mid] for mid in material_changed_ids]
                if changed_materials:
                    Material.objects.bulk_update(changed_materials, ["number"])

                order.status = "approved"
                order.user = employee
                order.save(update_fields=["status", "user"])

    except DatabaseError:
        messages.error(request, "Xatolik yuz berdi. Qayta urinib ko'ring")
        return redirect(back_url)

    notify_order_status_change(order)

    if order.sender_id and order.sender.telegram_chat:
        if action == "approved":
            send_telegram_message(
                order.sender.telegram_chat,
                f"<b>🔔 Yangi bildirishnoma</b>\n\n"
                f"✅ Omborxonaga yuborilgan #{order.id} - arizangiz tasdiqlandi.\n"
                f"⚠️ <b>{order.message_receiver}</b>\n"
                f"👤 <b>Bajaruvchi:</b> {order.receiver.full_name}\n"
                f"✔️ <b>Tasdiqlovchi:</b> {employee.full_name}\n\n"
                f"📅 <b>Vaqt:</b> {timezone.localtime(timezone.now()).strftime('%Y.%m.%d %H:%M:%S')}",
                reply_markup=barn_approved_markup(order.id),
            )
        else:
            send_telegram_message(
                order.sender.telegram_chat,
                f"<b>🔔 Yangi bildirishnoma</b>\n\n"
                f"❌ Omborxonaga yuborilgan #{order.id} - arizangiz rad etildi.\n"
                f"👤 <b>Ko'rib chiqdi:</b> {employee.full_name}\n\n"
                f"📅 <b>Vaqt:</b> {timezone.localtime(timezone.now()).strftime('%Y.%m.%d %H:%M:%S')}",
            )

    if action == "rejected":
        messages.success(request, "Ariza rad etildi. Materiallar omborga qaytarildi")
    else:
        messages.success(request, "Ariza tasdiqlandi")

    return redirect("order_agrement_arxiv")


@never_cache
@require_GET
@login_required
@permission_required("main.confirm_order", raise_exception=True)
def order_agrement_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.organization, "type", None) == "worker":
        raise PermissionDenied("Sizga ruxsat yo'q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Order.objects
        .filter(
            user=employee,
            goal__organization__type="client",
            status__in=["approved", "accepted", "canceled", "rejected"],
        )
        .select_related(*FULL_SENDER_RECEIVER_RELATED)
        .prefetch_related(MATERIALS_PREFETCH, DEED_PREFETCH)
        .order_by("-id")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
    }
    return render(request, "main/order_agrement_arxiv.html", context)