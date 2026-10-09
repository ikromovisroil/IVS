"""
Uchrashuvlar (Zoom): yaratish, bekor qilish, tugatish, eslatma.
Web (chat/meeting_views.py) va Android API (api/meeting_views.py) shu funksiyalardan foydalanadi.
"""
import logging
from datetime import timedelta, timezone as dt_timezone

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from main.models import Employee
from . import zoom
from .models import Meeting

logger = logging.getLogger(__name__)

MIN_DURATION, MAX_DURATION = 15, 480


class MeetingError(Exception):
    """Foydalanuvchiga ko'rsatiladigan xato."""


def can_open(user) -> bool:
    """Uchrashuvlar sahifasiga/API ga kirish: yaratish yoki ko'rish ruxsati."""
    return user.has_perm("chat.add_meeting") or user.has_perm("chat.view_meeting")


def _fmt(dt) -> str:
    return timezone.localtime(dt).strftime("%d.%m.%Y %H:%M")


def buffer_minutes() -> int:
    return max(int(getattr(settings, "MEETING_BUFFER_MINUTES", 10) or 0), 0)


def find_conflict(start_at, duration_minutes, exclude_pk=None):
    """
    Shu vaqt oralig'i (tanaffus bilan) boshqa uchrashuv bilan to'qnashadimi. Hamma uchrashuv bitta Zoom host akkauntida
    o'tadi, bir host bir vaqtda bitta uchrashuv o'tkaza oladi, shuning uchun vaqt hamma xodimlar uchun umumiy.
    Ketma-ket uchrashuvlar orasida kamida `MEETING_BUFFER_MINUTES` (standart 10) daqiqa tanaffus bo'lishi kerak.
    Erta tugatilgan uchrashuv haqiqiy tugash vaqtigacha band hisoblanadi.
    """
    buf = timedelta(minutes=buffer_minutes())
    end_at = start_at + timedelta(minutes=int(duration_minutes))
    candidates = Meeting.objects.filter(
        status__in=[Meeting.STATUS_SCHEDULED, Meeting.STATUS_FINISHED],
        start_at__lt=end_at + buf,
        start_at__gt=start_at - timedelta(minutes=MAX_DURATION) - buf,
    ).select_related("organizer")
    if exclude_pk:
        candidates = candidates.exclude(pk=exclude_pk)
    for other in candidates:
        if other.end_at + buf > start_at:
            return other
    return None


def _conflict_message(other) -> str:
    free_from = timezone.localtime(other.end_at + timedelta(minutes=buffer_minutes()))
    end = timezone.localtime(other.end_at)
    note = f" (orasida {buffer_minutes()} daqiqa tanaffus)" if buffer_minutes() else ""
    return (f"Bu vaqtda boshqa uchrashuv bor ({_fmt(other.start_at)} – {end:%H:%M}). "
            f"Iltimos, undan keyingi vaqtni tanlang: {free_from:%H:%M} dan boshlab{note}.")


def create_meeting(organizer: Employee, title, start_at, duration_minutes, agenda="") -> Meeting:
    if not organizer.user.has_perm("chat.add_meeting"):
        raise MeetingError("Uchrashuv yaratish huquqingiz yo'q")
    title = (title or "").strip()
    if not title:
        raise MeetingError("Mavzu kiritilmadi")
    if len(title) > 200:
        raise MeetingError("Mavzu juda uzun (200 belgigacha)")
    if start_at is None:
        raise MeetingError("Sana va vaqt kiritilmadi")
    if start_at <= timezone.now():
        raise MeetingError("Uchrashuv vaqti kelajakda bo'lishi kerak")
    try:
        duration_minutes = int(duration_minutes)
    except (TypeError, ValueError):
        raise MeetingError("Davomiyligi noto'g'ri")
    if not (MIN_DURATION <= duration_minutes <= MAX_DURATION):
        raise MeetingError(f"Davomiyligi {MIN_DURATION}–{MAX_DURATION} daqiqa orasida bo'lsin")
    if not zoom.zoom_enabled():
        raise MeetingError("Zoom hali sozlanmagan. Administrator bilan bog'laning.")

    # Bir vaqtda ikkita uchrashuv bo'lmaydi (bitta Zoom host): avval tekshiramiz (Zoom'ga murojaatdan oldin)
    conflict = find_conflict(start_at, duration_minutes)
    if conflict:
        raise MeetingError(_conflict_message(conflict))

    try:
        info = zoom.create_meeting(title, start_at.astimezone(dt_timezone.utc), duration_minutes, agenda)
    except zoom.ZoomError as exc:
        raise MeetingError(str(exc))

    invitation = zoom.get_invitation(info["id"])   # xato bo'lsa bo'sh — tugma havolani nusxalaydi

    with transaction.atomic():
        # Zoom javobini kutgan paytda boshqa odam shu vaqtni band qilgan bo'lishi mumkin: qayta tekshiruv
        conflict = find_conflict(start_at, duration_minutes)
        if conflict:
            try:
                zoom.delete_meeting(info["id"])
            except zoom.ZoomError:
                logger.exception("Ortiqcha Zoom uchrashuvi o'chirilmadi (zoom_id=%s)", info["id"])
            raise MeetingError(_conflict_message(conflict))
        meeting = Meeting.objects.create(
            organizer=organizer, title=title, agenda=(agenda or "").strip(), start_at=start_at,
            duration_minutes=duration_minutes, zoom_id=info["id"], join_url=info["join_url"],
            start_url=info["start_url"], password=info["password"], invitation=invitation,
        )

    return meeting


def cancel_meeting(meeting: Meeting, by: Employee) -> Meeting:
    if meeting.organizer_id != by.id:
        raise MeetingError("Faqat tashkilotchi bekor qila oladi")
    if not by.user.has_perm("chat.delete_meeting"):
        raise MeetingError("Uchrashuvni o'chirish huquqingiz yo'q")
    if meeting.status == Meeting.STATUS_CANCELLED:
        return meeting
    try:
        zoom.delete_meeting(meeting.zoom_id)
    except zoom.ZoomError as exc:
        raise MeetingError(str(exc))
    meeting.status = Meeting.STATUS_CANCELLED
    meeting.save(update_fields=["status"])
    return meeting


def finish_meeting(meeting: Meeting, by: Employee) -> Meeting:
    """Uchrashuvni rejadan oldin tugatish: Zoom'da (davom etayotgan bo'lsa) tugatiladi, vaqt bizda bo'shaydi."""
    if meeting.organizer_id != by.id:
        raise MeetingError("Faqat tashkilotchi tugata oladi")
    if meeting.status != Meeting.STATUS_SCHEDULED:
        raise MeetingError("Bu uchrashuvni tugatib bo'lmaydi")
    now = timezone.now()
    if meeting.start_at > now:
        raise MeetingError("Uchrashuv hali boshlanmagan. Uni bekor qilishingiz mumkin.")
    zoom.end_meeting(meeting.zoom_id)
    meeting.ended_at = min(now, meeting.start_at + timedelta(minutes=meeting.duration_minutes))
    meeting.status = Meeting.STATUS_FINISHED
    meeting.save(update_fields=["ended_at", "status"])
    return meeting


def meetings_for(employee: Employee):
    """O'zi yaratgan uchrashuvlar; "ko'rish" ruxsati (chat.view_meeting) bo'lsa — hammaning uchrashuvlari (faqat ko'rish)."""
    qs = Meeting.objects.select_related("organizer").order_by("start_at")
    if employee.user.has_perm("chat.view_meeting"):
        return qs
    return qs.filter(organizer=employee)


def send_due_reminders(minutes_before: int = 10) -> int:
    """Boshlanishiga `minutes_before` daqiqa qolgan uchrashuvlar uchun tashkilotchiga eslatma (bir marta)."""
    from main.push_views import send_push_notification

    now = timezone.now()
    due = Meeting.objects.filter(
        status=Meeting.STATUS_SCHEDULED, reminder_sent=False,
        start_at__gt=now, start_at__lte=now + timedelta(minutes=minutes_before),
    ).select_related("organizer")
    sent = 0
    for meeting in due:
        try:
            send_push_notification(
                meeting.organizer, title="Uchrashuv tez orada boshlanadi",
                body=f"{meeting.title} — {_fmt(meeting.start_at)}", url="/chat/meetings/",
                tag=f"meeting-reminder-{meeting.pk}",
            )
        except Exception:
            logger.exception("Eslatma yuborilmadi (meeting=%s, xodim=%s)", meeting.pk, meeting.organizer_id)
        meeting.reminder_sent = True
        meeting.save(update_fields=["reminder_sent"])
        sent += 1
    return sent
