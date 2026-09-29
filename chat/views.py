from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from main.models import Employee
from main.push_views import send_push_notification

from .ai import generate_ai_reply
from .models import Conversation, Message
from .realtime import push_delete, push_edit, push_message, push_read, serialize_message
from .services import (
    get_or_create_ai_conversation,
    get_or_create_direct_conversation,
    mark_read,
    online_info,
    touch_online,
    unread_count,
    visible_conversations,
)
from .validators import validate_chat_attachment


def _current_employee(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")
    return employee


def _serialize_conversation(conv: Conversation, employee: Employee) -> dict:
    other = conv.other_participant(employee)
    last_msg = conv.messages.order_by("-date_creat").first()
    status = online_info(other) if other else {"online": False, "last_seen": None}
    return {
        "id": conv.id,
        "kind": conv.kind,
        "title": "AI Yordamchi" if conv.kind == Conversation.KIND_AI else (other.full_name if other else "-"),
        "other_id": other.id if other else None,
        "last_message": ("📎 Fayl" if (last_msg and last_msg.attachment and not last_msg.body) else (last_msg.body[:80] if last_msg else "")),
        "last_message_at": last_msg.date_creat.isoformat() if last_msg else None,
        "unread_count": unread_count(conv, employee),
        "online": status["online"],
        "last_seen": status["last_seen"],
    }


@never_cache
@require_GET
@login_required
def chat_page(request):
    employee = _current_employee(request)
    return render(request, "chat/chat.html", {"employee": employee})


@never_cache
@require_GET
@login_required
def chat_conversations(request):
    employee = _current_employee(request)
    convs = visible_conversations(employee)
    data = [_serialize_conversation(c, employee) for c in convs]
    data.sort(key=lambda c: c["last_message_at"] or "", reverse=True)
    return JsonResponse({"results": data})


@never_cache
@require_GET
@login_required
def chat_contacts(request):
    """Yangi suhbat boshlash uchun xodimlar ro'yxati - `all_organization`
    huquqi bo'lmasa faqat o'z tashkiloti (boshqa tashkilot xodimlarining
    ismi/mavjudligi bilinib qolmasligi uchun - hozirgi ko'rish doirasi
    qoidalariga mos)."""
    employee = _current_employee(request)
    q = (request.GET.get("q") or "").strip()

    qs = Employee.objects.exclude(id=employee.id).select_related("organization")
    if not request.user.has_perm("main.all_organization"):
        qs = qs.filter(organization_id=employee.organization_id)
    if q:
        terms = q.split()
        query = Q()
        for term in terms:
            query &= (Q(last_name__icontains=term) | Q(first_name__icontains=term))
        qs = qs.filter(query)

    qs = qs.order_by("last_name", "first_name")[:50]
    results = [{"id": e.id, "name": e.full_name} for e in qs]
    return JsonResponse({"results": results})


@never_cache
@require_POST
@login_required
def chat_open(request):
    employee = _current_employee(request)
    target = (request.POST.get("target") or "").strip()

    if target == "ai":
        conv = get_or_create_ai_conversation(employee)
        return JsonResponse({"conversation_id": conv.id})

    if not target.isdigit():
        return JsonResponse({"error": "Xodim tanlanmadi"}, status=400)

    other = get_object_or_404(Employee, pk=int(target))
    if not request.user.has_perm("main.all_organization") and other.organization_id != employee.organization_id:
        raise PermissionDenied("Bu xodim bilan suhbat ocha olmaysiz")

    try:
        conv = get_or_create_direct_conversation(employee, other)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"conversation_id": conv.id})


@never_cache
@require_GET
@login_required
def chat_messages(request, conversation_id):
    employee = _current_employee(request)
    conv = get_object_or_404(Conversation, pk=conversation_id)
    if not conv.has_participant(employee):
        raise PermissionDenied("Bu suhbat sizga tegishli emas")

    read_ids = mark_read(conv, employee)
    if read_ids:
        push_read(conv, employee.id, read_ids)

    # O'chirilgan xabarlar butunlay ko'rsatilmaydi (baza yozuvi audit uchun
    # saqlanadi, lekin "Xabar o'chirildi" kabi izsiz ham chiqmaydi).
    qs = conv.messages.filter(is_deleted=False).select_related("sender").order_by("-date_creat")
    page_number = request.GET.get("page", 1)
    page_obj = Paginator(qs, 30).get_page(page_number)
    results = [serialize_message(m) for m in reversed(page_obj.object_list)]
    return JsonResponse({
        "results": results,
        "has_next_page": page_obj.has_previous(),  # eski xabarlar tepada
    })


@never_cache
@require_POST
@login_required
def chat_send(request, conversation_id):
    employee = _current_employee(request)
    conv = get_object_or_404(Conversation, pk=conversation_id)
    if not conv.has_participant(employee):
        raise PermissionDenied("Bu suhbat sizga tegishli emas")

    touch_online(employee)

    body = (request.POST.get("body") or "").strip()
    attachment = request.FILES.get("attachment")

    if not body and not attachment:
        return JsonResponse({"error": "Xabar bo'sh bo'lmasin"}, status=400)
    if len(body) > 4000:
        return JsonResponse({"error": "Xabar juda uzun"}, status=400)
    if attachment:
        try:
            validate_chat_attachment(attachment)
        except ValidationError as e:
            return JsonResponse({"error": "; ".join(e.messages)}, status=400)

    msg = Message.objects.create(conversation=conv, sender=employee, body=body, attachment=attachment)
    conv.save(update_fields=["date_edit"])
    push_message(msg)
    _notify_recipients(conv, employee, msg)

    if conv.kind == Conversation.KIND_AI:
        reply_text = generate_ai_reply(employee, conv, body)
        ai_msg = Message.objects.create(conversation=conv, sender=None, is_ai=True, body=reply_text)
        conv.save(update_fields=["date_edit"])
        push_message(ai_msg)
        send_push_notification(
            employee, title="AI Yordamchi", body=reply_text[:150],
            url="/chat/", tag=f"chat-ai-{conv.id}",
        )

    return JsonResponse({"message": serialize_message(msg)})


def _notify_recipients(conv: Conversation, sender: Employee, msg: Message) -> None:
    """Suhbatdagi boshqa (AI bo'lmagan) qatnashuvchiga push-bildirishnoma."""
    other = conv.other_participant(sender)
    if not other:
        return
    body_preview = msg.body[:150] if msg.body else "📎 Fayl yuborildi"
    send_push_notification(
        other, title=f"{sender.full_name}", body=body_preview,
        url="/chat/", tag=f"chat-{conv.id}",
    )


@never_cache
@require_POST
@login_required
def chat_edit(request, message_id):
    employee = _current_employee(request)
    msg = get_object_or_404(Message, pk=message_id)
    if msg.sender_id != employee.id:
        raise PermissionDenied("Faqat o'z xabaringizni tahrirlashingiz mumkin")
    if msg.is_deleted:
        return JsonResponse({"error": "O'chirilgan xabarni tahrirlab bo'lmaydi"}, status=400)

    body = (request.POST.get("body") or "").strip()
    if not body:
        return JsonResponse({"error": "Xabar bo'sh bo'lmasin"}, status=400)
    if len(body) > 4000:
        return JsonResponse({"error": "Xabar juda uzun"}, status=400)

    msg.body = body
    msg.is_edited = True
    msg.edited_at = timezone.now()
    msg.save(update_fields=["body", "is_edited", "edited_at"])
    push_edit(msg)
    return JsonResponse({"message": serialize_message(msg)})


@never_cache
@require_POST
@login_required
def chat_delete(request, message_id):
    employee = _current_employee(request)
    msg = get_object_or_404(Message, pk=message_id)
    if msg.sender_id != employee.id:
        raise PermissionDenied("Faqat o'z xabaringizni o'chirishingiz mumkin")

    msg.is_deleted = True
    msg.deleted_at = timezone.now()
    msg.body = ""
    if msg.attachment:
        msg.attachment.delete(save=False)
        msg.attachment = None
    msg.save(update_fields=["is_deleted", "deleted_at", "body", "attachment"])
    push_delete(msg)
    return JsonResponse({"ok": True})
