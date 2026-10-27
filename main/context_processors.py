import functools

from .models import *
from django.core.cache import cache
from django.db.models import Q
from django.conf import settings

CACHED_COUNTS = ("order_notifications", "order_receiver_count", "contact_badge_counts")


def cached_counts(name):
    """
    Har sahifada ishlaydigan og'ir hisoblagichlarni xodim bo'yicha qisqa muddat keshlaydi
    (`settings.CONTEXT_CACHE_SECONDS`, 0 bo'lsa o'chiq). Xodim o'zi o'zgartirgan joylarda
    `invalidate_counts()` bilan darhol yangilanadi.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request):
            ttl = getattr(settings, "CONTEXT_CACHE_SECONDS", 0)
            user = getattr(request, "user", None)
            employee = getattr(user, "employee", None) if user is not None and user.is_authenticated else None
            if not ttl or employee is None:
                return func(request)
            key = f"ctx:{name}:{employee.pk}"
            data = cache.get(key)
            if data is None:
                data = func(request)
                cache.set(key, data, ttl)
            return data
        return wrapper
    return decorator


def invalidate_counts(employee_id):
    """Xodimning keshlangan hisoblagichlarini tozalaydi (u o'zi amal bajargach darhol yangi son ko'rinishi uchun)."""
    cache.delete_many([f"ctx:{name}:{employee_id}" for name in CACHED_COUNTS])


# Xabar beruvchi belgilar: (xodim maydoni, tashkilot turi, holatlar, "ko'rildi" maydoni).
# Sanash (order_unseen_q) va o'chirish (mark_orders_seen) AYNAN shu ro'yxatdan — ikkalasi farqlanib qolmaydi.
ORDER_SEEN_RULES = (
    ("receiver", "worker", ("approved", "canceled"), "receiver_seen"),
    ("receiver", "client", ("accepted", "canceled", "rejected"), "receiver_seen"),
    ("sender", "worker", ("finished", "rejected"), "sender_seen"),
    ("sender", "client", ("approved", "rejected"), "sender_seen"),
    ("user", "client", ("accepted",), "user_seen"),
)


def order_unseen_q(employee):
    q = Q(pk__in=[])
    for who, org_type, statuses, seen in ORDER_SEEN_RULES:
        q |= Q(**{who: employee, "goal__organization__type": org_type, "status__in": statuses, seen: False})
    return q


def mark_orders_seen(employee):
    """Xodimning "yangi" belgilarini o'chiradi va hisoblagich keshini tozalaydi."""
    for who, org_type, statuses, seen in ORDER_SEEN_RULES:
        Order.objects.filter(**{who: employee, "goal__organization__type": org_type, "status__in": statuses, seen: False}).update(**{seen: True})
    invalidate_counts(employee.id)


@cached_counts("order_notifications")
def order_notifications(request):
    empty = {"order_notification_count": 0}

    if not request.user.is_authenticated:
        return empty

    employee = getattr(request.user, "employee", None)
    if not employee:
        return empty

    # order_receiver uchun (worker xodimlari)
    if employee.organization.type == "client":
        worker_goal_ids = OrderGoal.goal.through.objects.none().values_list("goal_id", flat=True)
    else:
        worker_goal_ids = OrderGoal.goal.through.objects.filter(ordergoal__employee=employee).values_list("goal_id", flat=True)

    # order_receiver_barn uchun (client xodimlari, region majburiy)
    if employee.organization.type == "worker" or not employee.region_id:
        barn_goal_ids = OrderGoal.goal.through.objects.none().values_list("goal_id", flat=True)
    else:
        barn_goal_ids = OrderGoal.goal.through.objects.filter(ordergoal__employee=employee).values_list("goal_id", flat=True)

    conditions = (
        order_unseen_q(employee) |
        # biriktirilgan, lekin hali qabul qilinmagan arizalar: belgi qabul qilinganda o'chadi (mark-seen emas)
        Q(receiver=employee, status="viewed", receiver_seen=False) |

        # order_receiver: hali receiver tayinlanmagan, worker goal'lariga ruxsatli
        Q(receiver__isnull=True,
          sender_region=employee.region,
          goal_id__in=worker_goal_ids,
          goal__organization__type="worker",
          status="viewed") |

        # order_receiver_barn: hali receiver tayinlanmagan, client goal'lariga ruxsatli
        Q(receiver__isnull=True,
          goal__organization__type="client",
          goal__organization=employee.organization,
          goal_id__in=barn_goal_ids,
          sender_region_id=employee.region_id,
          status="viewed")
    )

    all_notes = Order.objects.filter(conditions).distinct().order_by("-date_edit")

    return {"order_notification_count": all_notes.count()}


@cached_counts("order_receiver_count")
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
        order_goal_ids = OrderGoal.goal.through.objects.filter(ordergoal__employee=employee).values_list("goal_id", flat=True)

        count = Order.objects.filter(
            sender_region=employee.region,
            goal_id__in=order_goal_ids,
            goal__organization__type="worker",
            status="viewed",
        ).count()

        return {"order_receiver_badge_count": count}

    elif employee.organization.type == "client":
        # order_receiver_barn view bilan bir xil filtr
        if not employee.region_id:
            return empty

        order_goal_ids = OrderGoal.goal.through.objects.filter(ordergoal__employee=employee).values_list("goal_id", flat=True)

        count = Order.objects.filter(
            goal__organization__type="client",
            goal__organization=employee.organization,
            goal_id__in=order_goal_ids,
            sender_region_id=employee.region_id,
            status="viewed",
        ).count()

        return {"order_receiver_badge_count": count}

    return empty


@cached_counts("contact_badge_counts")
def contact_badge_counts(request):
    """Sidebardagi "Xabarlar" bo'limi uchun - "Imzolash uchun" va
    "Kelishish uchun" view'laridagi bilan AYNAN bir xil querysetdan
    hisoblangan sonlar (main/views.py: contact, contact_agrement)."""
    empty = {"contact_badge_count": 0, "contact_agrement_badge_count": 0}

    if not request.user.is_authenticated:
        return empty

    employee = getattr(request.user, "employee", None)
    if not employee:
        return empty

    contact_count = Deed.objects.filter(
        Q(sender_id=employee.id, status_sender="viewed") |
        Q(receiver_id=employee.id, status_receiver="viewed")
    ).distinct().count()

    agrement_count = Deed.objects.filter(
        deedconsent__employee_id=employee.id,
        deedconsent__status="viewed",
    ).distinct().count()

    return {
        "contact_badge_count": contact_count,
        "contact_agrement_badge_count": agrement_count,
    }
