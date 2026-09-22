# core/tasks.py
import logging

from celery import shared_task
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from .models import AuditLog

logger = logging.getLogger(__name__)

AUDIT_LOG_RETENTION_MONTHS = 3


@shared_task
def cleanup_old_audit_logs():
    """3 oydan eski AuditLog yozuvlarini o'chiradi - jadval cheksiz
    to'lib ketmasligi uchun. Har oyning 1-kuni, tunda ishga tushadi
    (config/celery.py dagi beat_schedule orqali)."""
    cutoff = timezone.now() - relativedelta(months=AUDIT_LOG_RETENTION_MONTHS)
    deleted_count, _ = AuditLog.objects.filter(date_creat__lt=cutoff).delete()
    logger.info("cleanup_old_audit_logs: %d ta %s dan eski yozuv o'chirildi", deleted_count, cutoff.date())
    return {"deleted": deleted_count, "cutoff": cutoff.isoformat()}
