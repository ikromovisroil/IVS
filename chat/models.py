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
    KIND_GROUP = "group"
    KIND_SAVED = "saved"
    KIND_CHOICES = [
        (KIND_DIRECT, "Shaxsiy suhbat"),
        (KIND_AI, "AI Yordamchi"),
        (KIND_GROUP, "Guruh"),
        (KIND_SAVED, "Saqlangan xabarlar"),
    ]

    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=KIND_DIRECT, db_index=True)
    # direct/ai uchun: participant_1/participant_2 ikki tomon.
    # group uchun: participant_1 - guruh yaratuvchisi, participant_2 - bo'sh,
    # haqiqiy a'zolar ro'yxati - `participants` (M2M).
    participant_1 = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="conversations_as_p1", db_index=True,
    )
    participant_2 = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="conversations_as_p2",
        null=True, blank=True, db_index=True,
    )
    # Faqat kind="group" uchun:
    name = models.CharField(max_length=100, null=True, blank=True, verbose_name="Guruh nomi")
    participants = models.ManyToManyField(Employee, blank=True, related_name="group_conversations")
    # Guruh adminlari - a'zo qo'shish/o'chirish va admin tayinlash huquqiga
    # ega (Telegram'dagi kabi). Yaratuvchi avtomatik admin bo'ladi.
    admins = models.ManyToManyField(Employee, blank=True, related_name="chat_admin_groups")

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
        if self.kind == self.KIND_GROUP:
            return f"Guruh: {self.name}"
        if self.kind == self.KIND_SAVED:
            return f"{self.participant_1} - Saqlangan xabarlar"
        return f"{self.participant_1} - {self.participant_2}"

    def other_participant(self, employee):
        """Berilgan xodim uchun suhbatdoshi (AI suhbatida va guruhda - None)."""
        if self.kind != self.KIND_DIRECT:
            return None
        if self.participant_1_id == employee.id:
            return self.participant_2
        return self.participant_1

    def has_participant(self, employee):
        if self.kind == self.KIND_GROUP:
            return self.participants.filter(id=employee.id).exists()
        return employee.id in (self.participant_1_id, self.participant_2_id)

    def is_group_admin(self, employee):
        return self.kind == self.KIND_GROUP and self.admins.filter(id=employee.id).exists()

    def is_group_creator(self, employee):
        """Guruh yaratuvchisi - "super admin": oddiy adminlar boshqa
        adminni chiqara olmaydi/admin qila olmaydi, faqat yaratuvchi
        buni qila oladi (`participant_1` guruh uchun yaratuvchini
        anglatadi, ko'ring yuqoridagi izoh)."""
        return self.kind == self.KIND_GROUP and self.participant_1_id == employee.id

    # "O'zimdan o'chirish" (WhatsApp uslubida) - suhbat ma'lumoti o'chmaydi,
    # faqat shu xodim uchun ro'yxatdan yashiriladi. Qarshi tomon yangi xabar
    # yozsa, avtomatik qayta paydo bo'ladi (services.get_or_create_direct_conversation
    # emas, chat_send o'zi tozalaydi).
    hidden_for = models.ManyToManyField(Employee, blank=True, related_name="hidden_conversations")


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
    # Yumshoq o'chirish: matn bazada saqlanadi (faqat ko'rinmaydi), fayl esa ochiq papkadan yopiq papkaga ko'chiriladi
    # (yo'li shu yerda); administrator admin paneldan tiklashi mumkin.
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_attachment = models.CharField(max_length=500, blank=True, default="", editable=False)

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


class Meeting(models.Model):
    """Zoom uchrashuvi: tashkilotchi, vaqt va Zoom havolalari."""

    STATUS_SCHEDULED = "scheduled"
    STATUS_CANCELLED = "cancelled"
    STATUS_FINISHED = "finished"
    STATUS_CHOICES = [
        (STATUS_SCHEDULED, "Rejalashtirilgan"),
        (STATUS_CANCELLED, "Bekor qilingan"),
        (STATUS_FINISHED, "Tugatilgan"),
    ]

    organizer = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="meetings_organized", db_index=True)
    title = models.CharField(max_length=200)
    agenda = models.TextField(blank=True, default="")
    start_at = models.DateTimeField(db_index=True)
    duration_minutes = models.PositiveSmallIntegerField(default=30)

    zoom_id = models.CharField(max_length=30, blank=True, default="")
    join_url = models.URLField(max_length=500, blank=True, default="")
    start_url = models.TextField(blank=True, default="")      # faqat tashkilotchiga ko'rsatiladi
    password = models.CharField(max_length=30, blank=True, default="")
    invitation = models.TextField(blank=True, default="")     # Zoom'ning tayyor taklif matni (nusxalash uchun)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_SCHEDULED, db_index=True)
    reminder_sent = models.BooleanField(default=False)
    # Rejadan oldin tugatilgan bo'lsa — haqiqiy tugash vaqti (shundan keyin vaqt bo'shaydi)
    ended_at = models.DateTimeField(null=True, blank=True)
    date_creat = models.DateTimeField(auto_now_add=True)

    @property
    def end_at(self):
        """Band vaqtning tugashi: rejadagi yoki (erta tugatilgan bo'lsa) haqiqiy tugash."""
        from datetime import timedelta
        return self.ended_at or (self.start_at + timedelta(minutes=self.duration_minutes))

    class Meta:
        db_table = "chat_meeting"
        ordering = ["start_at"]
        verbose_name = "Uchrashuv"
        verbose_name_plural = "Zoom"

    def __str__(self):
        return f"{self.title} ({self.start_at:%d.%m.%Y %H:%M})"


class ConversationClear(models.Model):
    """Xodim suhbatni "o'chirgan" (yashirgan) vaqti: shundan oldingi xabarlar unga qayta ko'rinmaydi
    (qarshi tomon yozib suhbat qaytganda ham). Ma'lumot bazada saqlanadi, qarshi tomonga ta'sir qilmaydi."""

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="clears")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="conversation_clears")
    cleared_at = models.DateTimeField()

    class Meta:
        db_table = "chat_conversation_clear"
        constraints = [
            models.UniqueConstraint(fields=["conversation", "employee"], name="uniq_chat_clear_conv_employee"),
        ]
        verbose_name = "Suhbat tozalangan vaqt"
        verbose_name_plural = "Suhbat tozalangan vaqtlar"

    def __str__(self):
        return f"{self.employee_id} / {self.conversation_id} / {self.cleared_at}"


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
