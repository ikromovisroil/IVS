from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Conversation, Message
from .validators import is_image_ext


def _group_name(employee_id: int) -> str:
    return f"chat_user_{employee_id}"


def _recipient_ids(conv: Conversation) -> set:
    return {conv.participant_1_id, conv.participant_2_id} - {None}


def _send(conv: Conversation, payload: dict) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    for emp_id in _recipient_ids(conv):
        try:
            async_to_sync(channel_layer.group_send)(_group_name(emp_id), payload)
        except Exception:
            pass


def serialize_message(msg: Message) -> dict:
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "sender_id": msg.sender_id,
        "sender_name": ("AI Yordamchi" if msg.is_ai else (msg.sender.full_name if msg.sender_id else "-")),
        "is_ai": msg.is_ai,
        "body": msg.body,
        "attachment_url": msg.attachment.url if msg.attachment else None,
        "attachment_name": (msg.attachment.name.rsplit("/", 1)[-1] if msg.attachment else None),
        "is_image": is_image_ext(msg.attachment.name) if msg.attachment else False,
        "is_edited": msg.is_edited,
        "is_deleted": msg.is_deleted,
        "read_at": msg.read_at.isoformat() if msg.read_at else None,
        "date_creat": msg.date_creat.isoformat(),
    }


def push_message(msg: Message) -> None:
    """Xabarni ikkala qatnashuvchining WebSocket guruhiga jo'natadi.

    Redis (yoki xotiradagi) channel layer ishlamasa ham (masalan lokal
    testda channels o'rnatilmagan holatda ishga tushsa) sahifa funksiyasini
    to'xtatib qo'ymaslik uchun xatolar jimgina e'tiborsiz qoldiriladi -
    xabar bazaga baribir yozilgan, faqat jonli push kelmaydi (foydalanuvchi
    keyingi so'rovda/yangilaganda ko'radi).
    """
    _send(msg.conversation, {"type": "chat.message", "message": serialize_message(msg)})


def push_edit(msg: Message) -> None:
    _send(msg.conversation, {"type": "chat.edit", "message": serialize_message(msg)})


def push_delete(msg: Message) -> None:
    _send(msg.conversation, {"type": "chat.delete", "message": serialize_message(msg)})


def push_read(conv: Conversation, reader_employee_id: int, message_ids: list) -> None:
    if not message_ids:
        return
    _send(conv, {
        "type": "chat.read",
        "conversation_id": conv.id,
        "reader_id": reader_employee_id,
        "message_ids": message_ids,
    })
