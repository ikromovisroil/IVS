from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth import get_user_model
from .models import Employee, Rol

User = get_user_model()

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_employee(sender, instance, created, **kwargs):
    if created:
        emp = Employee.objects.create(user=instance)
        Rol.objects.create(employee=emp)

@receiver(post_delete, sender=Employee)
def delete_user_on_employee_delete(sender, instance, **kwargs):
    if instance.user_id:
        User.objects.filter(pk=instance.user_id).delete()