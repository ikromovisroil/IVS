import json
from pywebpush import webpush, WebPushException
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from core.models import PushSubscription


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


def send_push_notification(employee, title, body, url="/"):
    """
    Berilgan xodimning BARCHA qurilmalariga push xabar yuboradi.

    Foydalanish namunasi:
        send_push_notification(
            order.receiver,
            "Yangi ariza",
            f"#{order.id} arizasi sizga tayinlandi",
            url="/order-receiver/"
        )
    """
    subscriptions = PushSubscription.objects.filter(employee=employee)

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url,
        "icon": "/static/img/apple-touch-icon.png",
    })

    dead_ids = []

    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh,
                        "auth": sub.auth,
                    },
                },
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY_PEM,
                vapid_claims=dict(settings.VAPID_CLAIMS),
            )
        except WebPushException as ex:
            status_code = getattr(ex.response, "status_code", None)
            if status_code in (404, 410):
                dead_ids.append(sub.id)

    if dead_ids:
        PushSubscription.objects.filter(id__in=dead_ids).delete()


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