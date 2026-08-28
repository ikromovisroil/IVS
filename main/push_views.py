import json
import logging
import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from pywebpush import webpush, WebPushException

from .models import Employee, OrderGoal
from core.models import PushSubscription

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────
# SERVICE WORKER — sayt ildizidan (/sw.js) xizmat qilish
# ─────────────────────────────────────────────────────────────────────────

def service_worker_js(request):

    sw_path = os.path.join(settings.BASE_DIR, "static", "js", "sw.js")
    with open(sw_path, "r", encoding="utf-8") as f:
        content = f.read()
    return HttpResponse(content, content_type="application/javascript")


# ─────────────────────────────────────────────────────────────────────────
# OBUNANI SAQLASH / O'CHIRISH
# ─────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def save_push_subscription(request):
    """
    Brauzerdan kelgan push subscription ma'lumotlarini (endpoint, keys)
    joriy foydalanuvchining xodim profiliga bog'lab saqlaydi.
    Agar shu endpoint uchun yozuv allaqachon mavjud bo'lsa, uni yangilaydi
    (update_or_create) — shuning uchun bir xil qurilma qayta obuna bo'lsa
    ham dublikat yaratilmaydi.
    """
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Noto'g'ri so'rov formati"}, status=400)

    endpoint = (data.get("endpoint") or "").strip()
    keys = data.get("keys") or {}
    p256dh = (keys.get("p256dh") or "").strip()
    auth = (keys.get("auth") or "").strip()

    if not endpoint or not p256dh or not auth:
        return JsonResponse({"error": "Obuna ma'lumotlari to'liq emas"}, status=400)

    user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]

    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "employee": employee,
            "p256dh": p256dh,
            "auth": auth,
            "user_agent": user_agent,
        },
    )

    return JsonResponse({"status": "ok"})


@login_required
@require_POST
def remove_push_subscription(request):
    """
    Berilgan endpoint bo'yicha push subscription'ni o'chiradi.
    Foydalanuvchi brauzerda bildirishnomalarni o'chirib qo'yganda
    yoki obunadan chiqqanda chaqiriladi.
    """
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Noto'g'ri so'rov formati"}, status=400)

    endpoint = (data.get("endpoint") or "").strip()
    if not endpoint:
        return JsonResponse({"error": "Endpoint ko'rsatilmagan"}, status=400)

    PushSubscription.objects.filter(employee=employee, endpoint=endpoint).delete()

    return JsonResponse({"status": "ok"})


# ─────────────────────────────────────────────────────────────────────────
# PUSH YUBORISH — asosiy funksiya
# ─────────────────────────────────────────────────────────────────────────

def send_push_notification(employee, title, body, url="/", tag=None):
    """
    Berilgan xodimning barcha faol push obunalariga bildirishnoma yuboradi.

    tag — brauzerda notification'larni guruhlashda ishlatiladi. Agar bir xil
    tag bilan bir nechta notification yuborilsa, brauzer eski notification'ni
    JIM (ekranga popup chiqarmasdan) yangisiga almashtiradi. Shuning uchun
    har bir HAQIQIY hodisa (ariza, hujjat) uchun UNIKAL tag berish shart,
    aks holda foydalanuvchi keyingi notification'larni ko'rmay qoladi.
    """
    subscriptions = PushSubscription.objects.filter(employee=employee)
    if not subscriptions.exists():
        return

    dead_ids = []

    payload = {
        "title": title,
        "body": body,
        "url": url,
        "icon": "/static/img/apple-touch-icon.png",
    }
    if tag:
        payload["tag"] = tag

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
                data=json.dumps(payload),
                vapid_private_key=settings.VAPID_PRIVATE_KEY_PEM,
                vapid_claims=dict(settings.VAPID_CLAIMS),
            )
            logger.info(
                "Push yuborildi: employee_id=%s, status=%s, tag=%s",
                employee.id, response.status_code, tag,
            )

        except WebPushException as e:
            status_code = e.response.status_code if e.response else None
            response_text = e.response.text if e.response else None
            logger.error(
                "Push xatosi: employee_id=%s, endpoint=%s, status=%s, body=%s",
                employee.id, sub.endpoint, status_code, response_text,
            )
            if status_code in (404, 410):
                dead_ids.append(sub.id)

        except Exception:
            logger.exception(
                "Push yuborishda kutilmagan xato: employee_id=%s, endpoint=%s",
                employee.id, sub.endpoint,
            )

    if dead_ids:
        PushSubscription.objects.filter(id__in=dead_ids).delete()


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

    eligible_ids = OrderGoal.objects.filter(
        goal=order.goal
    ).values_list("employee_id", flat=True)

    if goal_org_type == "worker":
        if not order.sender or not order.sender.region_id:
            return Employee.objects.none()

        return Employee.objects.filter(
            id__in=eligible_ids,
            region_id=order.sender.region_id,
        ).exclude(organization__type="client")

    elif goal_org_type == "client":
        if not order.sender or not order.sender.region_id:
            return Employee.objects.none()

        return Employee.objects.filter(
            id__in=eligible_ids,
            organization=order.goal.organization,
            region_id=order.sender.region_id,
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
            url="/order-receiver/",
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
        url="/order-sender/",
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
        url="/contact-user/",
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
            url="/contact-user/",
            tag=f"deed-watcher-{deed.id}",
        )