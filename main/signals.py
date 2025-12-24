from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Employee

@receiver(post_save, sender=User)
def create_employee(sender, instance, created, **kwargs):
    """
    Yangi User yaratilsa → avtomatik Employee yaratamiz.
    """
    if created:
        Employee.objects.create(
            user=instance,
        )
