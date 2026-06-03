from django.core.management.base import BaseCommand
from main.tasks import sync_all_employees


class Command(BaseCommand):
    help = "Xodimlarni Gateway orqali tekshiradi va yangilaydi"

    def handle(self, *args, **options):
        self.stdout.write("Sinxronizatsiya boshlanmoqda...")
        result = sync_all_employees()
        self.stdout.write(self.style.SUCCESS(
            f"Tugadi: yangilandi={result['updated']}, "
            f"bloklandi={result['blocked']}, "
            f"xato={result['errors']}, "
            f"jami={result['total']}"
        ))