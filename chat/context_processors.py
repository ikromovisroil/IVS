def chat_notifications(request):
    """Sidebardagi "Chat" bo'limi uchun umumiy o'qilmagan xabarlar soni."""
    empty = {"chat_unread_count": 0}

    if not request.user.is_authenticated:
        return empty

    employee = getattr(request.user, "employee", None)
    if not employee:
        return empty

    from django.db.models import F, OuterRef, Q, Subquery

    from .models import ConversationClear, Message
    from .services import visible_conversations

    cleared = ConversationClear.objects.filter(
        conversation=OuterRef("conversation"), employee=employee,
    ).values("cleared_at")[:1]

    count = (
        Message.objects.filter(
            conversation__in=visible_conversations(employee),
            read_at__isnull=True,
            is_deleted=False,
        )
        .exclude(sender=employee)
        .annotate(cleared_at=Subquery(cleared))
        .filter(Q(cleared_at__isnull=True) | Q(date_creat__gt=F("cleared_at")))
        .count()
    )

    return {"chat_unread_count": count}
