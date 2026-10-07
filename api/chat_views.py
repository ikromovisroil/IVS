"""
Chat — mobil (JWT) API. Saytdagi chat/views.py bilan bir xil qoidalar va xuddi shu servis funksiyalari
(chat/services.py, chat/realtime.py) ishlatiladi; farqi — sessiya o'rniga `Authorization: Bearer <access>`,
JSON (yoki multipart) kirish va `{"detail": ...}` xato formati.

Real vaqt hodisalari — WebSocket: wss://<server>/ws/chat/?token=<access> (qo'llanmaga qarang).
"""
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from chat.ai import generate_ai_reply
from chat.context_processors import chat_notifications
from chat.models import Conversation, Message
from chat.realtime import push_delete, push_edit, push_group_update, push_message, push_read, serialize_message
from chat.services import (
    add_group_members,
    create_group_conversation,
    get_or_create_ai_conversation,
    get_or_create_direct_conversation,
    get_or_create_saved_conversation,
    hide_conversation,
    mark_read,
    remove_group_member,
    set_group_admin,
    soft_delete_message,
    touch_online,
    unhide_conversation_for,
    visible_conversations,
    visible_messages,
)
from chat.validators import validate_chat_attachment
from chat.views import _notify_recipients, _serialize_conversation
from main.models import Employee
from main.push_views import send_push_notification

MAX_BODY = 4000


class ChatBaseView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def employee(self, request):
        emp = getattr(request.user, "employee", None)
        if not emp:
            raise PermissionDenied("Employee yo'q")
        return emp

    @staticmethod
    def ids(data, key):
        """Ro'yxat: JSON `[1,2]` yoki form `members=1&members=2` / `members[]=1`."""
        if hasattr(data, "getlist"):
            raw = data.getlist(key) or data.getlist(f"{key}[]")
        else:
            raw = data.get(key) or []
            if not isinstance(raw, (list, tuple)):
                raw = [raw]
        return [int(x) for x in raw if str(x).isdigit()]

    @staticmethod
    def message_json(request, msg):
        data = serialize_message(msg)
        if data.get("attachment_url"):
            data["attachment_url"] = request.build_absolute_uri(data["attachment_url"])
        return data

    def conversation_for(self, request, pk, employee):
        conv = get_object_or_404(Conversation, pk=pk)
        if not conv.has_participant(employee):
            raise PermissionDenied("Bu suhbat sizga tegishli emas")
        return conv


class ConversationsView(ChatBaseView):
    """GET /api/chat/conversations/ — suhbatlar ro'yxati (oxirgi xabar, o'qilmaganlar soni, onlayn holati)."""

    def get(self, request):
        emp = self.employee(request)
        data = [_serialize_conversation(c, emp) for c in visible_conversations(emp)]
        data.sort(key=lambda c: c["last_message_at"] or "", reverse=True)
        return Response({"results": data})


class ContactsView(ChatBaseView):
    """GET /api/chat/contacts/?q= — yangi suhbat uchun xodimlar (all_organization bo'lmasa faqat o'z tashkiloti, 50 tagacha)."""

    def get(self, request):
        emp = self.employee(request)
        qs = Employee.objects.exclude(id=emp.id).select_related("organization")
        if not request.user.has_perm("main.all_organization"):
            qs = qs.filter(organization_id=emp.organization_id)
        q = (request.query_params.get("q") or "").strip()
        for term in q.split():
            qs = qs.filter(Q(last_name__icontains=term) | Q(first_name__icontains=term))
        qs = qs.order_by("last_name", "first_name")[:50]
        return Response({"results": [{"id": e.id, "name": e.full_name} for e in qs]})


class OpenConversationView(ChatBaseView):
    """POST /api/chat/open/ {"target": "ai" | "saved" | <xodim id>} -> {"conversation_id": id}"""

    def post(self, request):
        emp = self.employee(request)
        target = str(request.data.get("target") or "").strip()
        if target == "ai":
            return Response({"conversation_id": get_or_create_ai_conversation(emp).id})
        if target == "saved":
            return Response({"conversation_id": get_or_create_saved_conversation(emp).id})
        if not target.isdigit():
            raise ValidationError({"detail": "Xodim tanlanmadi"})
        other = get_object_or_404(Employee, pk=int(target))
        if not request.user.has_perm("main.all_organization") and other.organization_id != emp.organization_id:
            raise PermissionDenied("Bu xodim bilan suhbat ocha olmaysiz")
        try:
            conv = get_or_create_direct_conversation(emp, other)
        except ValueError as e:
            raise ValidationError({"detail": str(e)})
        return Response({"conversation_id": conv.id})


class CreateGroupView(ChatBaseView):
    """POST /api/chat/groups/ {"name": "...", "members": [id, ...]} (o'zingizdan tashqari kamida 2 ta a'zo)."""

    def post(self, request):
        emp = self.employee(request)
        name = str(request.data.get("name") or "").strip()
        member_ids = self.ids(request.data, "members")
        if not request.user.has_perm("main.all_organization"):
            allowed = set(
                Employee.objects.filter(id__in=member_ids, organization_id=emp.organization_id)
                .values_list("id", flat=True)
            )
            if len(allowed) != len(set(member_ids)):
                raise PermissionDenied("Faqat o'z tashkilotingiz xodimlarini qo'sha olasiz")
        try:
            conv = create_group_conversation(emp, name, member_ids)
        except ValueError as e:
            raise ValidationError({"detail": str(e)})
        return Response({"conversation_id": conv.id}, status=status.HTTP_201_CREATED)


class MessagesView(ChatBaseView):
    """
    GET /api/chat/conversations/{id}/messages/?page=1 — xabarlar (30 tadan; page=1 — eng yangilari,
    ichida eskidan yangiga tartibda). `has_next_page` — yana eskilari bor. Ochilganda o'qilmaganlar "o'qildi" deb belgilanadi.
    """

    def get(self, request, pk):
        emp = self.employee(request)
        conv = self.conversation_for(request, pk, emp)
        read_ids = mark_read(conv, emp)
        if read_ids:
            push_read(conv, emp.id, read_ids)
        qs = visible_messages(conv, emp).select_related("sender").order_by("-date_creat")
        page_obj = Paginator(qs, 30).get_page(request.query_params.get("page", 1))
        return Response({
            "results": [self.message_json(request, m) for m in reversed(page_obj.object_list)],
            "has_next_page": page_obj.has_next(),
        })


class SendMessageView(ChatBaseView):
    """POST /api/chat/conversations/{id}/send/ — {"body": "..."} yoki multipart (body, attachment: jpg/png/pdf/word/excel, 15 MB gacha)."""

    def post(self, request, pk):
        emp = self.employee(request)
        conv = self.conversation_for(request, pk, emp)
        touch_online(emp)

        body = str(request.data.get("body") or "").strip()
        attachment = request.FILES.get("attachment")
        if not body and not attachment:
            raise ValidationError({"detail": "Xabar bo'sh bo'lmasin"})
        if len(body) > MAX_BODY:
            raise ValidationError({"detail": "Xabar juda uzun"})
        if attachment:
            try:
                validate_chat_attachment(attachment)
            except DjangoValidationError as e:
                raise ValidationError({"detail": "; ".join(e.messages)})

        msg = Message.objects.create(conversation=conv, sender=emp, body=body, attachment=attachment)
        conv.save(update_fields=["date_edit"])

        if conv.kind == Conversation.KIND_GROUP:
            for member in conv.participants.exclude(id=emp.id):
                unhide_conversation_for(conv, member)
        else:
            other = conv.other_participant(emp)
            if other:
                unhide_conversation_for(conv, other)

        push_message(msg)
        _notify_recipients(conv, emp, msg)

        if conv.kind == Conversation.KIND_AI:
            reply_text = generate_ai_reply(emp, conv, body)
            ai_msg = Message.objects.create(conversation=conv, sender=None, is_ai=True, body=reply_text)
            conv.save(update_fields=["date_edit"])
            push_message(ai_msg)
            send_push_notification(
                emp, title="AI Yordamchi", body=reply_text[:150], url="/chat/", tag=f"chat-ai-{conv.id}",
            )

        return Response({"message": self.message_json(request, msg)}, status=status.HTTP_201_CREATED)


class HideConversationView(ChatBaseView):
    """POST /api/chat/conversations/{id}/hide/ — suhbatni faqat o'zim uchun yashirish (qarshi tomon yozsa qaytadi)."""

    def post(self, request, pk):
        emp = self.employee(request)
        hide_conversation(self.conversation_for(request, pk, emp), emp)
        return Response({"ok": True})


class GroupMembersView(ChatBaseView):
    """GET /api/chat/conversations/{id}/members/ — guruh a'zolari (admin/yaratuvchi belgilari bilan)."""

    def get(self, request, pk):
        emp = self.employee(request)
        conv = self.conversation_for(request, pk, emp)
        if conv.kind != Conversation.KIND_GROUP:
            raise ValidationError({"detail": "Bu guruh emas"})
        admin_ids = set(conv.admins.values_list("id", flat=True))
        creator_id = conv.participant_1_id
        members = [
            {"id": m.id, "name": m.full_name, "is_admin": m.id in admin_ids,
             "is_creator": m.id == creator_id, "is_me": m.id == emp.id}
            for m in conv.participants.all().order_by("last_name", "first_name")
        ]
        return Response({
            "results": members,
            "am_admin": emp.id in admin_ids,
            "am_creator": emp.id == creator_id,
        })


def _require_admin(conv, emp):
    if conv.kind != Conversation.KIND_GROUP:
        raise PermissionDenied("Bu guruh emas")
    if not conv.is_group_admin(emp):
        raise PermissionDenied("Bu amal uchun guruh admini bo'lishingiz kerak")


class GroupAddMembersView(ChatBaseView):
    """POST /api/chat/conversations/{id}/members/add/ {"members": [id]} — faqat guruh admini."""

    def post(self, request, pk):
        emp = self.employee(request)
        conv = get_object_or_404(Conversation, pk=pk)
        _require_admin(conv, emp)
        allowed_org = None if request.user.has_perm("main.all_organization") else emp.organization_id
        added = add_group_members(conv, self.ids(request.data, "members"), allowed_org_id=allowed_org)
        if added:
            conv.save(update_fields=["date_edit"])
            push_group_update(conv)
        return Response({"added": added})


class GroupRemoveMemberView(ChatBaseView):
    """
    POST /api/chat/conversations/{id}/members/{member_id}/remove/ — o'zi chiqishi mumkin; admin faqat oddiy
    a'zoni; yaratuvchi (super admin) adminlarni ham chiqara oladi; yaratuvchini hech kim chiqara olmaydi.
    """

    def post(self, request, pk, member_id):
        emp = self.employee(request)
        conv = get_object_or_404(Conversation, pk=pk)
        if conv.kind != Conversation.KIND_GROUP:
            raise ValidationError({"detail": "Bu guruh emas"})
        is_self = member_id == emp.id
        if not conv.has_participant(emp) and not is_self:
            raise PermissionDenied("Bu suhbat sizga tegishli emas")
        if not is_self:
            if conv.participant_1_id == member_id:
                raise PermissionDenied("Guruh yaratuvchisini chiqarib bo'lmaydi")
            if conv.is_group_creator(emp):
                pass
            elif conv.is_group_admin(emp):
                if conv.admins.filter(id=member_id).exists():
                    raise PermissionDenied("Admin boshqa adminni chiqara olmaydi - faqat guruh yaratuvchisi")
            else:
                raise PermissionDenied("Faqat admin boshqa a'zoni chiqara oladi")
        remove_group_member(conv, member_id)
        conv.save(update_fields=["date_edit"])
        push_group_update(conv, removed_member_id=member_id)
        return Response({"ok": True})


class GroupSetAdminView(ChatBaseView):
    """POST /api/chat/conversations/{id}/members/{member_id}/admin/ {"is_admin": true|false} — faqat yaratuvchi."""

    def post(self, request, pk, member_id):
        emp = self.employee(request)
        conv = get_object_or_404(Conversation, pk=pk)
        if conv.kind != Conversation.KIND_GROUP:
            raise PermissionDenied("Bu guruh emas")
        if not conv.is_group_creator(emp):
            raise PermissionDenied("Bu amal uchun guruh yaratuvchisi (super admin) bo'lishingiz kerak")
        if not conv.participants.filter(id=member_id).exists():
            raise ValidationError({"detail": "Bu xodim guruh a'zosi emas"})
        if conv.participant_1_id == member_id:
            raise ValidationError({"detail": "Guruh yaratuvchisi doim admin hisoblanadi"})
        raw = request.data.get("is_admin")
        is_admin = raw is True or str(raw).strip().lower() in ("1", "true")
        set_group_admin(conv, member_id, is_admin)
        push_group_update(conv)
        return Response({"ok": True})


class EditMessageView(ChatBaseView):
    """POST /api/chat/messages/{id}/edit/ {"body": "..."} — faqat o'z xabari."""

    def post(self, request, pk):
        emp = self.employee(request)
        msg = get_object_or_404(Message, pk=pk)
        if msg.sender_id != emp.id:
            raise PermissionDenied("Faqat o'z xabaringizni tahrirlashingiz mumkin")
        if msg.is_deleted:
            raise ValidationError({"detail": "O'chirilgan xabarni tahrirlab bo'lmaydi"})
        body = str(request.data.get("body") or "").strip()
        if not body:
            raise ValidationError({"detail": "Xabar bo'sh bo'lmasin"})
        if len(body) > MAX_BODY:
            raise ValidationError({"detail": "Xabar juda uzun"})
        msg.body = body
        msg.is_edited = True
        msg.edited_at = timezone.now()
        msg.save(update_fields=["body", "is_edited", "edited_at"])
        push_edit(msg)
        return Response({"message": self.message_json(request, msg)})


class DeleteMessageView(ChatBaseView):
    """POST /api/chat/messages/{id}/delete/ — faqat o'z xabari. Xabar ikkala tomonda ko'rinmay qoladi (matn serverda
    saqlanadi, fayl yopiq papkaga ko'chiriladi; havola ishlamaydi)."""

    def post(self, request, pk):
        emp = self.employee(request)
        msg = get_object_or_404(Message, pk=pk)
        if msg.sender_id != emp.id:
            raise PermissionDenied("Faqat o'z xabaringizni o'chirishingiz mumkin")
        if not msg.is_deleted:
            soft_delete_message(msg)
            push_delete(msg)
        return Response({"ok": True})


class UnreadCountView(ChatBaseView):
    """GET /api/chat/unread-count/ — barcha suhbatlar bo'yicha o'qilmagan xabarlar soni (qizil raqam)."""

    def get(self, request):
        self.employee(request)
        return Response({"unread_count": chat_notifications(request)["chat_unread_count"]})


class PingView(ChatBaseView):
    """POST /api/chat/ping/ — "onlayn" holatini yangilash (WebSocket ulanmagan paytda; har 30 soniyada)."""

    def post(self, request):
        touch_online(self.employee(request))
        return Response(status=status.HTTP_204_NO_CONTENT)
