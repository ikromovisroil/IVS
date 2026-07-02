from django.contrib import admin
from .models import *
from django.utils.html import format_html
# =========================
# Inlines
# =========================

class RolInline(admin.StackedInline):
    model = Rol
    extra = 0
    can_delete = False


class OrderMaterialInline(admin.TabularInline):
    model = OrderMaterial
    extra = 1


class DeedConsentInline(admin.TabularInline):
    model = DeedConsent
    extra = 1


# =========================
# Simple models
# =========================

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("id", "inn", "name", "contract")
    search_fields = ("inn", "name", "contract")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "inn", "region", "name", "organization")
    list_filter = ("organization", "region")
    search_fields = ("name", "code", "inn", "organization__name")


@admin.register(Directorate)
class DirectorateAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "department")
    list_filter = ("department", "department__organization")
    search_fields = ("name", "code", "department__name", "department__organization__name")


@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "directorate")
    list_filter = ("directorate", "directorate__department")
    search_fields = ("name", "code", "directorate__name")


@admin.register(Rank)
class RankAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name")
    search_fields = ("name", "code",)


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "group")
    list_filter = ("group",)
    search_fields = ("name", "group__name")


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(StructureCategory)
class StructureCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "unit", "price")
    search_fields = ("name", "unit")
    list_filter = ("unit",)


# =========================
# Employee / Role
# =========================

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "id", "full_name", "user", "organization", "department",
        "directorate", "division", "rank", "region", "pinfl", "date_creat"
    )
    list_filter = (
        "organization", "department", "directorate", "division",
        "rank", "region", "date_creat"
    )
    search_fields = (
        "last_name", "first_name", "father_name",
        "user__username", "phone", "pinfl"
    )
    autocomplete_fields = (
        "user", "organization", "department", "directorate",
        "division", "rank", "region"
    )
    inlines = [RolInline]


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = (
        "id", "employee", "full", "region", "client", "confirm",
        "order", "order_edit", "boss", "shop", "akt", "status", "document",
        "technics", "technics_edit", "material", "material_edit"
    )
    list_filter = (
        "full", "region", "client", "confirm",
        "order", "order_edit", "boss", "shop", "akt", "status", "document",
        "technics", "technics_edit", "material", "material_edit"
    )
    search_fields = (
        "employee__last_name",
        "employee__first_name",
        "employee__father_name",
        "employee__user__username",
    )
    autocomplete_fields = ("employee",)


# =========================
# Technics / Structure / Material
# =========================

@admin.register(Technics)
class TechnicsAdmin(admin.ModelAdmin):
    list_display = (
        "id", "group", "category", "employee", "status",
        "name", "inventory", "serial", "is_active", "date_creat"
    )
    list_filter = (
        "group", "category", "organization", "region", "department",
        "directorate", "division", "status", "is_active"
    )
    search_fields = (
        "name", "inventory", "serial", "mac", "ip", 'year',
        "employee__last_name", "employee__first_name"
    )
    autocomplete_fields = (
        "group", "category", "organization", "department",
        "directorate", "division", "employee"
    )
    readonly_fields = ("qr_code", "date_creat", "date_edit")


@admin.register(Structure)
class StructureAdmin(admin.ModelAdmin):
    list_display = (
        "id", "technics", "category", "name", "status",
        "inventory", "serial", "price", "year", "is_active", "date_creat"
    )
    list_filter = ("organization", "region", "category", "status", "is_active")
    search_fields = (
        "name", "inventory", "serial"
    )
    autocomplete_fields = ("category", "organization", "technics")


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = (
        "id", "employee", "name", "unit",
        "number", "code", "price", "year", "is_active", "date_creat", "date_edit"
    )
    list_filter = ("organization", "employee", "unit", "is_active", "date_creat")
    search_fields = (
        "name", "code",
        "employee__last_name", "employee__first_name"
    )
    autocomplete_fields = ("employee", "unit")


@admin.register(MaterialUser)
class MaterialUserAdmin(admin.ModelAdmin):
    list_display = ("id", "sender", "receiver")


# =========================
# Order
# =========================

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id", "sender", "receiver", "user",
        "colored_status", "rating", "date_creat"
    )
    list_filter = (
        "status", "goal", "date_creat"
    )
    search_fields = (
        "id",
        "user__last_name", "user__first_name",
        "sender__last_name", "sender__first_name",
        "receiver__last_name", "receiver__first_name"
    )
    autocomplete_fields = ("sender", "receiver", "user")
    inlines = [OrderMaterialInline]
    readonly_fields = (
        "date_creat", "date_edit", "date_process", "date_finished",
        "date_approved", "date_accepted", "date_canceled", "date_rejected"
    )

    STATUS_COLORS = {
        "viewed": "#ffc107",     # sariq — yangi
        "process": "#e67e22",    # to'q sariq — jarayonda
        "finished": "#3498db",   # moviy-yashil — tayyorlandi
        "approved": "#2ecc71",   # yashil — tasdiqlandi
        "accepted": "#28a745",   # to'q yashil — qabul qilindi (yakuniy)
        "canceled": "#6c757d",   # kulrang — bekor qilindi
        "rejected": "#dc3545",   # qizil — rad etildi
    }

    def colored_status(self, obj):
        color = self.STATUS_COLORS.get(obj.status, "#999")
        label = obj.get_status_display()
        return format_html(
            '<span style="background-color:{}; color:#fff; padding:3px 10px; '
            'border-radius:10px; font-weight:bold; font-size:12px;">{}</span>',
            color, label
        )
    colored_status.short_description = "Holati"
    colored_status.admin_order_field = "status"


@admin.register(OrderMaterial)
class OrderMaterialAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "user", "material", "number", "given")
    search_fields = (
        "order__id", "user__first_name",
        "user__last_name", "user__father_name"
    )
    autocomplete_fields = ("order", "material")


# =========================
# Deed
# =========================

@admin.register(Deed)
class DeedAdmin(admin.ModelAdmin):
    list_display = (
        "id", "code", "sender", "receiver", "user",
        "colored_status_sender", "colored_status_receiver", "status",
        "date_creat"
    )
    list_filter = (
        "status_sender", "status_receiver", "status", "date_creat"
    )
    search_fields = (
        "code", "body", "message_sender", "message_receiver", "message_user",
        "sender__last_name", "sender__first_name",
        "receiver__last_name", "receiver__first_name",
        "user__last_name", "user__first_name"
    )
    autocomplete_fields = ("sender", "receiver", "user")
    readonly_fields = ("code", "date_creat", "date_edit")
    inlines = [DeedConsentInline]

    STATUS_COLORS = {
        "viewed": "#ffc107",     # sariq
        "approved": "#28a745",   # yashil
        "rejected": "#dc3545",   # qizil
    }

    def _status_badge(self, status):
        color = self.STATUS_COLORS.get(status, "#999")
        label = dict(Deed._meta.get_field("status_sender").choices).get(status, status)
        return format_html(
            '<span style="background-color:{}; color:#fff; padding:3px 10px; '
            'border-radius:10px; font-weight:bold; font-size:12px;">{}</span>',
            color, label
        )

    def colored_status_sender(self, obj):
        return self._status_badge(obj.status_sender)
    colored_status_sender.short_description = "status sender"
    colored_status_sender.admin_order_field = "status_sender"

    def colored_status_receiver(self, obj):
        return self._status_badge(obj.status_receiver)
    colored_status_receiver.short_description = "status receiver"
    colored_status_receiver.admin_order_field = "status_receiver"


@admin.register(DeedConsent)
class DeedConsentAdmin(admin.ModelAdmin):
    list_display = ("id", "deed", "employee", "colored_status", "date_creat")
    list_filter = ("status", "date_creat")
    search_fields = (
        "deed__code", "message",
        "employee__last_name", "employee__first_name"
    )
    autocomplete_fields = ("deed", "employee")

    STATUS_COLORS = {
        "viewed": "#ffc107",  # sariq
        "approved": "#28a745",  # yashil
        "rejected": "#dc3545",  # qizil
    }

    def colored_status(self, obj):
        color = self.STATUS_COLORS.get(obj.status, "#999")
        label = obj.get_status_display()
        return format_html(
            '<span style="background-color:{}; color:#fff; padding:3px 10px; '
            'border-radius:10px; font-weight:bold; font-size:12px;">{}</span>',
            color, label
        )

    colored_status.short_description = "Holati"
    colored_status.admin_order_field = "status"


# =========================
# Liable
# =========================

@admin.register(Liable)
class LiableAdmin(admin.ModelAdmin):
    list_display = ("id", "employee", "contract", "category")
    list_filter = ("category", "contract")
    search_fields = (
        "employee__last_name", "employee__first_name",
        "contract__name", "category__name"
    )
    autocomplete_fields = ("employee", "contract", "category")


@admin.register(MaterialMovement)
class MaterialMovementAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'status',
        'material',
        'user',
        'employee',
        'balance',
        'income',
        'outcome',
        'date_creat',
    ]
    list_filter = ['status', 'date_creat']
    search_fields = [
        'material__name',
        'user__last_name',
        'user__first_name',
        'employee__last_name',
        'employee__first_name',
    ]