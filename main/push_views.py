import json
import logging

from pywebpush import webpush, WebPushException
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from core.models import PushSubscription
from .models import *

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# OBUNA BOSHQARUVI
# ═══════════════════════════════════════════════════════════════════

@require_POST
@login_required
def save_push_subscription(request):
    """
    Frontend'dan kelgan push obunasini saqlaydi.
    Har bir brauzer/qurilma uchun bitta yozuv (endpoint bo'yicha unique).
    """
    employee = getattr(request.user, "employee", None)
    if not employee:
        return JsonResponse({"status": "no_employee"}, status=400)

    try:
        data = json.loads(request.body)
        endpoint = data["endpoint"]
        p256dh = data["keys"]["p256dh"]
        auth = data["keys"]["auth"]
    except (KeyError, ValueError, TypeError):
        return JsonResponse({"status": "invalid_data"}, status=400)

    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "employee": employee,
            "p256dh": p256dh,
            "auth": auth,
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:300],
        },
    )

    return JsonResponse({"status": "ok"})


@require_POST
@login_required
def remove_push_subscription(request):
    """Foydalanuvchi bildirishnomalarni o'chirganda obunani o'chiradi."""
    try:
        data = json.loads(request.body)
        endpoint = data.get("endpoint")
    except (ValueError, TypeError):
        endpoint = None

    if endpoint:
        PushSubscription.objects.filter(endpoint=endpoint).delete()

    return JsonResponse({"status": "ok"})


# ═══════════════════════════════════════════════════════════════════
# ASOSIY YUBORISH FUNKSIYASI
# ═══════════════════════════════════════════════════════════════════

def send_push_notification(employee, title, body, url="/"):
    subscriptions = PushSubscription.objects.filter(employee=employee)
    dead_ids = []

    for sub in subscriptions:
        try:
            response = webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh,
                        "auth": sub.auth,
                    },
                },
                data=json.dumps({"title": title, "body": body, "url": url}),
                vapid_private_key=settings.VAPID_PRIVATE_KEY_PEM,
                vapid_claims=dict(settings.VAPID_CLAIMS),
            )
            logger.error(f"[PUSH-DEBUG] webpush javobi: status={response.status_code}, employee_id={employee.id}")
        except WebPushException as e:
            status_code = e.response.status_code if e.response else None
            logger.error(f"[PUSH-DEBUG] WebPushException: status={status_code}, employee_id={employee.id}, error={e}")
            if status_code in (404, 410):
                dead_ids.append(sub.id)
        except Exception as e:
            logger.exception(f"[PUSH-DEBUG] Kutilmagan xato: employee_id={employee.id}, error={e}")

    if dead_ids:
        PushSubscription.objects.filter(id__in=dead_ids).delete()


# ═══════════════════════════════════════════════════════════════════
# SERVICE WORKER
# ═══════════════════════════════════════════════════════════════════

def service_worker_js(request):
    """
    sw.js faylini sayt ILDIZIDAN xizmat ko'rsatadi (masalan
    https://report.yatm.uz/sw.js), shunda uning "scope"i butun saytni
    qamrab oladi.
    """
    import os

    sw_path = os.path.join(settings.BASE_DIR, "static", "js", "sw.js")

    if not os.path.exists(sw_path) and getattr(settings, "STATIC_ROOT", None):
        sw_path = os.path.join(settings.STATIC_ROOT, "js", "sw.js")

    with open(sw_path, "r", encoding="utf-8") as f:
        content = f.read()

    response = HttpResponse(content, content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    return response


# ═══════════════════════════════════════════════════════════════════
# ARIZA (ORDER) — YANGI ARIZA YARATILGANDA
# ═══════════════════════════════════════════════════════════════════

def get_eligible_employees_for_new_order(order):
    """
    Berilgan (yangi, receiver=None, status='viewed') ariza uchun,
    uni ko'rish/qabul qilish huquqiga ega BARCHA xodimlarni qaytaradi.

    Bu - order_notifications context processoridagi "unassigned" filtr
    mantig'ining aynan TESKARISI: u yerda "xodim uchun mos arizalar"
    qidirilsa, bu yerda "ariza uchun mos xodimlar" qidiriladi.
    """
    if not order.goal or not order.goal.organization:
        return Employee.objects.none()

    goal_org_type = order.goal.organization.type

    eligible_ids = OrderGoal.objects.filter(
        goal=order.goal
    ).values_list("employee_id", flat=True)

    if goal_org_type == "worker":
        # order_receiver mantig'i bilan bir xil:
        # worker turidagi xodimlar, shu goal'ga ruxsatli,
        # ariza yuboruvchi bilan bir regionda
        if not order.sender or not order.sender.region_id:
            return Employee.objects.none()

        return Employee.objects.filter(
            id__in=eligible_ids,
            region_id=order.sender.region_id,
        ).exclude(organization__type="client")

    elif goal_org_type == "client":
        # order_receiver_barn mantig'i bilan bir xil:
        # client turidagi xodimlar, shu goal'ning tashkilotiga tegishli,
        # sender bilan bir regionda (region majburiy)
        if not order.sender or not order.sender.region_id:
            return Employee.objects.none()

        return Employee.objects.filter(
            id__in=eligible_ids,
            organization=order.goal.organization,
            region_id=order.sender.region_id,
        )

    return Employee.objects.none()


def notify_eligible_employees_new_order(order):
    employees = get_eligible_employees_for_new_order(order)

    if not employees.exists():
        return

    goal_org_type = order.goal.organization.type if order.goal and order.goal.organization else None

    if goal_org_type == "worker":
        url = reverse("order_receiver")
    elif goal_org_type == "client":
        url = reverse("order_receiver_barn")
    else:
        url = "/"

    title = "Yangi ariza"
    body = f"#{order.id} - Yangi ariza keldi"

    for emp in employees:
        send_push_notification(emp, title, body, url=url)


# ═══════════════════════════════════════════════════════════════════
# ARIZA (ORDER) — MAVJUD ARIZA STATUSI O'ZGARGANDA
# ═══════════════════════════════════════════════════════════════════

# Har bir status uchun sarlavha/matn - base.html'dagi bell bildirishnoma
# matnlari bilan bir xil uslubda
ORDER_STATUS_TEXT = {
    "viewed":   "Yangi ariza yuborildi",
    "process":  "Ariza ish jarayonida",
    "finished": "Ariza tayyorlandi",
    "approved": "Ariza tasdiqlandi",
    "accepted": "Ariza qabul qilindi",
    "canceled": "Ariza bekor qilindi",
    "rejected": "Ariza rad etildi",
}


def notify_order_status_change(order):
    """
    MAVJUD arizaning statusi/receiver/seen maydonlari o'zgarganda
    chaqiriladi (yangi ariza yaratishda EMAS - u uchun
    notify_eligible_employees_new_order ishlatiladi).

    order_notifications context processoridagi qolgan 5 ta shartni
    (receiver_seen, sender_seen, user_seen bo'yicha) aynan takrorlaydi,
    lekin bitta xodim uchun emas, balki order.save() dan keyin - kimga
    push kerakligini avtomatik aniqlaydi.

    Foydalanish: order.status yoki order.receiver o'zgargan HAR BIR
    view'da, order.save() dan KEYIN chaqiriladi:

        order.status = "process"
        order.receiver = employee
        order.save()

        from main.push_views import notify_order_status_change
        notify_order_status_change(order)
    """
    if not order.goal or not order.goal.organization:
        return

    org_type = order.goal.organization.type
    status_text = ORDER_STATUS_TEXT.get(order.status, "Ariza holati yangilandi")
    body = f"#{order.id} - {status_text}"

    # ── RECEIVER (ijrochi) ──────────────────────────────────────────
    if order.receiver and not order.receiver_seen:
        if org_type == "worker" and order.status in ["viewed", "approved", "canceled"]:
            send_push_notification(
                order.receiver, status_text, body, url=reverse("order_receiver")
            )
        elif org_type == "client" and order.status in ["viewed", "accepted", "canceled", "rejected"]:
            send_push_notification(
                order.receiver, status_text, body, url=reverse("order_receiver_barn")
            )

    # ── SENDER (yuboruvchi) ─────────────────────────────────────────
    if order.sender and not order.sender_seen:
        if org_type == "worker" and order.status in ["finished", "rejected"]:
            send_push_notification(
                order.sender, status_text, body, url=reverse("order_sender")
            )
        elif org_type == "client" and order.status in ["approved", "rejected"]:
            send_push_notification(
                order.sender, status_text, body, url=reverse("order_sender_barn")
            )

    # ── USER (tasdiqlovchi) ─────────────────────────────────────────
    if order.user and not order.user_seen:
        if org_type == "client" and order.status == "accepted":
            send_push_notification(
                order.user, status_text, body, url=reverse("order_agrement")
            )


# ═══════════════════════════════════════════════════════════════════
# DALOLATNOMA (DEED)
# ═══════════════════════════════════════════════════════════════════

def notify_deed_sender(deed):
    """
    Dalolatnoma yaratilganda, imzolovchilarga (deed.sender va,
    agar mavjud bo'lsa, deed.receiver) push yuboradi.

    Diqqat: "author_name" har doim deed.user (hujjatni yaratgan/yuborgan
    shaxs) dan olinadi - deed.sender/deed.receiver dan EMAS, chunki ular
    push oluvchining o'zi, "kimdan kelgani" emas.
    """
    author_name = deed.user.full_name if deed.user else "Noma'lum"

    if deed.sender:
        send_push_notification(
            deed.sender,
            "Imzolashga yuborildi",
            f"{author_name} tomonidan yangi dalolatnoma imzolash uchun yuborildi",
            url=reverse("contact"),
        )

    if deed.receiver:
        send_push_notification(
            deed.receiver,
            "Imzolashga yuborildi",
            f"{author_name} tomonidan yangi dalolatnoma imzolash uchun yuborildi",
            url=reverse("contact"),
        )


def notify_deed_watchers(deed, employees):
    """
    Kelishuvchilarga (DeedConsent orqali biriktirilgan xodimlarga) push
    yuboradi. "employees" - Employee obyektlari ro'yxati yoki queryset
    (masalan DeedConsent.objects.bulk_create dan keyin, o'sha xodimlar).

    Foydalanish namunasi (reest_post/svod_post/akt_post/document_post
    kabi view'larda):

        emps = Employee.objects.filter(id__in=ids).only("id")
        objs = [DeedConsent(deed=deed, employee=e, status="viewed") for e in emps]
        DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

        from main.push_views import notify_deed_watchers
        notify_deed_watchers(deed, emps)
    """
    author_name = deed.user.full_name if deed.user else "Noma'lum"
    deed_type = deed.get_status_display()  # masalan: "Reestr", "Akt", "Yakuniy hisobot"

    for emp in employees:
        send_push_notification(
            emp,
            "Kelishish uchun dalolatnoma",
            f"{author_name} tomonidan yangi {deed_type} kelishuv uchun yuborildi",
            url=reverse("contact_agrement"),
        )