"""Mavjud ma'lumotda o' va g' ni o‘ va g‘ ga almashtiradi (tashkilot, bo'lim, boshqarma, F.I.Sh., lavozim va h.k.).

    python manage.py normalize_apostrophes           # faqat ko'rsatadi (hech narsa o'zgarmaydi)
    python manage.py normalize_apostrophes --apply   # o'zgartiradi

Yangi va o'zgartirilgan yozuvlar saqlashda o'zi tuzatiladi (main/signals.py). Bu buyruq faqat eski ma'lumot uchun.
Yozuvlar queryset.update() bilan yoziladi: "o'zgartirilgan sana" (date_edit) va signallar ta'sirlanmaydi.
"""
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from main.uz_text import _APOS, NORMALIZED_FIELDS, normalize_og


class Command(BaseCommand):
    help = "O' va G' dan keyingi apostrofni o‘ / g‘ ga keltiradi (standart: faqat ko'rsatadi)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Haqiqatan o'zgartirish (bo'lmasa — faqat ko'rsatadi)")

    def handle(self, *args, apply, **options):
        total_rows = 0
        with transaction.atomic():
            for model_name, fields in NORMALIZED_FIELDS.items():
                model = apps.get_model("main", model_name)
                has_apos = Q()
                for field in fields:
                    for char in _APOS:
                        if char != "‘":
                            has_apos |= Q(**{f"{field}__contains": char})
                changed = []
                for row in model.objects.filter(has_apos).values("pk", *fields):
                    new = {f: normalize_og(row[f]) for f in fields if row[f]}
                    diff = {f: v for f, v in new.items() if v != row[f]}
                    if diff:
                        changed.append((row, diff))
                if not changed:
                    continue
                total_rows += len(changed)
                self.stdout.write(f"{model_name}: {len(changed)} ta yozuv")
                for row, diff in changed[:3]:
                    f = next(iter(diff))
                    self.stdout.write(f"    #{row['pk']} {f}: {row[f]!r} -> {diff[f]!r}")
                if apply:
                    for row, diff in changed:
                        model.objects.filter(pk=row["pk"]).update(**diff)
        if apply:
            self.stdout.write(self.style.SUCCESS(f"O'zgartirildi: {total_rows} ta yozuv."))
        else:
            self.stdout.write(self.style.WARNING(f"Hech narsa o'zgartirilmadi (ko'rib chiqish): {total_rows} ta yozuv o'zgaradi. --apply bilan o'zgartiring."))
