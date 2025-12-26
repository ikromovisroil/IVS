from django.core.management.base import BaseCommand

from main.services.api_fetch import fetch_all_employees
from main.services.pinfl_attach import attach_pinfl_if_employee_exists


class Command(BaseCommand):
    help = "API xodimlarini tekshirib, bazada bo‘lsa PINFL biriktiradi"

    def add_arguments(self, parser):
        parser.add_argument("tin", type=str)

    def handle(self, *args, **opts):

        tin = opts["tin"]

        self.stdout.write(self.style.WARNING(
            f"⏳ API yuklanmoqda… {tin}"
        ))

        employees = fetch_all_employees(tin)

        self.stdout.write(self.style.SUCCESS(
            f"📥 {len(employees)} ta xodim qabul qilindi"
        ))

        for emp in employees:
            msg = attach_pinfl_if_employee_exists(emp)
            self.stdout.write(msg)
