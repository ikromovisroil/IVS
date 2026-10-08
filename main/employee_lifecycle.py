"""
Xodimni "o'chirish" o'rniga FAOLSIZLANTIRISH.

Xodim yozuvi o'chirilsa, uning arizalari (sender/receiver), hujjatlari va materiallaridagi bog'lanishlar bo'shab qoladi
(SET_NULL) va hisobotlardan yo'qoladi. Shu sabab xodim yozuvi saqlanadi, faqat tizimga kirish to'xtatiladi.
"""
from django.db import transaction


def deactivate_employee(employee):
    from core.models import MobileDevice, PushSubscription
    from .models import Technics

    with transaction.atomic():
        user = employee.user
        if user and user.is_active:
            user.is_active = False
            user.save(update_fields=["is_active"])

        # Telegram bot va push bildirishnomalar to'xtatiladi
        employee.telegram_chat = None
        employee.save(update_fields=["telegram_chat"])
        PushSubscription.objects.filter(employee=employee).delete()
        MobileDevice.objects.filter(employee=employee).delete()

        # Xodimga biriktirilgan texnikalar xodimdan ajratiladi (avvalgi o'chirishdagi kabi: bo'lim saqlanadi)
        Technics.objects.filter(employee=employee).update(employee=None)


def activate_employee(employee):
    user = employee.user
    if user and not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])
