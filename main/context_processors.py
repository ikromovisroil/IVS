from .models import *
from django.db.models import Q
from django.conf import settings


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

    # KUZATUVCHI: kelishuv talab qilinayotgan yoki o‘zgargan
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

    # order_receiver uchun (worker xodimlari)
    if employee.organization.type == "client":
        worker_goal_ids = OrderGoal.objects.none().values_list("goal_id", flat=True)
    else:
        worker_goal_ids = OrderGoal.objects.filter(
            employee=employee
        ).values_list("goal_id", flat=True)

    # order_receiver_barn uchun (client xodimlari, region majburiy)
    if employee.organization.type == "worker" or not employee.region_id:
        barn_goal_ids = OrderGoal.objects.none().values_list("goal_id", flat=True)
    else:
        barn_goal_ids = OrderGoal.objects.filter(
            employee=employee
        ).values_list("goal_id", flat=True)

    conditions = (
        Q(receiver=employee, goal__organization__type="worker",
          status__in=["viewed", "approved", "canceled"], receiver_seen=False) |
        Q(receiver=employee, goal__organization__type="client",
          status__in=["viewed", "accepted", "canceled", "rejected"], receiver_seen=False) |

        Q(sender=employee, goal__organization__type="worker",
          status__in=["finished", "rejected"], sender_seen=False) |
        Q(sender=employee, goal__organization__type="client",
          status__in=["approved", "rejected"], sender_seen=False) |

        Q(user=employee, goal__organization__type="client",
          status="accepted", user_seen=False) |

        # order_receiver: hali receiver tayinlanmagan, worker goal'lariga ruxsatli
        Q(receiver__isnull=True,
          sender__region=employee.region,
          goal_id__in=worker_goal_ids,
          goal__organization__type="worker",
          status="viewed") |

        # order_receiver_barn: hali receiver tayinlanmagan, client goal'lariga ruxsatli
        Q(receiver__isnull=True,
          goal__organization__type="client",
          goal__organization=employee.organization,
          goal_id__in=barn_goal_ids,
          sender__region_id=employee.region_id,
          status="viewed")
    )

    all_notes = Order.objects.filter(conditions).distinct().order_by("-date_edit")

    return {
        "order_notifications": all_notes[:10],
        "order_notification_count": all_notes.count(),
    }


def order_receiver_count(request):
    """
    Sidebar'dagi 'Arizalarni Bajarish' bo'limi uchun,
    order_receiver / order_receiver_barn view'laridagi bilan
    AYNAN bir xil querysetdan hisoblangan son.
    """
    empty = {"order_receiver_badge_count": 0}

    if not request.user.is_authenticated:
        return empty

    employee = getattr(request.user, "employee", None)
    if not employee:
        return empty

    if not employee.organization or not employee.organization.type:
        return empty

    if employee.organization.type == "worker":
        # order_receiver view bilan bir xil filtr
        order_goal_ids = OrderGoal.objects.filter(
            employee=employee
        ).values_list("goal_id", flat=True)

        count = Order.objects.filter(
            sender__region=employee.region,
            goal_id__in=order_goal_ids,
            goal__organization__type="worker",
            status="viewed",
        ).count()

        return {"order_receiver_badge_count": count}

    elif employee.organization.type == "client":
        # order_receiver_barn view bilan bir xil filtr
        if not employee.region_id:
            return empty

        order_goal_ids = OrderGoal.objects.filter(
            employee=employee
        ).values_list("goal_id", flat=True)

        count = Order.objects.filter(
            goal__organization__type="client",
            goal__organization=employee.organization,
            goal_id__in=order_goal_ids,
            sender__region_id=employee.region_id,
            status="viewed",
        ).count()

        return {"order_receiver_badge_count": count}

    return empty


def vapid_context(request):
    """
    VAPID public key'ni har bir sahifaga yetkazadi - frontend JS
    (base.html'dagi push subscription kodi) buni push obunasi
    yaratishda ishlatadi.
    """
    return {"vapid_public_key": getattr(settings, "VAPID_PUBLIC_KEY", "")}