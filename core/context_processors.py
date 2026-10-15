def notification_center(request):
    """Tepadagi umumiy qo'ng'iroq uchun: o'qilmagan soni va oxirgi o'qilmagan (yangi) bildirishnomalar."""
    empty = {"notif_unread": 0, "notif_recent": []}
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return empty
    employee = getattr(user, "employee", None)
    if not employee:
        return empty

    from .models import Notification

    unread = Notification.objects.filter(employee=employee, is_read=False)
    return {
        "notif_unread": unread.count(),
        "notif_recent": list(unread.order_by("-date_creat", "-id")[:6]),   # menyuda faqat yangilari
    }
