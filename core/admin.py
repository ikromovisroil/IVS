# core/admin.py
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import *

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
# Xodimni tahrirlash havolasi — inline va alohida sahifada
# birgalikda ishlatiladi, shu sabab alohida funksiya qilib
# chiqarib qo'ydik (kod takrorlanmasin).
# ---------------------------------------------------------
def _employee_edit_link(obj):
    if not obj.employee_id:
        return "—"
    url = reverse("admin:main_employee_change", args=[obj.employee_id])
    return format_html(
        '<a class="button" href="{}" target="_blank">✏️ Tahrirlash</a>', url
    )


# ---------------------------------------------------------
# SyncEmployeeLog inline — SyncLog ichida
# ---------------------------------------------------------
class SyncEmployeeLogInline(admin.TabularInline):
    model           = SyncEmployeeLog
    extra           = 0
    can_delete      = False
    readonly_fields = ("pinfl", "full_name", "result_badge", "changes", "error_msg", "edit_link")
    fields          = ("pinfl", "full_name", "result_badge", "changes", "error_msg", "edit_link")
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

    def edit_link(self, obj):
        return _employee_edit_link(obj)
    edit_link.short_description = "Xodimni tahrirlash"

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
    list_display    = (
        "date_creat", "full_name", "pinfl", "result_badge",
        "changes_short", "edit_employee_link"
    )
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
            '<span style="background-color:{}; color:#fff; padding:3px 10px; '
            'border-radius:10px; font-weight:bold; font-size:12px;">{}</span>',
            color, obj.get_result_display()
        )
    result_badge.short_description = "Natija"

    def changes_short(self, obj):
        text = obj.changes or obj.error_msg or "—"
        return text[:80] + "..." if len(text) > 80 else text
    changes_short.short_description = "Tafsilot"

    def edit_employee_link(self, obj):
        return _employee_edit_link(obj)
    edit_employee_link.short_description = "Xodimni tahrirlash"



@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "employee", "short_endpoint", "user_agent", "date_creat")
    list_filter = ("date_creat",)
    search_fields = (
        "employee__last_name",
        "employee__first_name",
        "employee__father_name",
        "endpoint",
    )
    autocomplete_fields = ("employee",)
    readonly_fields = ("endpoint", "p256dh", "auth", "user_agent", "date_creat")
    ordering = ("-date_creat",)

    def short_endpoint(self, obj):
        return obj.endpoint[:60] + "..." if len(obj.endpoint) > 60 else obj.endpoint
    short_endpoint.short_description = "Endpoint"