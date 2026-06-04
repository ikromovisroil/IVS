# core/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import AuditLog, SyncLog, SyncEmployeeLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display    = ("date_creat", "employee", "action", "model", "object_id", "method", "ip")
    list_filter     = ("action", "model", "method", "date_creat")
    search_fields   = ("employee__first_name", "employee__last_name", "path", "description")
    readonly_fields = (
        "employee", "action", "model", "object_id",
        "path", "method", "ip", "user_agent", "description", "date_creat"
    )
    ordering = ("-date_creat",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# ---------------------------------------------------------
# SyncEmployeeLog inline — SyncLog ichida
# ---------------------------------------------------------
class SyncEmployeeLogInline(admin.TabularInline):
    model           = SyncEmployeeLog
    extra           = 0
    can_delete      = False
    readonly_fields = ("pinfl", "full_name", "result_badge", "changes", "error_msg")
    fields          = ("pinfl", "full_name", "result_badge", "changes", "error_msg")
    ordering        = ("-date_creat",)

    def result_badge(self, obj):
        colors = {
            "updated": "#28a745",
            "blocked": "#dc3545",
            "error":   "#ffc107",
        }
        color = colors.get(obj.result, "#6c757d")
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;'
            'border-radius:8px;font-size:12px;">{}</span>',
            color, obj.get_result_display()
        )
    result_badge.short_description = "Natija"

    def has_add_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------
# SyncLog
# ---------------------------------------------------------
@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display    = (
        "date_creat", "status_badge",
        "total", "updated_col", "blocked_col",
        "skipped", "errors_col", "duration_display"
    )
    list_filter     = ("status", "date_creat")
    readonly_fields = (
        "date_creat", "total", "updated", "blocked",
        "skipped", "errors", "duration", "status"
    )
    ordering        = ("-date_creat",)
    inlines         = [SyncEmployeeLogInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def status_badge(self, obj):
        colors = {
            "success": "#28a745",
            "partial": "#ffc107",
            "failed":  "#dc3545",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background:{};color:white;padding:3px 10px;'
            'border-radius:10px;font-size:12px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = "Holat"

    def updated_col(self, obj):
        return format_html(
            '<span style="color:#28a745;font-weight:bold">{}</span>', obj.updated
        )
    updated_col.short_description = "Yangilandi"

    def blocked_col(self, obj):
        color = "#dc3545" if obj.blocked > 0 else "#6c757d"
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>', color, obj.blocked
        )
    blocked_col.short_description = "Bloklandi"

    def errors_col(self, obj):
        color = "#dc3545" if obj.errors > 0 else "#6c757d"
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>', color, obj.errors
        )
    errors_col.short_description = "Xato"

    def duration_display(self, obj):
        m, s = divmod(obj.duration, 60)
        return f"{m}m {s}s" if m else f"{s}s"
    duration_display.short_description = "Vaqt"


# ---------------------------------------------------------
# SyncEmployeeLog — alohida sahifa
# ---------------------------------------------------------
@admin.register(SyncEmployeeLog)
class SyncEmployeeLogAdmin(admin.ModelAdmin):
    list_display    = ("date_creat", "full_name", "pinfl", "result_badge", "changes_short")
    list_filter     = ("result", "date_creat")
    search_fields   = ("full_name", "pinfl")
    readonly_fields = (
        "sync", "employee", "pinfl", "full_name",
        "result", "changes", "error_msg", "date_creat"
    )
    ordering        = ("-date_creat",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def result_badge(self, obj):
        colors = {
            "updated": "#28a745",
            "blocked": "#dc3545",
            "error":   "#ffc107",
        }
        color = colors.get(obj.result, "#6c757d")
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;'
            'border-radius:8px;font-size:12px;">{}</span>',
            color, obj.get_result_display()
        )
    result_badge.short_description = "Natija"

    def changes_short(self, obj):
        text = obj.changes or obj.error_msg or "—"
        return text[:80] + "..." if len(text) > 80 else text
    changes_short.short_description = "Tafsilot"