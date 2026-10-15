"""
Bildirishnomalar markazi: markaziy servis.

Hamma push yuboriladigan joy `main.push_views.send_push_notification()` orqali o'tadi, u esa shu yerdagi `record()` ni
chaqiradi. Shu sabab ariza, hujjat, Zoom, chat va kelajakdagi barcha voqealar avtomatik tarixga yoziladi.

`tag` voqea identifikatori ("order-status-12-finished", "chat-5", "deed-sender-3", "meeting-reminder-9"),
uning birinchi qismi (`order`, `deed`, `chat`, `meeting`) bildirishnoma turini belgilaydi.
"""
import logging

from django.db import transaction
from django.utils import timezone

from .models import Notification

logger = logging.getLogger(__name__)

KIND_BY_PREFIX = {
    "order": Notification.KIND_ORDER,
    "deed": Notification.KIND_DEED,
    "meeting": Notification.KIND_MEETING,
    "chat": Notification.KIND_CHAT,
}


def kind_from_tag(tag):
    prefix = (tag or "").split("-", 1)[0]
    return KIND_BY_PREFIX.get(prefix, Notification.KIND_SYSTEM)


def safe_url(url):
    """Faqat sayt ichidagi yo'l ('/...') ruxsat etiladi (tashqi manzilga yo'naltirib bo'lmasin)."""
    url = (url or "").strip()
    if url.startswith("/") and not url.startswith("//"):
        return url
    return "/"


def record(employee, title, body="", url="/", tag="", kind=None):
    """
    Bildirishnomani tarixga yozadi. Xato bo'lsa asosiy ish (ariza, hujjat...) to'xtamasligi uchun hech qachon
    istisno chiqarmaydi. Bir xil `tag` bilan o'qilmagan bildirishnoma bo'lsa yangi yozuv ochilmaydi:
    mavjudi yangilanadi va `count` oshadi (masalan, bir suhbatdagi ko'p xabar bitta qatorda).
    """
    if employee is None:
        return None
    try:
        kind = kind or kind_from_tag(tag)
        title = (title or "")[:200]
        body = (body or "")[:500]
        url = safe_url(url)[:300]
        tag = (tag or "")[:120]
        with transaction.atomic():
            if tag:
                existing = (
                    Notification.objects.filter(employee=employee, tag=tag, is_read=False)
                    .order_by("-id").first()
                )
                if existing:
                    existing.title, existing.body, existing.url = title, body, url
                    existing.count += 1
                    existing.date_creat = timezone.now()
                    existing.save(update_fields=["title", "body", "url", "count", "date_creat"])
                    return existing
            return Notification.objects.create(
                employee=employee, kind=kind, title=title, body=body, url=url, tag=tag,
            )
    except Exception:
        logger.exception("Bildirishnomani yozishda xato (employee=%s, tag=%s)", getattr(employee, "pk", None), tag)
        return None


def unread_count(employee):
    return Notification.objects.filter(employee=employee, is_read=False).count()


def mark_read(employee, ids):
    """Faqat o'zining bildirishnomalarini o'qilgan qiladi. Qaytaradi: yangilangan soni."""
    return Notification.objects.filter(employee=employee, id__in=list(ids), is_read=False).update(
        is_read=True, date_read=timezone.now(),
    )


def mark_all_read(employee, kind=None):
    qs = Notification.objects.filter(employee=employee, is_read=False)
    if kind:
        qs = qs.filter(kind=kind)
    return qs.update(is_read=True, date_read=timezone.now())


def mark_read_by_tag(employee, *tags):
    """Voqea ko'rilganda (masalan, chat ochilganda) unga tegishli bildirishnomalarni o'qilgan qiladi."""
    return Notification.objects.filter(employee=employee, tag__in=tags, is_read=False).update(
        is_read=True, date_read=timezone.now(),
    )
