# config/celery.py
from celery import Celery
from celery.schedules import crontab

app = Celery("config")  # ← "config" — project nomi

app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "sync-employees-nightly": {
        "task": "main.tasks.sync_all_employees",  # ← "main" app
        "schedule": crontab(hour=0, minute=30),
    },
}