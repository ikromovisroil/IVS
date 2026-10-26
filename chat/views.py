from django.core.exceptions import PermissionDenied

from main.models import Employee
from main.push_views import send_push_notification

from .models import Conversation, Message
from .services import online_info, visible_messages, unread_count


def _current_employee(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")
    return employee


def _serialize_conversation(conv: Conversation, employee: Employee) -> dict:
    other = conv.other_participant(employee)
    last_msg = visible_messages(conv, employee).order_by("-date_creat").first()
    status = online_info(other) if other else {"online": False, "last_seen": None}
    if conv.kind == Conversation.KIND_AI:
        title = "AI Yordamchi"
    elif conv.kind == Conversation.KIND_GROUP:
        title = conv.name or "Guruh"
    elif conv.kind == Conversation.KIND_SAVED:
        title = "Saqlangan xabarlar"
    else:
        title = other.full_name if other else "-"
    return {
        "id": conv.id,
        "kind": conv.kind,
        "title": title,
        "other_id": other.id if other else None,
        "member_count": conv.participants.count() if conv.kind == Conversation.KIND_GROUP else None,
        "is_admin": conv.is_group_admin(employee) if conv.kind == Conversation.KIND_GROUP else None,
        "last_message": ("📎 Fayl" if (last_msg and last_msg.attachment and not last_msg.body) else (last_msg.body[:80] if last_msg else "")),
        "last_message_at": last_msg.date_creat.isoformat() if last_msg else None,
        "unread_count": unread_count(conv, employee),
        "online": status["online"],
        "last_seen": status["last_seen"],
    }


def _notify_recipients(conv: Conversation, sender: Employee, msg: Message) -> None:
    """Suhbatdagi boshqa (AI bo'lmagan) qatnashuvchi(lar)ga push-bildirishnoma."""
    body_preview = msg.body[:150] if msg.body else "📎 Fayl yuborildi"
    title = sender.full_name if conv.kind != Conversation.KIND_GROUP else f"{conv.name}: {sender.full_name}"

    if conv.kind == Conversation.KIND_GROUP:
        recipients = conv.participants.exclude(id=sender.id)
    else:
        other = conv.other_participant(sender)
        recipients = [other] if other else []

    for recipient in recipients:
        send_push_notification(
            recipient, title=title, body=body_preview,
            url="/chat/", tag=f"chat-{conv.id}",
        )


