from celery import shared_task


@shared_task
def send_meeting_reminders():
    """Har daqiqada: boshlanishiga 10 daqiqa qolgan Zoom uchrashuvlar uchun eslatma yuboradi (bir marta)."""
    from .meetings import send_due_reminders

    return send_due_reminders()
