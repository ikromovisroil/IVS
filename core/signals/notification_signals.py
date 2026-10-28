"""Ariza endi "yangi" emas (qabul qilindi, rad etildi, bekor qilindi) — "yangi ariza" bildirishnomalari o'qilgan bo'ladi."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Notification
from chat.models import Meeting
from main.models import Deed, DeedConsent, Order


def close_new_order_notifications(order_ids):
    """Yangi ariza haqidagi (tag="order-new-<id>") o'qilmagan bildirishnomalarni hamma xodimda o'qilgan qiladi."""
    from django.utils import timezone

    tags = [f"order-new-{pk}" for pk in order_ids]
    return Notification.objects.filter(tag__in=tags, is_read=False).update(is_read=True, date_read=timezone.now())


@receiver(post_save, sender=Order)
def order_left_new_status(sender, instance, created, **kwargs):
    """Ariza "Yangi" (viewed) holatdan chiqqanda — boshqa ijrochilarda ham "yangi ariza" bildirishnomasi o'chadi."""
    if not created and instance.status != "viewed":
        close_new_order_notifications([instance.pk])


def close_deed_notifications(tags, employee_id=None):
    """Hujjat bildirishnomalarini (imzolash / kelishish) o'qilgan qiladi; employee_id berilsa — faqat shu xodimda."""
    from django.utils import timezone

    qs = Notification.objects.filter(tag__in=tags, is_read=False)
    if employee_id:
        qs = qs.filter(employee_id=employee_id)
    return qs.update(is_read=True, date_read=timezone.now())


@receiver(post_save, sender=Deed)
def deed_signer_answered(sender, instance, created, **kwargs):
    """Imzolovchi hujjatni imzolasa/rad etsa — "imzolashga yuborildi" bildirishnomasi o'chadi (sahifaga kirmasdan ham).
    Hujjat rad etilgan bo'lsa u tugagan: kelishuvchilardagi bildirishnoma ham o'chadi."""
    if created:
        return
    if instance.status_sender != "viewed" and instance.sender_id:
        close_deed_notifications([f"deed-sender-{instance.pk}"], instance.sender_id)
    if "rejected" in (instance.status_sender, instance.status_receiver):
        close_deed_notifications([f"deed-sender-{instance.pk}", f"deed-watcher-{instance.pk}"])


@receiver(post_save, sender=DeedConsent)
def deed_consent_answered(sender, instance, created, **kwargs):
    """Kelishuvchi kelishsa/rad etsa — "kelishishga yuborildi" bildirishnomasi o'chadi."""
    if not created and instance.status != "viewed" and instance.employee_id:
        close_deed_notifications([f"deed-watcher-{instance.deed_id}"], instance.employee_id)


def close_meeting_reminders(meeting_ids):
    """Uchrashuv eslatmalarini (tag="meeting-reminder-<id>") o'qilgan qiladi."""
    from django.utils import timezone

    tags = [f"meeting-reminder-{pk}" for pk in meeting_ids]
    return Notification.objects.filter(tag__in=tags, is_read=False).update(is_read=True, date_read=timezone.now())


@receiver(post_save, sender=Meeting)
def meeting_no_longer_upcoming(sender, instance, created, **kwargs):
    """Uchrashuv bekor qilinsa yoki yakunlansa — "tez orada boshlanadi" eslatmasi o'chadi."""
    if not created and instance.status != Meeting.STATUS_SCHEDULED:
        close_meeting_reminders([instance.pk])
