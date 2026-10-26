import secrets
from django.db.models import Q
from django.contrib.auth.models import Permission
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from .html_pdf import deed_to_pdf_bytes, add_text_watermark_pdf_bytes, HtmlPdfError
from .models import Order, Employee, OrderGoal, OrderMaterial, Material, MaterialMovement, Deed, DeedConsent
from .push_views import get_eligible_employees_for_new_order


# ═══════════════════════════════════════════════════════════════════
# SENDER (worker) — ariza yuboruvchi
# ═══════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════
# RECEIVER (worker) — ariza qabul qiluvchi/bajaruvchi
# ═══════════════════════════════════════════════════════════════════

def _assignee_candidates(order):
    """Superuser arizani biriktira oladigan xodimlar: arizaga ruxsatli (OrderGoal),
    yuboruvchi bilan bir hududdagi, ariza kategoriyasi tashkilotidagi va
    "Ariza bajarish" (change_order) huquqi bor xodimlar. Tashkilot mos bo'lmasa
    ariza ijrochining "faol arizalar" ro'yxatida ko'rinmaydi, huquqsiz xodim esa
    o'sha sahifani umuman ocha olmaydi."""
    perm = Permission.objects.filter(codename="change_order", content_type__app_label="main").first()
    perm_q = Q(user__is_superuser=True)
    if perm:
        perm_q |= Q(user__user_permissions=perm) | Q(user__groups__permissions=perm)
    return (
        get_eligible_employees_for_new_order(order)
        .filter(user__isnull=False, organization_id=order.goal.organization_id)
        .filter(perm_q)
        .distinct()
        .order_by("last_name", "first_name", "father_name")
    )


# ═══════════════════════════════════════════════════════════════════
# RECEIVER — hujjat (deed) imzolashga yuborish
# ═══════════════════════════════════════════════════════════════════


# Akt (dalolatnoma) — eski sahifa va yangi interfeys (api/spa/orders.py) uchun umumiy qism
ORDER_DEED_BODY_TEMPLATE = "main/partials/order_deed_body.html"


def order_deed_queryset():
    """Akt matni uchun kerakli bog'lanishlar bilan arizalar."""
    return Order.objects.select_related(
        "sender", "sender__organization",
        "sender__department", "receiver", "receiver__rank",
        "technics",
    ).prefetch_related(
        Prefetch("materials", queryset=OrderMaterial.objects.select_related("material", "material__unit"))
    )


def order_deed_context(order):
    """Akt sahifasi va matni konteksti: imzolovchilar — ariza muallifi tashkiloti xodimlari."""
    employees = (
        Employee.objects
        .filter(organization=order.sender.organization)
        .select_related("organization", "rank")
    )
    return {"order": order, "employees": employees, "today": timezone.now()}


def create_order_act(order, employee, sender, body, message):
    """
    Bajarilgan ariza bo'yicha akt yaratadi: muallif va ijrochi kelishuvi (imzolovchi bo'lmasa), "TASDIQLANMAGAN"
    belgili PDF. Bildirishnomani chaqiruvchi yuboradi. PDF yasalmasa HtmlPdfError (tranzaksiya bekor qilinadi).
    """
    with transaction.atomic():
        deed = Deed.objects.create(
            organization=order.sender.organization,
            sender_id=sender.id,
            user_id=employee.id,
            message_user=message,
            body=body,
            status='act',
        )
        deed.orders.set([order.id])

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
    return deed


# ═══════════════════════════════════════════════════════════════════
# SENDER (client) — "barn"
# ═══════════════════════════════════════════════════════════════════


def _restore_given_materials(order, reason):
    """
    Omborxonachi allaqachon bergan (given > 0) materiallarni omborga qaytaradi va harakat jurnaliga yozadi.
    Material arizasi `finished` holatda bekor qilinganda ishlatiladi (avval ombor qoldig'i qaytmay qolardi).
    Chaqiruvchi transaction.atomic() ichida bo'lishi kerak.
    """
    order_materials = list(
        OrderMaterial.objects.select_for_update(of=("self",)).filter(order=order).select_related("material")
    )
    material_ids = [om.material_id for om in order_materials if om.material_id and (om.given or 0) > 0]
    materials = {m.id: m for m in Material.objects.select_for_update().filter(id__in=material_ids)}

    changed_materials, changed_oms, movements = [], [], []
    for om in order_materials:
        given = om.given or 0
        if given <= 0:
            continue
        mat = materials.get(om.material_id)
        if mat:
            mat.number = (mat.number or 0) + given
            changed_materials.append(mat)
            movements.append(MaterialMovement(
                material=mat, user=order.sender, employee=mat.employee, status="order",
                income=given, body=f"Ariza #{order.id} {reason} - qaytarildi",
            ))
        om.given = 0
        changed_oms.append(om)

    if changed_materials:
        Material.objects.bulk_update(changed_materials, ["number"])
    if changed_oms:
        OrderMaterial.objects.bulk_update(changed_oms, ["given"])
    if movements:
        MaterialMovement.objects.bulk_create(movements)


class CartEmptyError(Exception):
    """Savatda material yo'q."""


def create_order_from_cart(employee, goal, body, numbers=None, check=None):
    """
    Xodim savatidagi (order yo'q) materiallardan omborxona arizasi yaratadi — eski sahifa va api/spa/orders_barn.py
    uchun umumiy. numbers: {qator_id: soni} (kamida 1). check(items) — qulf ostida qo'shimcha tekshiruv (istisno
    tashlasa tranzaksiya bekor). Savat bo'sh bo'lsa CartEmptyError. Bildirishnomani chaqiruvchi yuboradi.
    """
    numbers = numbers or {}
    with transaction.atomic():
        cart_items = list(
            OrderMaterial.objects
            .select_for_update(of=("self",))
            .filter(user=employee, order__isnull=True, material__isnull=False)
            .select_related("material")
        )
        if not cart_items:
            raise CartEmptyError
        if check:
            check(cart_items)

        order = Order.objects.create(
            goal=goal, sender=employee, message_sender=body, status="viewed",
        )
        for item in cart_items:
            if item.id in numbers:
                item.number = max(int(numbers[item.id]), 1)
            item.order = order

        OrderMaterial.objects.bulk_update(cart_items, ["number", "order"])
    return order


# ═══════════════════════════════════════════════════════════════════
# RECEIVER — "barn"
# ═══════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════
# AGREMENT — tasdiqlovchi
# ═══════════════════════════════════════════════════════════════════


