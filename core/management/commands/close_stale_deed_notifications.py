"""Bir martalik tuzatish: imzolangan/kelishilgan/rad etilgan hujjatlarning o'qilmagan bildirishnomalari o'qilgan qilinadi."""
import re

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Notification
from main.models import Deed, DeedConsent

TAG = re.compile(r"deed-(sender|watcher)-(\d+)")


class Command(BaseCommand):
    help = "Javob berilgan hujjatlarning o'qilmagan 'deed-sender-<id>' / 'deed-watcher-<id>' bildirishnomalarini o'qilgan qiladi."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Faqat sonini ko'rsatadi, o'zgartirmaydi.")

    def handle(self, *args, **opts):
        rows = [
            (pk, employee_id, m.group(1), int(m.group(2)))
            for pk, employee_id, tag in Notification.objects.filter(is_read=False, tag__regex=r"^deed-(sender|watcher)-\d+$")
            .values_list("pk", "employee_id", "tag")
            if (m := TAG.fullmatch(tag))
        ]
        deed_ids = {r[3] for r in rows}
        deeds = {
            d.pk: d for d in Deed.objects.filter(pk__in=deed_ids).only("pk", "sender_id", "status_sender", "status_receiver")
        }
        answered = set(
            DeedConsent.objects.filter(deed_id__in=deed_ids).exclude(status="viewed").values_list("deed_id", "employee_id")
        )

        stale = []
        for pk, employee_id, kind, deed_id in rows:
            deed = deeds.get(deed_id)
            if deed is None or "rejected" in (deed.status_sender, deed.status_receiver):
                stale.append(pk)    # hujjat o'chirilgan yoki rad etilgan — tugagan
            elif kind == "sender" and deed.sender_id == employee_id and deed.status_sender != "viewed":
                stale.append(pk)
            elif kind == "watcher" and (deed_id, employee_id) in answered:
                stale.append(pk)

        if opts["dry_run"]:
            count = len(stale)
        else:
            count = Notification.objects.filter(pk__in=stale).update(is_read=True, date_read=timezone.now())
        self.stdout.write(f"{count} ta bildirishnoma{' (dry-run)' if opts['dry_run'] else ' o‘qilgan qilindi'}.")
