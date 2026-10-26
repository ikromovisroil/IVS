"""Bir martalik tuzatish: "yangi ariza" bildirishnomalari, ariza allaqachon "Yangi" holatda bo'lmasa, o'qilgan qilinadi."""
import re

from django.core.management.base import BaseCommand

from core.models import Notification
from core.signals.notification_signals import close_new_order_notifications
from main.models import Order


class Command(BaseCommand):
    help = "Yangi emas arizalarning o'qilmagan 'order-new-<id>' bildirishnomalarini o'qilgan qiladi."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Faqat sonini ko'rsatadi, o'zgartirmaydi.")

    def handle(self, *args, **opts):
        tags = Notification.objects.filter(tag__startswith="order-new-", is_read=False).values_list("tag", flat=True).distinct()
        ids = {int(m.group(1)) for t in tags if (m := re.fullmatch(r"order-new-(\d+)", t))}
        # Bazada yo'q (o'chirilgan) yoki "Yangi" emas arizalar
        still_new = set(Order.objects.filter(pk__in=ids, status="viewed").values_list("pk", flat=True))
        stale = sorted(ids - still_new)
        if opts["dry_run"]:
            count = Notification.objects.filter(tag__in=[f"order-new-{pk}" for pk in stale], is_read=False).count()
        else:
            count = close_new_order_notifications(stale)
        self.stdout.write(f"{len(stale)} ta ariza, {count} ta bildirishnoma{' (dry-run)' if opts['dry_run'] else ' o‘qilgan qilindi'}.")
