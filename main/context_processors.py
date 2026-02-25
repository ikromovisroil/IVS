from .models import *


def deed_notifications(request):
    if not request.user.is_authenticated:
        return {}

    user = request.user
    employee = getattr(user, "employee", None)

    # RECEIVER uchun: yangi kelgan dalolatnoma (status viewed)
    receiver_notes = Deed.objects.filter(
        receiver=employee,
        status_receiver="viewed"
    )

    # SENDER uchun: tasdiqlangan yoki rad etilgan, hali ko‘rilmagan
    sender_notes = Deed.objects.filter(
        sender=employee,
        sender_seen=False,
        status_sender__in=["approved", "rejected"]
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
        status__in=['viewed', 'approved', 'rejected'],
        receiver_seen=False
    )

    # 3) Sender uchun
    sender_notes = Order.objects.filter(
        sender=employee,
        status__in=['accepted', 'finished'],
        receiver_seen=False
    )

    all_notes = (receiver_notes | sender_notes).order_by('-date_edit')

    return {
        'order_notifications': all_notes,
        'order_notification_count': all_notes.count()
    }





