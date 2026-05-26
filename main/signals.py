from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth import get_user_model
from .models import Employee, Rol

User = get_user_model()

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_employee(sender, instance, created, **kwargs):
    if not created:
        return
    Employee.objects.get_or_create(user=instance)

@receiver(post_save, sender=Employee)
def create_rol(sender, instance, created, **kwargs):
    if not created:
        return
    Rol.objects.get_or_create(employee=instance)

