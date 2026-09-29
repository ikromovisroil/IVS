from django.db import models

from main.models import Employee
from .validators import validate_chat_attachment


class Conversation(models.Model):
    """Ikki xodim orasidagi (yoki xodim va AI yordamchi orasidagi) suhbat.

    Telegram'dagi kabi - har bir juftlik uchun bitta doimiy suhbat. AI bilan
    suhbatda `participant_2` bo'sh qoladi, `kind="ai"` bilan belgilanadi.
    """

    KIND_DIRECT = "direct"
    KIND_AI = "ai"
    KIND_CHOICES = [
        (KIND_DIRECT, "Shaxsiy suhbat"),
        (KIND_AI, "AI Yordamchi"),
    ]

    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=KIND_DIRECT, db_index=True)
    participant_1 = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="conversations_as_p1", db_index=True,
    )
    participant_2 = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="conversations_as_p2",
        null=True, blank=True, db_index=True,
    )

    date_creat = models.DateTimeField(auto_now_add=True)
    date_edit = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chat_conversation"
        verbose_name = "Suhbat"
        verbose_name_plural = "Suhbatlar"
        # DIQQAT: bitta juftlik uchun bitta suhbat bo'lishi (dublikat
        # bo'lmasligi) DB constraint orqali emas, `get_or_create_conversation()`
        # orqali ta'minlanadi - chunki AI suhbatida participant_2 NULL bo'lib,
        # NULL ustunli UniqueConstraint kutilganidek ishlamaydi (NULL != NULL).
        indexes = [
            models.Index(fields=["participant_1", "date_edit"]),
            models.Index(fields=["participant_2", "date_edit"]),
        ]

    def __str__(self):
        if self.kind == self.KIND_AI:
            return f"{self.participant_1} - AI Yordamchi"
        return f"{self.participant_1} - {self.participant_2}"

    def other_participant(self, employee):
        """Berilgan xodim uchun suhbatdoshi (AI suhbatida - None)."""
        if self.kind == self.KIND_AI:
            return None
        if self.participant_1_id == employee.id:
            return self.participant_2
        return self.participant_1

    def has_participant(self, employee):
        return employee.id in (self.participant_1_id, self.participant_2_id)


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages", db_index=True,
    )
    # sender=None -> AI yordamchi yozgan xabar.
    sender = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="chat_messages_sent", db_index=True,
    )
    body = models.TextField(blank=True)
    attachment = models.FileField(
        upload_to="chat/%Y/%m/", null=True, blank=True, validators=[validate_chat_attachment],
    )
    is_ai = models.BooleanField(default=False, db_index=True)

    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    date_creat = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "chat_message"
        verbose_name = "Xabar"
        verbose_name_plural = "Xabarlar"
        ordering = ["date_creat"]

    def __str__(self):
        who = "AI" if self.is_ai else (self.sender.full_name if self.sender_id else "-")
        preview = (self.body or "")[:30]
        return f"{who}: {preview}"


class OnlineStatus(models.Model):
    """Xodimning oxirgi faollik vaqti - "Onlayn"/"Oxirgi faollik" ko'rsatish
    uchun. Chat WebSocket ulanishi va ping'lar orqali yangilanadi."""

    employee = models.OneToOneField(
        Employee, on_delete=models.CASCADE, related_name="chat_online_status", db_index=True,
    )
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chat_online_status"
        verbose_name = "Onlayn holati"
        verbose_name_plural = "Onlayn holatlari"

    def __str__(self):
        return f"{self.employee} - {self.last_seen}"
