from .models import *
from django.http import JsonResponse


def deed_notifications(request):
    if not request.user.is_authenticated:
        return {}

    user = request.user
    employee = getattr(user, "employee", None)

    # RECEIVER uchun: yangi kelgan dalolatnoma (status viewed)
    receiver_notes = Deed.objects.filter(
        receiver=employee,
        status="viewed"
    )

    # SENDER uchun: tasdiqlangan yoki rad etilgan, hali ko‘rilmagan
    sender_notes = Deed.objects.filter(
        sender=employee,
        sender_seen=False,
        status__in=["approved", "rejected"]
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
    count = all_notes.count()

    return {
        "deed_notifications": all_notes,
        "deed_notification_count": count
    }


def order_notifications(request):
    if not request.user.is_authenticated:
        return {}

    user = request.user

    try:
        employee = user.employee
    except Employee.DoesNotExist:
        return {}

    # 1) Receiver uchun
    receiver_notes = Order.objects.filter(
        receiver=employee,
        status__in=['accepted', 'approved', 'rejected'],
        receiver_seen=False
    )

    # 2) Bosslar uchun
    if employee.is_boss:
        boss_notes = Order.objects.filter(
            status='viewed',
            sender__region=employee.region,
            receiver_seen=False
        ).exclude(receiver=employee)
    else:
        boss_notes = Order.objects.none()

    # 3) Sender uchun
    sender_notes = Order.objects.filter(
        sender=employee,
        status='finished',
        receiver_seen=False
    )

    all_notes = (receiver_notes | boss_notes | sender_notes).order_by('-date_edit')

    return {
        'order_notifications': all_notes,
        'order_notification_count': all_notes.count()
    }





