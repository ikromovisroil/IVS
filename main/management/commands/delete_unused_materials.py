"""Tashkilotning arizaga biriktirilmagan materiallarini (va ularning kirim-chiqim yozuvlarini) bazadan o'chiradi.

    python manage.py delete_unused_materials --organization 1            # faqat ko'rsatadi (hech narsa o'chmaydi)
    python manage.py delete_unused_materials --organization 1 --apply    # o'chiradi

Arizaga (OrderMaterial) biriktirilgan materiallarga tegilmaydi. Material kirim-chiqim yozuvlariga (MaterialMovement)
PROTECT bilan bog'langan, shuning uchun ular materiallar bilan birga o'chiriladi. QAYTARIB BO'LMAYDI: oldin baza zaxirasini oling.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from main.models import Material, MaterialMovement, Organization, OrderMaterial


class Command(BaseCommand):
    help = "Tashkilotning arizaga biriktirilmagan materiallarini kirim-chiqim yozuvlari bilan o'chiradi (standart: faqat ko'rsatadi)."

    def add_arguments(self, parser):
        parser.add_argument("--organization", type=int, required=True, help="Tashkilot ID si")
        parser.add_argument("--apply", action="store_true", help="Haqiqatan o'chirish (bo'lmasa — faqat ko'rsatadi)")

    def handle(self, *args, organization, apply, **options):
        org = Organization.objects.filter(pk=organization).first()
        if org is None:
            raise CommandError(f"Tashkilot topilmadi: {organization}")

        in_orders = OrderMaterial.objects.filter(material__organization=org).values("material_id")
        free = Material.objects.filter(organization=org).exclude(pk__in=in_orders)
        movements = MaterialMovement.objects.filter(material__in=free)
        total = Material.objects.filter(organization=org).count()
        free_count, movement_count = free.count(), movements.count()

        self.stdout.write(f"Tashkilot: {org.name} (id={org.pk})")
        self.stdout.write(f"Jami materiallar: {total} | arizaga biriktirilgan (qoladi): {total - free_count} | o'chiriladi: {free_count}")
        self.stdout.write(f"Ular bilan birga o'chadigan kirim-chiqim yozuvlari: {movement_count}")
        for m in free.order_by("name")[:10]:
            self.stdout.write(f"  - #{m.pk} {m.name} ({m.number})")
        if free_count > 10:
            self.stdout.write(f"  ... va yana {free_count - 10} ta")

        if not apply:
            self.stdout.write(self.style.WARNING("Hech narsa o'chirilmadi (ko'rib chiqish). O'chirish uchun --apply qo'shing."))
            return
        if not free_count:
            self.stdout.write("O'chiriladigan material yo'q.")
            return
        with transaction.atomic():
            deleted_movements = movements.delete()[0]
            deleted_materials = Material.objects.filter(pk__in=list(free.values_list("pk", flat=True))).delete()[0]
        self.stdout.write(self.style.SUCCESS(f"O'chirildi: {deleted_materials} ta material, {deleted_movements} ta kirim-chiqim yozuvi."))
