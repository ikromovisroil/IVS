from celery import Celery
from celery.schedules import crontab

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    # Har kun soat 00:00 da
    "sync-employees-daily": {
        "task": "main.tasks.sync_all_employees",
        "schedule": crontab(hour=0, minute=0),
    },
    # Har oyning 1-kuni, tunda soat 01:00 da - 3 oydan eski AuditLog
    # yozuvlarini tozalaydi (jadval to'lib ketmasligi uchun)
    "cleanup-audit-logs-monthly": {
        "task": "core.tasks.cleanup_old_audit_logs",
        "schedule": crontab(day_of_month=1, hour=1, minute=0),
    },
}