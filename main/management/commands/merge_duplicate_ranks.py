"""
Bir xil nomli lavozimlarni (Rank) birlashtiradi. Hamma eski kodlar `RankCode` jadvali orqali saqlanadi, xodimlar
bitta lavozimga ko'chiriladi, ortiqcha lavozimlar o'chiriladi.

    python manage.py merge_duplicate_ranks            # faqat ko'rsatadi (hech narsa o'zgarmaydi)
    python manage.py merge_duplicate_ranks --apply    # haqiqatan bajaradi (avval bazadan zaxira oling!)

Qolgan lavozim: xodimi eng ko'p bo'lgani (teng bo'lsa - eng kichik ID).
Nomlar apostrof turi, katta-kichik harf va ortiqcha bo'sh joydan qat'i nazar solishtiriladi.
"""
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from main.models import Employee, Rank, RankCode
from main.ranks import normalize_rank_name


class Command(BaseCommand):
    help = "Bir xil nomli lavozimlarni birlashtiradi (kodlari saqlanadi)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Haqiqatan bajarish (aks holda faqat ko'rsatadi)")
        parser.add_argument("--top", type=int, default=15, help="Hisobotda nechta guruh ko'rsatilsin")

    def handle(self, *args, **options):
        apply = options["apply"]
        ranks = list(Rank.objects.annotate(emp_count=Count("employee")).order_by("id"))
        groups = defaultdict(list)
        for rank in ranks:
            key = normalize_rank_name(rank.name)
            if key:
                groups[key].append(rank)
        duplicated = {k: v for k, v in groups.items() if len(v) > 1}

        total_extra = sum(len(v) - 1 for v in duplicated.values())
        self.stdout.write(
            f"Jami lavozim: {len(ranks)} | takrorlangan nom: {len(duplicated)} | ortiqcha yozuv: {total_extra}"
        )
        for key, items in sorted(duplicated.items(), key=lambda kv: -len(kv[1]))[: options["top"]]:
            self.stdout.write(f"  {len(items):>4} ta  {key[:60]}")

        if not duplicated:
            self.stdout.write(self.style.SUCCESS("Birlashtiriladigan narsa yo'q."))
            return
        if not apply:
            self.stdout.write(self.style.WARNING("Bu ko'rish rejimi. Bajarish uchun --apply qo'shing."))
            return

        moved_employees = deleted = linked = 0
        with transaction.atomic():
            for items in duplicated.values():
                canonical = max(items, key=lambda r: (r.emp_count, -r.id))
                for extra in items:
                    if extra.id == canonical.id:
                        continue
                    # Eski kodlar canonical lavozimga bog'lanadi (sinxronizatsiya ularni topishda davom etadi)
                    code = (extra.code or "").strip()
                    if code:
                        link, created = RankCode.objects.get_or_create(code=code, defaults={"rank": canonical})
                        if not created and link.rank_id != canonical.id:
                            link.rank = canonical
                            link.save(update_fields=["rank"])
                        linked += 1
                    RankCode.objects.filter(rank=extra).update(rank=canonical)
                    moved_employees += Employee.objects.filter(rank=extra).update(rank=canonical)
                    extra.delete()
                    deleted += 1

        self.stdout.write(self.style.SUCCESS(
            f"Tayyor: {deleted} ta lavozim o'chirildi, {moved_employees} ta xodim ko'chirildi, {linked} ta kod bog'landi."
        ))
