def chat_notifications(request):
    """Sidebardagi "Chat" bo'limi uchun umumiy o'qilmagan xabarlar soni."""
    empty = {"chat_unread_count": 0}

    if not request.user.is_authenticated:
        return empty

    employee = getattr(request.user, "employee", None)
    if not employee:
        return empty

    from .models import Message
    from .services import visible_conversations

    count = Message.objects.filter(
        conversation__in=visible_conversations(employee),
        read_at__isnull=True,
        is_deleted=False,
    ).exclude(sender=employee).count()

    return {"chat_unread_count": count}
