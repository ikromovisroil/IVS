from django.contrib import admin

from .models import Conversation, Message, OnlineStatus


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
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "is_ai", "is_edited", "is_deleted", "date_creat")
    list_filter = ("is_ai", "is_deleted")
    search_fields = ("body",)
    autocomplete_fields = ("conversation", "sender")


@admin.register(OnlineStatus)
class OnlineStatusAdmin(admin.ModelAdmin):
    list_display = ("id", "employee", "last_seen")
    search_fields = ("employee__last_name", "employee__first_name")
    autocomplete_fields = ("employee",)
