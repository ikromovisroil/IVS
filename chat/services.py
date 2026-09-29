from django.db import transaction

from main.models import Employee
from .models import Conversation, Message


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
    return conv


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
    qilmaydi."""
    conversation.hidden_for.add(employee)


def unhide_conversation_for(conversation: Conversation, employee: Employee) -> None:
    """Xodim yashirgan suhbatga yangi xabar kelganda, ro'yxatga qaytarish
    uchun (agar yashirilmagan bo'lsa - no-op)."""
    conversation.hidden_for.remove(employee)


def unread_count(conversation: Conversation, employee: Employee) -> int:
    return conversation.messages.filter(read_at__isnull=True).exclude(sender=employee).count()


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
