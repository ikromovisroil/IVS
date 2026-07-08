from .models import *
from django.db.models import Q

def deed_notifications(request):
    if not request.user.is_authenticated:
        return {
            "deed_notifications": Order.objects.none(),
            "deed_notification_count": 0,
        }

    employee = getattr(request.user, "employee", None)
    if not employee:
        return {
            "deed_notifications": Order.objects.none(),
            "deed_notification_count": 0,
        }

    # RECEIVER uchun: yangi kelgan dalolatnoma (status viewed)
    receiver_notes = Deed.objects.filter(
        receiver=employee,
        status_receiver="viewed"
    )

    # SENDER uchun: tasdiqlangan yoki rad etilgan, hali ko‘rilmagan
    sender_notes = Deed.objects.filter(
        sender=employee,
        status_sender="viewed"
    )

    # 3️⃣ KUZATUVCHI: kelishuv talab qilinayotgan yoki o‘zgargan
    watcher_notes = Deed.objects.filter(
        deedconsent__employee=employee,
        deedconsent__status='viewed'
    )

    all_notes = (
            receiver_notes |
            sender_notes |
            watcher_notes
    ).distinct().order_by("-date_edit")

    return {
        "deed_notifications": all_notes[:10],
        "deed_notification_count": all_notes.count(),
    }


def order_notifications(request):
    if not request.user.is_authenticated:
        return {
            "order_notifications": Order.objects.none(),
            "order_notification_count": 0,
        }

    employee = getattr(request.user, "employee", None)
    if not employee:
        return {
            "order_notifications": Order.objects.none(),
            "order_notification_count": 0,
        }

    rol = getattr(employee, "rol", None)
    if not rol:
        return {
            "order_notifications": Order.objects.none(),
            "order_notification_count": 0,
        }

    receiver_notes = Order.objects.none()
    sender_notes = Order.objects.none()
    sender_notes_all = Order.objects.none()
    user_notes = Order.objects.none()

    sender_notes = Order.objects.filter(
        organization_id=4,
        sender=employee,
        status__in=["finished", "rejected"],
        sender_seen=False,
    )

    if getattr(rol, "client", False):
        receiver_notes = Order.objects.filter(
            receiver=employee,
            status__in=["accepted", "canceled", "rejected"],
            receiver_seen=False,
        )

        sender_notes_all = Order.objects.filter(
            organization_id=employee.organization_id,
            sender=employee,
            status__in=["approved", "rejected"],
            sender_seen=False,
        ).exclude(organization_id=4)

        user_notes = Order.objects.filter(
            user=employee,
            status="accepted",
            user_seen=False,
        )
    else:
        receiver_notes = Order.objects.filter(
            receiver=employee,
            status__in=["approved", "canceled"],
            receiver_seen=False,
        )

    all_notes = (
        receiver_notes
        | sender_notes
        | sender_notes_all
        | user_notes
    ).distinct().order_by("-date_edit")

    return {
        "order_notifications": all_notes[:10],
        "order_notification_count": all_notes.count(),
    }