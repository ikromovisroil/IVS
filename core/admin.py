from django.contrib import admin
from .models import *
# Register your models here.



@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("employee", "model", "action", "date_creat")
    list_filter = ("action", "model", "method", "date_creat")
    search_fields = ("employee__first_name", "employee__last_name")

