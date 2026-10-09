from django.contrib import admin

from django.contrib import messages as dj_messages

from main.admin import NoDeleteAdminMixin

from .models import Conversation, ConversationClear, Meeting, Message, OnlineStatus
from .services import restore_message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("sender", "is_ai", "body", "date_creat", "read_at")
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "participant_1", "participant_2", "date_edit")
    list_filter = ("kind",)
    search_fields = (
        "participant_1__last_name", "participant_1__first_name",
        "participant_2__last_name", "participant_2__first_name",
    )
    autocomplete_fields = ("participant_1", "participant_2")
    ordering = ("-date_edit", "-id")
    inlines = [MessageInline]


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
