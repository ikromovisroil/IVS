from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from core.models import AuditLog
from main.models import *

def write_log(instance, action):
    AuditLog.objects.create(
        employee=getattr(instance, "sender", None)
        or getattr(instance, "receiver", None)
        or getattr(instance, "employee", None),
        action=action,
        model=instance.__class__.__name__,
        object_id=instance.pk,
        description=f"{action} {instance.__class__.__name__}",
    )

@receiver(post_save, sender=Order)
def order_saved(sender, instance, created, **kwargs):
    write_log(instance, "create" if created else "update")

@receiver(post_delete, sender=Order)
def order_deleted(sender, instance, **kwargs):
    write_log(instance, "delete")

@receiver(post_save, sender=Deed)
def deed_saved(sender, instance, created, **kwargs):
    write_log(instance, "create" if created else "update")

@receiver(post_delete, sender=Deed)
def deed_deleted(sender, instance, **kwargs):
    write_log(instance, "delete")
