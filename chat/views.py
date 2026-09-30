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
from .realtime import push_delete, push_edit, push_group_update, push_message, push_read, serialize_message
from .services import (
    add_group_members,
    create_group_conversation,
    get_or_create_ai_conversation,
    get_or_create_direct_conversation,
    get_or_create_saved_conversation,
    hide_conversation,
    mark_read,
    online_info,
    remove_group_member,
    set_group_admin,
    touch_online,
    unhide_conversation_for,
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

    if target == "saved":
        conv = get_or_create_saved_conversation(employee)
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
@require_POST
@login_required
def chat_create_group(request):
    employee = _current_employee(request)
    name = (request.POST.get("name") or "").strip()
    member_ids_raw = request.POST.getlist("members[]") or request.POST.getlist("members")

    member_ids = [m for m in member_ids_raw if str(m).isdigit()]
    if not request.user.has_perm("main.all_organization"):
        allowed_ids = set(
            Employee.objects.filter(
                id__in=member_ids, organization_id=employee.organization_id,
            ).values_list("id", flat=True)
        )
        if len(allowed_ids) != len(set(int(m) for m in member_ids)):
            raise PermissionDenied("Faqat o'z tashkilotingiz xodimlarini qo'sha olasiz")

    try:
        conv = create_group_conversation(employee, name, member_ids)
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

    # Qarshi tomon(lar) bu suhbatni "o'zidan o'chirgan" bo'lsa ham, yangi
    # xabar kelganda ro'yxatiga qaytarib qo'yiladi (WhatsApp'dagi kabi).
    if conv.kind == Conversation.KIND_GROUP:
        for member in conv.participants.exclude(id=employee.id):
            unhide_conversation_for(conv, member)
    else:
        other = conv.other_participant(employee)
        if other:
            unhide_conversation_for(conv, other)

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


@never_cache
@require_POST
@login_required
def chat_hide(request, conversation_id):
    """Suhbatni faqat so'ragan xodim uchun ro'yxatdan yashiradi (ma'lumot
    o'chmaydi, qarshi tomonga ta'sir qilmaydi)."""
    employee = _current_employee(request)
    conv = get_object_or_404(Conversation, pk=conversation_id)
    if not conv.has_participant(employee):
        raise PermissionDenied("Bu suhbat sizga tegishli emas")

    hide_conversation(conv, employee)
    return JsonResponse({"ok": True})


def _require_group_admin(conv, employee):
    if conv.kind != Conversation.KIND_GROUP:
        raise PermissionDenied("Bu guruh emas")
    if not conv.is_group_admin(employee):
        raise PermissionDenied("Bu amal uchun guruh admini bo'lishingiz kerak")


def _require_group_creator(conv, employee):
    if conv.kind != Conversation.KIND_GROUP:
        raise PermissionDenied("Bu guruh emas")
    if not conv.is_group_creator(employee):
        raise PermissionDenied("Bu amal uchun guruh yaratuvchisi (super admin) bo'lishingiz kerak")


@never_cache
@require_GET
@login_required
def chat_group_members(request, conversation_id):
    employee = _current_employee(request)
    conv = get_object_or_404(Conversation, pk=conversation_id)
    if not conv.has_participant(employee):
        raise PermissionDenied("Bu suhbat sizga tegishli emas")
    if conv.kind != Conversation.KIND_GROUP:
        return JsonResponse({"error": "Bu guruh emas"}, status=400)

    admin_ids = set(conv.admins.values_list("id", flat=True))
    creator_id = conv.participant_1_id
    members = [
        {
            "id": m.id, "name": m.full_name,
            "is_admin": m.id in admin_ids,
            "is_creator": m.id == creator_id,
            "is_me": m.id == employee.id,
        }
        for m in conv.participants.all().order_by("last_name", "first_name")
    ]
    return JsonResponse({
        "results": members,
        "am_admin": employee.id in admin_ids,
        "am_creator": employee.id == creator_id,
    })


@never_cache
@require_POST
@login_required
def chat_group_add_members(request, conversation_id):
    employee = _current_employee(request)
    conv = get_object_or_404(Conversation, pk=conversation_id)
    _require_group_admin(conv, employee)

    member_ids = request.POST.getlist("members[]") or request.POST.getlist("members")
    allowed_org_id = None if request.user.has_perm("main.all_organization") else employee.organization_id
    added = add_group_members(conv, member_ids, allowed_org_id=allowed_org_id)
    if added:
        conv.save(update_fields=["date_edit"])
        push_group_update(conv)
    return JsonResponse({"added": added})


@never_cache
@require_POST
@login_required
def chat_group_remove_member(request, conversation_id, member_id):
    """A'zoni chiqarish - uch darajali huquq:
    - Oddiy a'zo - hech kimni chiqara olmaydi (faqat o'zi chiqa oladi).
    - Admin - faqat oddiy a'zolarni chiqara oladi (boshqa adminni yoki
      yaratuvchini chiqara olmaydi).
    - Guruh yaratuvchisi (super admin) - adminlarni ham, oddiy a'zolarni
      ham chiqara oladi. Yaratuvchini hech kim (o'zidan tashqari) chiqara
      olmaydi.
    """
    employee = _current_employee(request)
    conv = get_object_or_404(Conversation, pk=conversation_id)
    if conv.kind != Conversation.KIND_GROUP:
        return JsonResponse({"error": "Bu guruh emas"}, status=400)

    is_self = member_id == employee.id
    if not conv.has_participant(employee) and not is_self:
        raise PermissionDenied("Bu suhbat sizga tegishli emas")

    if not is_self:
        if conv.participant_1_id == member_id:
            raise PermissionDenied("Guruh yaratuvchisini chiqarib bo'lmaydi")
        if conv.is_group_creator(employee):
            pass  # super admin - adminlarni ham, oddiy a'zolarni ham chiqara oladi
        elif conv.is_group_admin(employee):
            if conv.admins.filter(id=member_id).exists():
                raise PermissionDenied("Admin boshqa adminni chiqara olmaydi - faqat guruh yaratuvchisi")
        else:
            raise PermissionDenied("Faqat admin boshqa a'zoni chiqara oladi")

    remove_group_member(conv, member_id)
    conv.save(update_fields=["date_edit"])
    push_group_update(conv, removed_member_id=member_id)
    return JsonResponse({"ok": True})


@never_cache
@require_POST
@login_required
def chat_group_set_admin(request, conversation_id, member_id):
    """Admin tayinlash/tushirish - faqat guruh yaratuvchisi (super admin)
    huquqiga ega, oddiy adminlar bunga aralasha olmaydi."""
    employee = _current_employee(request)
    conv = get_object_or_404(Conversation, pk=conversation_id)
    _require_group_creator(conv, employee)

    if not conv.participants.filter(id=member_id).exists():
        return JsonResponse({"error": "Bu xodim guruh a'zosi emas"}, status=400)
    if conv.participant_1_id == member_id:
        return JsonResponse({"error": "Guruh yaratuvchisi doim admin hisoblanadi"}, status=400)

    is_admin = (request.POST.get("is_admin") or "").strip() == "1"

    set_group_admin(conv, member_id, is_admin)
    push_group_update(conv)
    return JsonResponse({"ok": True})


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
