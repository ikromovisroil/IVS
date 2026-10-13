"""
Texnikalarning QR rasmlarini joriy domen (SITE_BASE_URL) bo'yicha qayta yaratadi.
Domen almashganda yoki QR eski manzilni ko'rsatib qolganda ishlatiladi:

    python manage.py regenerate_technics_qr            # hammasi
    python manage.py regenerate_technics_qr --dry-run  # faqat nimalar o'zgarishini ko'rsatadi
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from main.models import Technics


class Command(BaseCommand):
    help = "Texnikalarning QR rasmlarini SITE_BASE_URL bo'yicha qayta yaratadi."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Hech narsa yozmasdan faqat sonini ko'rsatadi")

    def handle(self, *args, **options):
        qs = Technics.objects.all().order_by("id")
        total = qs.count()
        self.stdout.write(f"Manzil: {settings.SITE_BASE_URL.rstrip('/')}/technics/<id>/  |  texnikalar: {total} ta")
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry-run: hech narsa o'zgartirilmadi."))
            return
        done = failed = 0
        for tech in qs.iterator():
            try:
                tech.generate_qr_code(save=True)
                done += 1
            except Exception as exc:   # bitta rasm xatosi qolganlarini to'xtatmasin
                failed += 1
                self.stderr.write(f"#{tech.pk}: {exc}")
        self.stdout.write(self.style.SUCCESS(f"Tayyor: {done} ta, xato: {failed} ta"))
