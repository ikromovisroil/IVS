from django.contrib import admin
from .models import *

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
    list_display = ("id", "name", "contract")
    search_fields = ("name", "contract")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "organization")
    list_filter = ("organization",)
    search_fields = ("name", "organization__name")


@admin.register(Directorate)
class DirectorateAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "department")
    list_filter = ("department", "department__organization")
    search_fields = ("name", "department__name", "department__organization__name")


@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "directorate")
    list_filter = ("directorate", "directorate__department")
    search_fields = ("name", "directorate__name")


@admin.register(Rank)
class RankAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


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


@admin.register(MaterialCategory)
class MaterialCategoryAdmin(admin.ModelAdmin):
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
        "directorate", "division", "rank", "region", "phone", "pinfl",
        "date_creat"
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

    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = "F.I.SH"


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = (
        "id", "employee", "full",
        "confirm", "order", "boss", "shop", "akt", "status",
        "technics", "technics_edit", "material", "material_edit"
    )
    list_filter = (
        "full", "confirm", "order", "boss", "shop", "akt", "status",
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
        "id", "name", "group", "category", "employee", "organization",
        "status", "inventory", "serial", "ip", "price", "year", "is_active"
    )
    list_filter = (
        "group", "category", "organization", "department",
        "directorate", "division", "status", "is_active", "year"
    )
    search_fields = (
        "name", "parametr", "inventory", "serial", "mac", "ip",
        "employee__last_name", "employee__first_name",
        "organization__name", "category__name"
    )
    autocomplete_fields = (
        "group", "category", "organization", "department",
        "directorate", "division", "employee"
    )
    readonly_fields = ("qr_code", "date_creat", "date_edit")


@admin.register(Structure)
class StructureAdmin(admin.ModelAdmin):
    list_display = (
        "id", "name", "category", "organization", "technics",
        "status", "inventory", "serial", "price", "year", "is_active"
    )
    list_filter = ("category", "organization", "status", "is_active", "year")
    search_fields = (
        "name", "parametr", "inventory", "serial",
        "organization__name", "category__name", "technics__name"
    )
    autocomplete_fields = ("category", "organization", "technics")


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = (
        "id", "name", "employee", "category", "unit",
        "status", "number", "code", "price", "year", "is_active"
    )
    list_filter = ("category", "unit", "status", "is_active", "year")
    search_fields = (
        "name", "code",
        "employee__last_name", "employee__first_name",
        "category__name", "unit__name"
    )
    autocomplete_fields = ("employee", "category", "unit")


@admin.register(MaterialUser)
class MaterialUserAdmin(admin.ModelAdmin):
    list_display = ("id", "sender", "receiver")


# =========================
# Order
# =========================

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id", "sender", "receiver", "goal", "technics",
        "status", "rating", "receiver_seen",
        "date_creat", "date_accepted", "date_finished",
        "date_approved", "date_rejected"
    )
    list_filter = (
        "status", "receiver_seen", "goal",
        "date_creat", "date_accepted", "date_finished",
        "date_approved", "date_rejected"
    )
    search_fields = (
        "sender__last_name", "sender__first_name",
        "receiver__last_name", "receiver__first_name",
        "technics__name"
    )
    autocomplete_fields = ("sender", "receiver", "goal", "technics")
    inlines = [OrderMaterialInline]
    readonly_fields = (
        "date_creat", "date_edit", "date_accepted",
        "date_finished", "date_approved", "date_rejected"
    )


@admin.register(OrderMaterial)
class OrderMaterialAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "material", "number")
    list_filter = ("material__category",)
    search_fields = ("order__body", "material__name", "material__code")
    autocomplete_fields = ("order", "material")


# =========================
# Deed
# =========================

@admin.register(Deed)
class DeedAdmin(admin.ModelAdmin):
    list_display = (
        "id", "code", "sender", "receiver", "user",
        "status_sender", "status_receiver", "file_type",
        "sender_seen", "receiver_seen", "date_creat"
    )
    list_filter = (
        "status_sender", "status_receiver",
        "file_type", "sender_seen", "receiver_seen", "date_creat"
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


@admin.register(DeedConsent)
class DeedConsentAdmin(admin.ModelAdmin):
    list_display = ("id", "deed", "employee", "status", "date_creat")
    list_filter = ("status", "date_creat")
    search_fields = (
        "deed__code", "message",
        "employee__last_name", "employee__first_name"
    )
    autocomplete_fields = ("deed", "employee")


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