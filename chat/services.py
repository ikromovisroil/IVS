import logging
import shutil
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from main.models import Employee
from .models import Conversation, ConversationClear, Message

logger = logging.getLogger(__name__)


@transaction.atomic
def get_or_create_direct_conversation(employee_a: Employee, employee_b: Employee) -> Conversation:
    """Ikki xodim orasidagi shaxsiy suhbatni topadi, bo'lmasa yaratadi.

    Dublikat bo'lmasligi uchun juftlik har doim ID bo'yicha kichikroq
    `participant_1` bilan normallashtiriladi.
    """
    if employee_a.id == employee_b.id:
        raise ValueError("O'zi bilan suhbat ochib bo'lmaydi")

    p1, p2 = sorted([employee_a, employee_b], key=lambda e: e.id)

    conv = Conversation.objects.filter(
        kind=Conversation.KIND_DIRECT, participant_1=p1, participant_2=p2,
    ).first()
    if conv:
        return conv

    return Conversation.objects.create(
        kind=Conversation.KIND_DIRECT, participant_1=p1, participant_2=p2,
    )


@transaction.atomic
def get_or_create_ai_conversation(employee: Employee) -> Conversation:
    conv = Conversation.objects.filter(
        kind=Conversation.KIND_AI, participant_1=employee,
    ).first()
    if conv:
        return conv
    return Conversation.objects.create(kind=Conversation.KIND_AI, participant_1=employee)


@transaction.atomic
def get_or_create_saved_conversation(employee: Employee) -> Conversation:
    """Telegram'dagi "Saqlangan xabarlar" kabi - xodimning o'zi bilan
    shaxsiy suhbati, eslatma/fayl saqlash uchun."""
    conv = Conversation.objects.filter(
        kind=Conversation.KIND_SAVED, participant_1=employee,
    ).first()
    if conv:
        return conv
    return Conversation.objects.create(kind=Conversation.KIND_SAVED, participant_1=employee)


@transaction.atomic
def create_group_conversation(creator: Employee, name: str, member_ids) -> Conversation:
    """Yangi guruh suhbati yaratadi. Kamida yaratuvchidan tashqari 2 ta
    a'zo bo'lishi kerak (aks holda oddiy shaxsiy suhbatdan farqi qolmaydi)."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Guruh nomini kiriting")
    if len(name) > 100:
        raise ValueError("Guruh nomi juda uzun")

    member_ids = set(int(m) for m in member_ids if str(m).isdigit())
    member_ids.discard(creator.id)
    if len(member_ids) < 2:
        raise ValueError("Guruhda (o'zingizdan tashqari) kamida 2 ta a'zo bo'lishi kerak")

    valid_ids = set(
        Employee.objects.filter(id__in=member_ids).values_list("id", flat=True)
    )
    valid_ids.add(creator.id)

    conv = Conversation.objects.create(kind=Conversation.KIND_GROUP, participant_1=creator, name=name)
    conv.participants.set(valid_ids)
    conv.admins.add(creator)
    return conv


def add_group_members(conv: Conversation, member_ids, allowed_org_id=None) -> list:
    """Guruhga yangi a'zo(lar) qo'shadi. `allowed_org_id` berilsa, faqat shu
    tashkilot xodimlari qo'shiladi (ko'rish doirasi qoidasiga mos). Haqiqatda
    qo'shilgan (avvaldan a'zo bo'lmagan, mavjud) Employee ID'lari qaytariladi."""
    ids = set(int(m) for m in member_ids if str(m).isdigit())
    qs = Employee.objects.filter(id__in=ids)
    if allowed_org_id is not None:
        qs = qs.filter(organization_id=allowed_org_id)
    existing = set(conv.participants.values_list("id", flat=True))
    new_ids = set(qs.values_list("id", flat=True)) - existing
    if new_ids:
        conv.participants.add(*new_ids)
    return list(new_ids)


def remove_group_member(conv: Conversation, member_id: int) -> None:
    """A'zoni guruhdan chiqaradi - shu bilan birga admin bo'lsa, admindan
    ham chiqariladi."""
    conv.participants.remove(member_id)
    conv.admins.remove(member_id)


def set_group_admin(conv: Conversation, member_id: int, is_admin: bool) -> None:
    if is_admin:
        conv.admins.add(member_id)
    else:
        conv.admins.remove(member_id)


def visible_conversations(employee: Employee):
    """Shu xodim ishtirok etgan va o'zi uchun yashirmagan suhbatlar, oxirgi
    faollik bo'yicha."""
    from django.db.models import Q

    return (
        Conversation.objects
        .filter(Q(participant_1=employee) | Q(participant_2=employee) | Q(participants=employee))
        .exclude(hidden_for=employee)
        .distinct()
        .select_related("participant_1", "participant_2")
        .prefetch_related("participants")
        .order_by("-date_edit")
    )


def hide_conversation(conversation: Conversation, employee: Employee) -> None:
    """Suhbatni faqat shu xodim uchun ro'yxatdan yashiradi (WhatsApp'dagi
    "chatni o'chirish" kabi) - ma'lumot o'chmaydi, qarshi tomonga ta'sir
    qilmaydi. Yashirilgan vaqt saqlanadi: suhbat qaytganda ham shundan oldingi
    xabarlar bu xodimga ko'rinmaydi."""
    conversation.hidden_for.add(employee)
    ConversationClear.objects.update_or_create(
        conversation=conversation, employee=employee, defaults={"cleared_at": timezone.now()},
    )


def cleared_at_for(conversation: Conversation, employee: Employee):
    return (
        ConversationClear.objects
        .filter(conversation=conversation, employee=employee)
        .values_list("cleared_at", flat=True)
        .first()
    )


def visible_messages(conversation: Conversation, employee: Employee):
    """Xodim ko'ra oladigan xabarlar: o'chirilmagan va (agar suhbatni "o'chirgan" bo'lsa) shundan keyingilari."""
    qs = conversation.messages.filter(is_deleted=False)
    cleared = cleared_at_for(conversation, employee)
    if cleared:
        qs = qs.filter(date_creat__gt=cleared)
    return qs


def soft_delete_message(msg: Message) -> None:
    """Xabarni "o'chiradi": matn bazada qoladi (ko'rinmaydi), fayl ochiq MEDIA_ROOT'dan yopiq papkaga ko'chiriladi
    (eski havola ishlamaydi). Administrator tiklashi mumkin (restore_message)."""
    msg.is_deleted = True
    msg.deleted_at = timezone.now()
    update_fields = ["is_deleted", "deleted_at"]

    if msg.attachment:
        try:
            src = Path(msg.attachment.path)
            dest_dir = Path(settings.CHAT_PRIVATE_ROOT) / f"{timezone.now():%Y%m}"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"{msg.pk}_{src.name}"
            shutil.move(str(src), str(dest))
            msg.deleted_attachment = str(dest.relative_to(Path(settings.CHAT_PRIVATE_ROOT)))
        except (FileNotFoundError, NotImplementedError, ValueError):
            # Fayl allaqachon yo'q (yoki fayl tizimi emas) — havola baribir olib tashlanadi
            logger.warning("Chat fayli ko'chirilmadi (msg=%s)", msg.pk)
            msg.deleted_attachment = ""
        msg.attachment = None
        update_fields += ["attachment", "deleted_attachment"]

    msg.save(update_fields=update_fields)


def restore_message(msg: Message) -> None:
    """Administrator: o'chirilgan xabarni (va faylini) qaytaradi."""
    update_fields = ["is_deleted", "deleted_at"]
    if msg.deleted_attachment:
        src = Path(settings.CHAT_PRIVATE_ROOT) / msg.deleted_attachment
        if src.exists():
            dest_dir = Path(settings.MEDIA_ROOT) / "chat" / f"{timezone.now():%Y}" / f"{timezone.now():%m}"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / src.name
            shutil.move(str(src), str(dest))
            msg.attachment.name = str(dest.relative_to(Path(settings.MEDIA_ROOT))).replace("\\", "/")
            update_fields.append("attachment")
        msg.deleted_attachment = ""
        update_fields.append("deleted_attachment")
    msg.is_deleted = False
    msg.deleted_at = None
    msg.save(update_fields=update_fields)


def unhide_conversation_for(conversation: Conversation, employee: Employee) -> None:
    """Xodim yashirgan suhbatga yangi xabar kelganda, ro'yxatga qaytarish
    uchun (agar yashirilmagan bo'lsa - no-op)."""
    conversation.hidden_for.remove(employee)


def unread_count(conversation: Conversation, employee: Employee) -> int:
    return visible_messages(conversation, employee).filter(read_at__isnull=True).exclude(sender=employee).count()


def mark_read(conversation: Conversation, employee: Employee):
    """O'qilmagan (o'zi yozmagan) xabarlarni "o'qildi" deb belgilaydi.

    Qaysi xabarlar o'qilgani (ID ro'yxati) qaytariladi - chaqiruvchi shu
    ro'yxatni WebSocket orqali yuboruvchiga "o'qildi" (✓✓) sifatida
    push qilishi uchun."""
    from django.utils import timezone

    qs = conversation.messages.filter(read_at__isnull=True).exclude(sender=employee)
    ids = list(qs.values_list("id", flat=True))
    if ids:
        qs.update(read_at=timezone.now())
    return ids


def touch_online(employee: Employee) -> None:
    from .models import OnlineStatus

    OnlineStatus.objects.update_or_create(employee=employee)


ONLINE_THRESHOLD_SECONDS = 45


def online_info(employee: Employee) -> dict:
    """{"online": bool, "last_seen": iso-str|None} - berilgan xodim uchun."""
    from django.utils import timezone
    from .models import OnlineStatus

    status = OnlineStatus.objects.filter(employee=employee).first()
    if not status:
        return {"online": False, "last_seen": None}

    is_online = (timezone.now() - status.last_seen).total_seconds() < ONLINE_THRESHOLD_SECONDS
    return {"online": is_online, "last_seen": status.last_seen.isoformat()}
