from celery import Celery
from celery.schedules import crontab

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    # Har kun soat 12:00 da
    "sync-employees-daily": {
        "task": "main.tasks.sync_all_employees",
        "schedule": crontab(hour=12, minute=0),
    },
}
