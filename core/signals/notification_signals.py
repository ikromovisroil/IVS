"""Ariza endi "yangi" emas (qabul qilindi, rad etildi, bekor qilindi) — "yangi ariza" bildirishnomalari o'qilgan bo'ladi."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Notification
from main.models import Order


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
