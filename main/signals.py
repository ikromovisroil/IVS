from django.apps import apps
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth import get_user_model
from .models import Employee
from .uz_text import NORMALIZED_FIELDS, normalize_og

User = get_user_model()

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_employee(sender, instance, created, **kwargs):
    if not created:
        return
    Employee.objects.get_or_create(user=instance)


def _normalize_apostrophes(sender, instance, **kwargs):
    """Nom va F.I.Sh. maydonlarida o' va g' -> o‘ va g‘ (Gateway sinxronizatsiyasi va qo'lda kiritish ham)."""
    for field in NORMALIZED_FIELDS.get(sender.__name__, ()):
        value = getattr(instance, field, None)
        if isinstance(value, str):
            setattr(instance, field, normalize_og(value))


for _name in NORMALIZED_FIELDS:
    pre_save.connect(_normalize_apostrophes, sender=apps.get_model("main", _name), dispatch_uid=f"og_apostrophe_{_name}")
