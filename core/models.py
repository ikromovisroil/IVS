# core/models.py
from django.db import models
from main.models import Employee


class AuditLog(models.Model):
    ACTIONS = (
        ("login",  "Login"),
        ("logout", "Logout"),
        ("create", "Create"),
        ("update", "Update"),
        ("delete", "Delete"),
    )
    employee    = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True)
    action      = models.CharField(max_length=20, choices=ACTIONS)
    model       = models.CharField(max_length=100)
    object_id   = models.PositiveIntegerField(null=True, blank=True)
    path        = models.CharField(max_length=255, blank=True, default="")
    method      = models.CharField(max_length=10,  blank=True, default="")
    ip          = models.GenericIPAddressField(null=True, blank=True)
    user_agent  = models.TextField(blank=True, default="")
    description = models.TextField(blank=True, default="")
    date_creat  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} {self.model}#{self.object_id} by {self.employee}"

    class Meta:
        db_table            = 'auditLog'
        verbose_name        = "Harakat"
        verbose_name_plural = "Harakatlar"
        ordering            = ["-date_creat"]


class SyncLog(models.Model):
    STATUS = (
        ('success', 'Muvaffaqiyatli'),
        ('partial', 'Qisman xato'),
        ('failed',  'Xatolik'),
    )
    total      = models.PositiveIntegerField(default=0)
    updated    = models.PositiveIntegerField(default=0)
    blocked    = models.PositiveIntegerField(default=0)
    skipped    = models.PositiveIntegerField(default=0)
    errors     = models.PositiveIntegerField(default=0)
    duration   = models.PositiveIntegerField(default=0, help_text="Sekundlarda")
    status     = models.CharField(max_length=20, choices=STATUS, default='success')
    date_creat = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.date_creat.strftime('%Y-%m-%d %H:%M')} | {self.get_status_display()} | jami={self.total}"

    class Meta:
        db_table            = 'synclog'
        verbose_name        = "Sync natijasi"
        verbose_name_plural = "Sync natijalari"
        ordering            = ["-date_creat"]


class SyncEmployeeLog(models.Model):
    RESULT = (
        ('updated', 'Yangilandi'),
        ('blocked', 'Bloklandi'),
        ('error',   'Xato'),
    )
    sync       = models.ForeignKey(SyncLog, on_delete=models.CASCADE,
                                   related_name='employee_logs', db_index=True)
    employee   = models.ForeignKey(Employee, on_delete=models.SET_NULL,
                                   null=True, blank=True, db_index=True)
    pinfl      = models.CharField(max_length=20, blank=True, default="")
    full_name  = models.CharField(max_length=300, blank=True, default="")
    result     = models.CharField(max_length=20, choices=RESULT, db_index=True)
    changes    = models.TextField(blank=True, default="")
    error_msg  = models.TextField(blank=True, default="")
    date_creat = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} ({self.pinfl}) — {self.get_result_display()}"

    class Meta:
        db_table            = 'syncemployeelog'
        verbose_name        = "Xodim sync yozuvi"
        verbose_name_plural = "Xodim sync yozuvlari"
        ordering            = ["-date_creat"]


class PushSubscription(models.Model):
    """
    Har bir brauzer/qurilma uchun push obunasi.
    Bitta xodim bir nechta qurilmadan kirishi mumkin (telefon, kompyuter),
    shuning uchun employee -> ko'p PushSubscription bo'lishi mumkin.
    """
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name="push_subscriptions", db_index=True
    )
    endpoint = models.URLField(max_length=1000, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=200)
    user_agent = models.CharField(max_length=300, null=True, blank=True)
    date_creat = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee} - {self.endpoint[:50]}..."

    class Meta:
        db_table = 'push_subscription'
        verbose_name = "Push obunasi"
        verbose_name_plural = "Push obunalari"
