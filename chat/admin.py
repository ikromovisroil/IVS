from django.contrib import admin

from django.contrib import messages as dj_messages
from django.urls import reverse
from django.utils.html import format_html

from main.admin import NoDeleteAdminMixin

from .models import Conversation, ConversationClear, Meeting, Message, OnlineStatus
from .services import restore_message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "participant_1", "participant_2", "date_edit")
    list_filter = ("kind",)
    search_fields = (
        "participant_1__last_name", "participant_1__first_name",
        "participant_2__last_name", "participant_2__first_name",
    )
    autocomplete_fields = ("participant_1", "participant_2", "participants", "admins", "hidden_for")
    ordering = ("-date_edit", "-id")
    readonly_fields = ("messages_link",)

    # Suhbatdagi hamma xabarni inline qilib chizish minglab qatorda sahifani qotirardi: filtrlangan ro'yxatga havola
    @admin.display(description="Xabarlar")
    def messages_link(self, obj):
        if not obj.pk:
            return "—"
        url = reverse("admin:chat_message_changelist") + f"?conversation__id__exact={obj.pk}"
        return format_html('<a href="{}">{} ta xabar — ro‘yxatni ochish</a>', url, obj.messages.count())


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "is_ai", "is_edited", "is_deleted", "date_creat")
    list_filter = ("is_ai", "is_deleted")
    search_fields = ("body",)
    autocomplete_fields = ("conversation", "sender")
    ordering = ("-date_creat", "-id")
    readonly_fields = ("deleted_attachment",)
    actions = ["restore_deleted"]

    @admin.action(description="O'chirilgan xabarlarni tiklash (matn va fayl bilan)")
    def restore_deleted(self, request, queryset):
        count = 0
        for msg in queryset.filter(is_deleted=True):
            restore_message(msg)
            count += 1
        self.message_user(request, f"Tiklandi: {count} ta xabar", dj_messages.SUCCESS)


@admin.register(ConversationClear)
class ConversationClearAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "employee", "cleared_at")
    autocomplete_fields = ("conversation", "employee")


@admin.register(OnlineStatus)
class OnlineStatusAdmin(admin.ModelAdmin):
    list_display = ("id", "employee", "last_seen")
    search_fields = ("employee__last_name", "employee__first_name")
    autocomplete_fields = ("employee",)


@admin.register(Meeting)
class MeetingAdmin(NoDeleteAdminMixin, admin.ModelAdmin):
    """
    Zoom uchrashuvlari: faqat ko'rish. Yaratish/bekor qilish/tugatish sayt orqali (Zoom bilan bog'liq),
    admin panelda o'zgartirsak Zoom'dagi uchrashuv bilan nomuvofiqlik bo'lib qoladi.
    """
    list_display = ("id", "title", "organizer", "start_at", "end_at", "duration_minutes", "status")
    list_filter = ("status",)
    search_fields = ("title", "organizer__last_name", "organizer__first_name", "zoom_id")
    ordering = ("-start_at",)
    date_hierarchy = "start_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Tugash vaqti")
    def end_at(self, obj):
        return obj.end_at
