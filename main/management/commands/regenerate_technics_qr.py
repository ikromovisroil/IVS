"""
Texnikalarning QR rasmlarini joriy domen (SITE_BASE_URL) bo'yicha qayta yaratadi.
Domen almashganda yoki QR eski manzilni ko'rsatib qolganda ishlatiladi:

    python manage.py regenerate_technics_qr                  # hammasi
    python manage.py regenerate_technics_qr --dry-run        # faqat nimalar o'zgarishini ko'rsatadi
    python manage.py regenerate_technics_qr --start-id 5000  # to'xtab qolgan bo'lsa, shu ID dan davom ettirish

Har 500 ta rasmdan keyin jarayon ko'rsatiladi. To'xtatilsa (Ctrl+C) oxirgi tayyor ID chiqadi.
"""
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from main.models import Technics

PROGRESS_EVERY = 500


class Command(BaseCommand):
    help = "Texnikalarning QR rasmlarini SITE_BASE_URL bo'yicha qayta yaratadi."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Hech narsa yozmasdan faqat sonini ko'rsatadi")
        parser.add_argument("--start-id", type=int, default=0, help="Shu ID dan boshlab (to'xtab qolganda davom ettirish)")

    def handle(self, *args, **options):
        qs = Technics.objects.filter(pk__gte=options["start_id"]).order_by("id")
        total = qs.count()
        self.stdout.write(f"Manzil: {settings.SITE_BASE_URL.rstrip('/')}/technics/<id>/  |  texnikalar: {total} ta")
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry-run: hech narsa o'zgartirilmadi."))
            return

        done = failed = 0
        last_id = None
        started = time.monotonic()
        try:
            for tech in qs.iterator(chunk_size=500):
                try:
                    tech.generate_qr_code(save=True)
                    done += 1
                    last_id = tech.pk
                except Exception as exc:   # bitta rasm xatosi qolganlarini to'xtatmasin
                    failed += 1
                    self.stderr.write(f"#{tech.pk}: {exc}")
                if (done + failed) % PROGRESS_EVERY == 0:
                    elapsed = time.monotonic() - started
                    self.stdout.write(f"{done + failed}/{total}  (oxirgi ID: {tech.pk}, {elapsed:.0f} soniya)", ending="\n")
                    self.stdout.flush()
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING(
                f"\nTo'xtatildi. Tayyor: {done} ta. Davom ettirish: --start-id {(last_id or 0) + 1}"
            ))
            return
        self.stdout.write(self.style.SUCCESS(
            f"Tayyor: {done} ta, xato: {failed} ta  ({time.monotonic() - started:.0f} soniya)"
        ))
