"""
bot/services.py

Telegram bot uchun biznes-mantiq:
1. Ariza yaratish - FAQAT ATM'ga
2. Bajarilgan ATM arizasini baholash (bekor qilib bo'lmaydi)
3. Ombor (client) arizasi tasdiqlangach - "qabul qildim" belgilash

Barcha funksiyalar SINXRON - aiogram handler'larida
`asgiref.sync.sync_to_async` bilan o'raladi.
"""
from dataclasses import dataclass

from django.db import transaction, DatabaseError

from main.models import Employee, Order, Goal


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


@dataclass
class MenuFlags:
    pass


def get_menu_flags(employee: Employee) -> MenuFlags:
    return MenuFlags()


# ---------------------------------------------------------------------------
# 1) ARIZA YARATISH - FAQAT ATM'GA
# ---------------------------------------------------------------------------

def list_available_goals(employee: Employee):
    return list(Goal.objects.filter(organization__type="worker").order_by("name"))


@dataclass
class OrderResult:
    ok: bool
    message: str
    order: Order | None = None


def create_order(employee: Employee, goal_id: int, message_text: str) -> OrderResult:
    goal = Goal.objects.filter(pk=goal_id).first()
    if not goal:
        return OrderResult(False, "Ariza turi topilmadi")

    available_ids = {g.id for g in list_available_goals(employee)}
    if goal.id not in available_ids:
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
# 2) BAHOLASH (ATM) - FAQAT baho, bekor qilish YO'Q
# ---------------------------------------------------------------------------

def rate_order(employee: Employee, order_id: int, rating: int) -> OrderResult:
    if rating not in {1, 2, 3, 4, 5}:
        return OrderResult(False, "Baho 1 dan 5 gacha bo'lishi kerak")

    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().filter(
                pk=order_id, status="finished", sender=employee,
            ).first()
            if not order:
                return OrderResult(False, "Ariza topilmadi yoki allaqachon baholangan")

            order.status = "approved"
            order.rating = rating
            order.save(update_fields=["status", "rating"])
    except DatabaseError:
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

    # Tekshiruvlar transaction tashqarisida (web bilan bir xil)
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
            order = Order.objects.select_for_update().get(pk=order_id)

            # Race condition — qayta tekshirish (web bilan bir xil)
            if order.status != "approved":
                return OrderResult(False, "Ariza topilmadi yoki allaqachon qabul qilingan")

            order.status = "accepted"
            order.save(update_fields=["status"])

            if order.materials.exists():
                try:
                    # request=None - bot HTTP so'rov konteksti bilan ishlamaydi,
                    # sign_pdf_inplace SITE_BASE_URL orqali o'zi domenni oladi.
                    _create_deed_for_order(order, request=None)
                except HtmlPdfError:
                    # Web'dagi kabi: xatoni chiqarib, transaction'ni ROLLBACK qilamiz
                    # (status "approved"ga qaytadi, "accepted" bo'lmay qoladi)
                    deed_error = "hujjat"
                    raise
                except Exception:
                    deed_error = "imzo"
                    raise

    except _DatabaseError:
        return OrderResult(False, "Xatolik, qayta urinib ko'ring")
    except (HtmlPdfError, Exception) as e:
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
        # deed_error yo'q bo'lsa - kutilmagan boshqa xato
        logging.getLogger(__name__).exception(
            "receive_order kutilmagan xato (order=%s)", order_id
        )
        return OrderResult(False, "Kutilmagan xatolik yuz berdi. Qayta urinib ko'ring")

    return OrderResult(True, "Qabul qilinganligi belgilandi va hujjat yaratildi. Rahmat!", order)