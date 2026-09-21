"""
bot/services.py
"""
from __future__ import annotations

from dataclasses import dataclass
import logging

from django.db import transaction, DatabaseError, connection
from django.db.models import Q
from django.utils import timezone

from bot.notify import send_telegram_message, rating_markup
from main.models import Employee, Order, Goal, OrderGoal

logger = logging.getLogger(__name__)

WAREHOUSE_FINISH_MESSAGE = "Materiallarni ombordan qabul qilib olishingiz mumkin"


def _locking_qs(qs):

    if connection.features.has_select_for_update:
        return qs.select_for_update()
    return qs


def _now_str() -> str:
    return timezone.localtime(timezone.now()).strftime("%Y.%m.%d %H:%M:%S")


def _goal_org_type(order: Order) -> str | None:
    goal = order.goal
    if goal is None or goal.organization_id is None:
        return None
    return goal.organization.type


def _push_status_change(order: Order) -> None:
    """Saytdagi kabi: ariza yuboruvchisiga web-push (holat o'zgarganda).
    Holat allaqachon bazaga yozilgan, shuning uchun push xatosi natijani buzmasligi kerak."""
    from main.push_views import notify_order_status_change
    try:
        notify_order_status_change(order)
    except Exception:
        logger.exception("notify_order_status_change xatosi (order=%s)", order.pk)


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
            # Baholash faqat ATM (worker) arizasi uchun. Ombor arizasi
            # tasdiqlash (approved) bosqichidan o'tishi shart, saytdagi kabi.
            order = _locking_qs(Order.objects).filter(
                pk=order_id, status="finished", sender=employee,
                goal__organization__type="worker",
            ).first()
            if not order:
                return OrderResult(False, "Ariza topilmadi yoki allaqachon baholangan")

            order.status = "accepted"
            order.rating = rating
            order.save(update_fields=["status", "rating"])
    except DatabaseError:
        logger.exception("DatabaseError yuz berdi (order_id=%s)", order_id)
        return OrderResult(False, "Xatolik, qayta urinib ko'ring")

    _push_status_change(order)
    return OrderResult(True, "Rahmat! Bahoyingiz qabul qilindi", order)


def list_pending_ratings(employee: Employee, limit: int = 10):
    return list(
        Order.objects
        .filter(sender=employee, status="finished", goal__organization__type="worker")
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

    if is_worker_employee(employee):
        return OrderResult(False, "Sizga ruxsat yo'q")

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

    _push_status_change(order)
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
    """Yangi arizani qabul qiladi: receiver=employee, status -> process.

    Saytdagi order_accepted (ATM) va order_accepted_barn (ombor) bilan bir xil
    shartlar: ariza turi, tashkilot va yuboruvchi hududi tekshiriladi."""
    if not can_execute_orders(employee):
        return OrderResult(False, "Sizda arizalarni bajarish huquqi yo'q")

    def _eligible(o: Order) -> bool:
        org_type = _goal_org_type(o)
        if o.sender_id is None or o.sender.region_id != employee.region_id:
            return False
        if o.goal_id not in _allowed_goal_ids(employee):
            return False
        if org_type == "worker":
            return not is_client_employee(employee)
        if org_type == "client":
            return (
                not is_worker_employee(employee)
                and o.goal.organization_id == employee.organization_id
            )
        return False

    try:
        with transaction.atomic():
            order = _locking_qs(Order.objects).filter(
                pk=order_id, status="viewed", receiver__isnull=True,
            ).first()
            if not order:
                return OrderResult(False, "Ariza topilmadi yoki allaqachon qabul qilingan")

            if not _eligible(order):
                return OrderResult(False, "Bu arizani qabul qilish huquqingiz yo'q")

            order.receiver = employee
            order.status = "process"
            order.save(update_fields=["receiver", "status"])

            order_kind = "ATMga yuborgan" if _goal_org_type(order) == "worker" else "Omborxonaga yuborilgan"
    except DatabaseError:
        logger.exception("DatabaseError yuz berdi (order_id=%s)", order_id)
        return OrderResult(False, "Xatolik, qayta urinib ko'ring")

    _push_status_change(order)

    if order.sender_id and order.sender.telegram_chat:
        send_telegram_message(
            order.sender.telegram_chat,
            f"<b>🔔 Yangi bildirishnoma</b>\n\n"
            f"✅ {order_kind} #{order.id} - arizangiz qabul qilindi.\n"
            f"👤 <b>Bajaruvchi:</b> {employee.full_name}\n\n"
            f"📅 <b>Vaqt:</b> {_now_str()}",
        )

    return OrderResult(True, "Ariza qabul qilindi", order)


def finish_order(employee: Employee, order_id: int) -> OrderResult:
    """Qabul qilingan arizani yakunlaydi: status -> finished.

    Saytdagi order_material_post (ATM) va order_material_barn (ombor) mantiqi:
    ATM - texnika/material ixtiyoriy; ombor - tashkilot tekshiriladi va
    yakunlash matni yoziladi. Materiali bor ombor arizasida berilgan sonlar
    (given) va ombor qoldig'i faqat saytda kiritiladi."""
    try:
        with transaction.atomic():

            order = _locking_qs(Order.objects).filter(
                pk=order_id, receiver=employee, status="process"
            ).first()
            if not order:
                return OrderResult(False, "Ariza topilmadi yoki allaqachon yakunlangan")

            update_fields = ["status"]
            if _goal_org_type(order) == "client":
                if is_worker_employee(employee) or order.goal.organization_id != employee.organization_id:
                    return OrderResult(False, "Bu ariza sizning tashkilotingizga tegishli emas")
                if order.materials.exists():
                    return OrderResult(
                        False,
                        "Bu arizada materiallar bor. Materiallar sonini kiritish uchun saytdan yakunlang",
                    )
                order.message_receiver = WAREHOUSE_FINISH_MESSAGE
                update_fields.append("message_receiver")
            elif is_client_employee(employee):
                return OrderResult(False, "Sizga ruxsat yo'q")

            order.status = "finished"
            order.save(update_fields=update_fields)

            order = Order.objects.select_related("sender", "goal", "goal__organization").get(pk=order.pk)
    except DatabaseError:
        logger.exception("finish_order DatabaseError (order_id=%s)", order_id)
        return OrderResult(False, "Xatolik, qayta urinib ko'ring")

    _push_status_change(order)

    if order.sender_id and order.sender.telegram_chat:
        if _goal_org_type(order) == "client":
            send_telegram_message(
                order.sender.telegram_chat,
                f"<b>🔔 Yangi bildirishnoma</b>\n\n"
                f"✅ Omborxonaga yuborilgan #{order.id} - arizangiz bajarildi.\n"
                f"👤 <b>Bajaruvchi:</b> {employee.full_name}\n\n"
                f"📅 <b>Vaqt:</b> {_now_str()}",
            )
        else:
            send_telegram_message(
                order.sender.telegram_chat,
                f"<b>🔔 Yangi bildirishnoma</b>\n\n"
                f"✅ ATMga yuborgan #{order.id} - arizangiz bajarildi.\n"
                f"👤 <b>Bajaruvchi:</b> {employee.full_name}\n\n"
                f"📅 <b>Vaqt:</b> {_now_str()}\n\n"
                f"⭐ <b>Iltimos, xizmat sifatini baholang:</b>",
                reply_markup=rating_markup(order.id),
            )

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