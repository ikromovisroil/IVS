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
    empty = {"order_notifications": Order.objects.none(), "order_notification_count": 0}

    if not request.user.is_authenticated:
        return empty

    employee = getattr(request.user, "employee", None)
    if not employee:
        return empty

    conditions = (
        # Ijrochi (receiver) — yangi ariza kelganda ham ko'rsin (FIX: "viewed" qo'shildi)
        Q(receiver=employee, goal__organization__type="worker",
          status__in=["viewed", "approved", "canceled"], receiver_seen=False) |
        Q(receiver=employee, goal__organization__type="client",
          status__in=["viewed", "accepted", "canceled", "rejected"], receiver_seen=False) |

        # Yuboruvchi (sender)
        Q(sender=employee, goal__organization__type="worker",
          status__in=["finished", "rejected"], sender_seen=False) |
        Q(sender=employee, goal__organization__type="client",
          status__in=["approved", "rejected"], sender_seen=False) |

        # Tasdiqlovchi (user)
        Q(user=employee, goal__organization__type="client",
          status="accepted", user_seen=False)
    )

    all_notes = Order.objects.filter(conditions).distinct().order_by("-date_edit")

    return {
        "order_notifications": all_notes[:10],
        "order_notification_count": all_notes.count(),
    }