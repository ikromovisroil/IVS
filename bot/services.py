"""
bot/services.py
"""
from __future__ import annotations

from dataclasses import dataclass
import logging

from django.db import transaction, DatabaseError, connection
from django.db.models import Q

from main.models import Employee, Order, Goal, OrderGoal

logger = logging.getLogger(__name__)


def _locking_qs(qs):

    if connection.features.has_select_for_update:
        return qs.select_for_update()
    return qs


# ---------------------------------------------------------------------------
# Xodimni aniqlash / bog'lash
# ---------------------------------------------------------------------------

def find_employee_by_pinfl(pinfl: str) -> Employee | None:
    pinfl = (pinfl or "").strip()
    if not pinfl.isdigit() or len(pinfl) != 14:
        return None
    return (
        Employee.objects
        .select_related("organization", "user")
        .filter(pinfl=pinfl, user__isnull=False)
        .first()
    )


def link_telegram_chat(employee: Employee, chat_id: int) -> None:
    Employee.objects.filter(telegram_chat=chat_id).exclude(pk=employee.pk).update(
        telegram_chat=None
    )
    employee.telegram_chat = chat_id
    employee.save(update_fields=["telegram_chat"])


def get_employee_by_chat_id(chat_id: int) -> Employee | None:
    return (
        Employee.objects
        .select_related("organization", "region", "user")
        .filter(telegram_chat=chat_id)
        .first()
    )


def unlink_telegram_chat(employee: Employee) -> None:
    employee.telegram_chat = None
    employee.save(update_fields=["telegram_chat"])


def save_employee_phone(employee: Employee, phone_number: str) -> None:
    """Telegram orqali ulashilgan telefon raqamini xodimga saqlaydi."""
    phone_number = (phone_number or "").strip()
    if not phone_number:
        return
    if not phone_number.startswith("+"):
        phone_number = "+" + phone_number
    employee.phone = phone_number
    employee.save(update_fields=["phone"])


@dataclass
class MenuFlags:
    pass


def get_menu_flags(employee: Employee) -> MenuFlags:
    return MenuFlags()


# ---------------------------------------------------------------------------
# TASHKILOT TURI BO'YICHA YORDAMCHI FUNKSIYALAR
# ---------------------------------------------------------------------------

def is_worker_employee(employee: Employee) -> bool:
    """Xodim 'worker' (xizmat ko'rsatuvchi) tashkilotdanmi."""
    return bool(employee.organization_id and employee.organization.type == "worker")


def is_client_employee(employee: Employee) -> bool:
    """Xodim 'client' (mijoz) tashkilotdanmi."""
    return bool(employee.organization_id and employee.organization.type == "client")


def can_execute_orders(employee: Employee) -> bool:
    """Xodimda 'Ariza bajarish' (main.change_order) huquqi bor-yo'qligini tekshiradi."""
    if not employee.user_id:
        return False
    return employee.user.has_perm("main.change_order")


# ---------------------------------------------------------------------------
# UMUMIY NATIJA TIPI (barcha ariza amallari uchun)
# ---------------------------------------------------------------------------

@dataclass
class OrderResult:
    ok: bool
    message: str
    order: Order | None = None


# ---------------------------------------------------------------------------
# 1) ARIZA YARATISH - ATM (worker) va OMBORXONA (client) uchun ALOHIDA
# ---------------------------------------------------------------------------

def list_atm_goals(employee: Employee):
    """ATM uchun - faqat 'worker' turidagi tashkilotlarning kategoriyalari."""
    return list(Goal.objects.filter(organization__type="worker").order_by("name"))


def list_warehouse_goals(employee: Employee):

    if not employee.organization_id:
        return []
    return list(
        Goal.objects
        .filter(organization__type="client", organization_id=employee.organization_id)
        .order_by("name")
    )


def create_order(employee: Employee, goal_id: int, message_text: str, context: str = "atm") -> OrderResult:

    goal = Goal.objects.filter(pk=goal_id).first()
    if not goal:
        return OrderResult(False, "Ariza turi topilmadi")

    if context == "warehouse":
        allowed_ids = {g.id for g in list_warehouse_goals(employee)}
    else:
        allowed_ids = {g.id for g in list_atm_goals(employee)}

    if goal.id not in allowed_ids:
        return OrderResult(False, "Sizga bu turdagi arizani yuborish ruxsat etilmagan")

    order = Order.objects.create(
        sender=employee,
        goal=goal,
        message_sender=(message_text or "").strip() or None,
        status="viewed",
    )
    return OrderResult(True, "Ariza muvaffaqiyatli yuborildi", order)


def list_my_orders(employee: Employee, limit: int = 20):
    return list(
        Order.objects
        .filter(sender=employee)
        .select_related("goal", "receiver")
        .order_by("-id")[:limit]
    )


# ---------------------------------------------------------------------------
# 2) BAHOLASH - FAQAT baho, bekor qilish YO'Q
# ---------------------------------------------------------------------------

def rate_order(employee: Employee, order_id: int, rating: int) -> OrderResult:
    if rating not in {1, 2, 3, 4, 5}:
        return OrderResult(False, "Baho 1 dan 5 gacha bo'lishi kerak")

    try:
        with transaction.atomic():
            order = _locking_qs(Order.objects).filter(
                pk=order_id, status="finished", sender=employee,
            ).first()
            if not order:
                return OrderResult(False, "Ariza topilmadi yoki allaqachon baholangan")

            order.status = "accepted"
            order.rating = rating
            order.save(update_fields=["status", "rating"])
    except DatabaseError:
        logger.exception("DatabaseError yuz berdi (order_id=%s)", order_id)
        return OrderResult(False, "Xatolik, qayta urinib ko'ring")

    return OrderResult(True, "Rahmat! Bahoyingiz qabul qilindi", order)


def list_pending_ratings(employee: Employee, limit: int = 10):
    return list(
        Order.objects
        .filter(sender=employee, status="finished")
        .select_related("goal", "receiver")
        .order_by("-id")[:limit]
    )


# ---------------------------------------------------------------------------
# 3) OMBOR (client) ARIZASI - TASDIQLANGANDAN KEYIN "QABUL QILDIM"
# (order_decide_barn(action="accepted") bilan TO'LIQ bir xil mantiq,
# hujjat (Deed) yaratish bilan birga)
# ---------------------------------------------------------------------------

def receive_order(employee: Employee, order_id: int) -> OrderResult:
    from django.db import DatabaseError as _DatabaseError
    from main.html_pdf import _create_deed_for_order, HtmlPdfError
    import logging

    order = Order.objects.filter(pk=order_id).first()
    if not order:
        return OrderResult(False, "Ariza topilmadi")

    if order.sender_id != employee.id:
        return OrderResult(False, "Ariza sizga tegishli emas")

    if order.status != "approved":
        return OrderResult(False, "Ariza topilmadi yoki allaqachon qabul qilingan")

    deed_error = None
    try:
        with transaction.atomic():
            order = _locking_qs(Order.objects).get(pk=order_id)

            if order.status != "approved":
                return OrderResult(False, "Ariza topilmadi yoki allaqachon qabul qilingan")

            order.status = "accepted"
            order.save(update_fields=["status"])

            if order.materials.exists():
                try:
                    _create_deed_for_order(order, request=None)
                except HtmlPdfError:
                    deed_error = "hujjat"
                    raise
                except Exception:
                    deed_error = "imzo"
                    raise

    except _DatabaseError:
        return OrderResult(False, "Xatolik, qayta urinib ko'ring")
    except (HtmlPdfError, Exception):
        if deed_error == "hujjat":
            return OrderResult(
                False,
                "Ariza qabul qilinmadi — hujjat yaratishda xatolik yuz berdi. "
                "Qayta urinib ko'ring yoki saytga kiring.",
            )
        elif deed_error == "imzo":
            return OrderResult(
                False,
                "Ariza qabul qilinmadi — hujjatga imzo/QR urishda xatolik yuz berdi. "
                "Qayta urinib ko'ring yoki saytga kiring.",
            )
        logging.getLogger(__name__).exception(
            "receive_order kutilmagan xato (order=%s)", order_id
        )
        return OrderResult(False, "Kutilmagan xatolik yuz berdi. Qayta urinib ko'ring")

    return OrderResult(True, "Qabul qilinganligi belgilandi va hujjat yaratildi. Rahmat!", order)


# ---------------------------------------------------------------------------
# 4) ARIZA BAJARISH (ijrochi oqimi): Qabul qilish -> Yakunlash
# ATM va Omborxona uchun ALOHIDA (context orqali)
# ---------------------------------------------------------------------------

def _allowed_goal_ids(employee: Employee):
    return list(
        OrderGoal.objects.filter(employee=employee).values_list("goal_id", flat=True)
    )


def _context_goal_filter(employee: Employee, context: str) -> Q:

    if context == "warehouse":
        return Q(
            goal__organization__type="client",
            goal__organization_id=employee.organization_id,
        )
    return Q(goal__organization__type="worker")


def list_orders_to_execute(employee: Employee, context: str = "atm", limit: int = 20):

    goal_ids = _allowed_goal_ids(employee)
    if not goal_ids:
        return []

    ctx_filter = _context_goal_filter(employee, context)

    new_orders = (
        Order.objects
        .filter(
            ctx_filter,
            status="viewed",
            goal_id__in=goal_ids,
            receiver__isnull=True,
            sender__region_id=employee.region_id,   # <-- har doim, istisnosiz
        )
        .select_related(
            "goal", "sender", "sender__organization", "sender__department",
            "sender__directorate", "sender__division", "sender__rank",
        )
        .order_by("id")[:limit]
    )
    pending_orders = (
        Order.objects
        .filter(ctx_filter, status="process", receiver=employee)
        .select_related(
            "goal", "sender", "sender__organization", "sender__department",
            "sender__directorate", "sender__division", "sender__rank",
        )
        .order_by("id")[:limit]
    )
    return list(new_orders) + list(pending_orders)


def accept_order(employee: Employee, order_id: int) -> OrderResult:
    """Yangi arizani qabul qiladi: receiver=employee, status -> process."""
    if not can_execute_orders(employee):
        return OrderResult(False, "Sizda arizalarni bajarish huquqi yo'q")

    try:
        with transaction.atomic():
            order = _locking_qs(Order.objects).filter(
                pk=order_id, status="viewed", receiver__isnull=True,
            ).first()
            if not order:
                return OrderResult(False, "Ariza topilmadi yoki allaqachon qabul qilingan")

            if order.goal_id not in _allowed_goal_ids(employee):
                return OrderResult(False, "Sizga ushbu turdagi arizani qabul qilish ruxsat etilmagan")

            order.receiver = employee
            order.status = "process"
            order.save(update_fields=["receiver", "status"])
    except DatabaseError:
        logger.exception("DatabaseError yuz berdi (order_id=%s)", order_id)
        return OrderResult(False, "Xatolik, qayta urinib ko'ring")

    return OrderResult(True, "Ariza qabul qilindi", order)


def finish_order(employee: Employee, order_id: int) -> OrderResult:
    """Qabul qilingan arizani yakunlaydi: status -> finished."""
    try:
        with transaction.atomic():

            order = _locking_qs(Order.objects).filter(
                pk=order_id, receiver=employee, status="process"
            ).first()
            if not order:
                return OrderResult(False, "Ariza topilmadi yoki allaqachon yakunlangan")

            order.status = "finished"
            order.save(update_fields=["status"])

            order = Order.objects.select_related("sender", "goal").get(pk=order.pk)
    except DatabaseError:
        logger.exception("finish_order DatabaseError (order_id=%s)", order_id)
        return OrderResult(False, "Xatolik, qayta urinib ko'ring")

    return OrderResult(True, "Ish muvaffaqiyatli yakunlandi!", order)


def list_completed_orders(employee: Employee, context: str = "atm", limit: int = 20):
    """Shu xodim (ijrochi sifatida) yakunlagan arizalar tarixi (context bo'yicha)."""
    ctx_filter = _context_goal_filter(employee, context)
    return list(
        Order.objects
        .filter(ctx_filter, receiver=employee, status__in=["finished", "approved", "accepted", "rejected"])
        .select_related(
            "goal", "sender", "sender__organization", "sender__department",
            "sender__directorate", "sender__division", "sender__rank",
        )
        .order_by("-id")[:limit]
    )