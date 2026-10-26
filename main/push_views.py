import logging


from .models import Employee, OrderGoal

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────
# PUSH YUBORISH — asosiy funksiya
# ─────────────────────────────────────────────────────────────────────────

def send_push_notification(employee, title, body, url="/", tag=None):
    """
    Xodimga bildirishnoma: bildirishnomalar markazi tarixiga yozadi, brauzer push (Web Push) va Android (FCM) ga yuboradi.

    tag — brauzerda bir xil hodisani guruhlash uchun: bir xil tag bilan kelgan yangi bildirishnoma eskisini JIM
    almashtiradi, shuning uchun har bir HAQIQIY hodisa (ariza, hujjat) uchun UNIKAL tag berish shart.
    Haqiqiy yuborish Celery worker'da, orqa fonda bajariladi (`main.tasks.send_push_notification_task`, `send_fcm_notification_task`).
    """
    from core.notifications import record
    from .fcm import fcm_enabled
    from .tasks import send_fcm_notification_task, send_push_notification_task

    # Bildirishnomalar markazi tarixiga yozish (push ishlamasa ham tarixda qoladi; xato bo'lsa jim o'tadi)
    record(employee, title, body, url, tag)

    send_push_notification_task.delay(employee.id, title, body, url, tag)
    # Android (FCM): sozlanmagan bo'lsa navbatga qo'yilmaydi
    if fcm_enabled():
        send_fcm_notification_task.delay(employee.id, title, body, url, tag)


# ─────────────────────────────────────────────────────────────────────────
# BIZNES-MANTIQ — kimga push yuborish kerakligini aniqlash
# ─────────────────────────────────────────────────────────────────────────

def get_eligible_employees_for_new_order(order):
    """
    Yangi ariza (order) haqida push xabar olishi kerak bo'lgan xodimlarni
    aniqlaydi. order_receiver sahifasidagi ko'rish mantig'i bilan bir xil:
    - goal.organization.type == "worker" bo'lsa, sender bilan bir xil
      hududdagi (region) va OrderGoal orqali shu goal'ga ruxsatli
      xodimlar (client tashkilotlaridan tashqari).
    - goal.organization.type == "client" bo'lsa, o'sha aniq tashkilot
      va bir xil hududdagi xodimlar.
    """
    if not order.goal or not order.goal.organization:
        return Employee.objects.none()

    goal_org_type = order.goal.organization.type

    eligible_ids = OrderGoal.goal.through.objects.filter(
        goal=order.goal
    ).values_list("ordergoal__employee_id", flat=True)

    if goal_org_type == "worker":
        region_id = order.sender_region_id or (order.sender.region_id if order.sender else None)
        if not region_id:
            return Employee.objects.none()

        return Employee.objects.filter(
            id__in=eligible_ids,
            region_id=region_id,
        ).exclude(organization__type="client")

    elif goal_org_type == "client":
        region_id = order.sender_region_id or (order.sender.region_id if order.sender else None)
        if not region_id:
            return Employee.objects.none()

        return Employee.objects.filter(
            id__in=eligible_ids,
            organization=order.goal.organization,
            region_id=region_id,
        )

    return Employee.objects.none()


# ─────────────────────────────────────────────────────────────────────────
# NOTIFY FUNKSIYALARI — har biri o'z hodisasi uchun unikal tag bilan
# ─────────────────────────────────────────────────────────────────────────

def notify_eligible_employees_new_order(order):
    """
    Yangi ariza yaratilganda, unga ruxsatli barcha xodimlarga push
    yuboradi. Har bir ariza uchun UNIKAL tag ("order-new-{id}") ishlatiladi,
    shunda har bir ariza alohida, ko'rinadigan notification bo'ladi.
    """
    eligible_employees = get_eligible_employees_for_new_order(order)

    for employee in eligible_employees:
        send_push_notification(
            employee,
            title="Yangi ariza yuborildi",
            body=f"#{order.id} {order.sender.full_name if order.sender else ''}",
            url="/order/receiver/",
            tag=f"order-new-{order.id}",
        )


def notify_order_status_change(order):
    """
    Ariza holati o'zgarganda, ariza yuboruvchisiga (sender) push yuboradi.
    Har bir status o'zgarishi uchun UNIKAL tag ishlatiladi (order.id +
    status), shunda bir xil ariza bo'yicha ketma-ket kelgan turli status
    o'zgarishlari bir-birini yashirib qo'ymaydi.
    """
    if not order.sender:
        return

    status_display = order.get_status_display() if hasattr(order, "get_status_display") else order.status

    send_push_notification(
        order.sender,
        title="Ariza holati o'zgardi",
        body=f"#{order.id} — {status_display}",
        url="/order/sender/",
        tag=f"order-status-{order.id}-{order.status}",
    )


def notify_deed_sender(deed):
    """
    Hujjat (Deed) imzolashga yuborilganda, imzolovchi (sender)ga push
    yuboradi. Har bir hujjat uchun unikal tag.
    """
    if not deed.sender:
        return

    send_push_notification(
        deed.sender,
        title="Hujjat imzolashga yuborildi",
        body=f"Hujjat #{deed.id} sizning imzoingizni kutmoqda",
        url="/contact/user/",
        tag=f"deed-sender-{deed.id}",
    )


def notify_deed_watchers(deed, employees):
    """
    Hujjat (Deed) bo'yicha kelishuvchilarga (DeedConsent orqali biriktirilgan
    xodimlar) push yuboradi. Har bir hujjat uchun unikal tag, lekin har bir
    xodimga alohida yuboriladi (ular bir-biriga ta'sir qilmaydi, chunki
    tag faqat bitta foydalanuvchining o'z brauzeri ichida guruhlaydi).
    """
    for employee in employees:
        send_push_notification(
            employee,
            title="Hujjat kelishishga yuborildi",
            body=f"Hujjat #{deed.id} bo'yicha fikringiz kutilmoqda",
            url="/contact/user/",
            tag=f"deed-watcher-{deed.id}",
        )