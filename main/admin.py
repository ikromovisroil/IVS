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
    list_display = ("id", "inn", "name", "contract")
    search_fields = ("inn", "name", "contract")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "region", "name", "organization")
    list_filter = ("organization", "region")
    search_fields = ("name", "organization__name")


@admin.register(Directorate)
class DirectorateAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "department")
    list_filter = ("department", "department__organization")
    search_fields = ("name", "department__name", "department__organization__name")


@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "directorate")
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
        "directorate", "division", "rank", "region", "pinfl"
    )
    list_filter = (
        "organization", "department", "directorate", "division",
        "rank", "region"
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
        "id", "employee", "full", "client",
        "confirm", "order", "boss", "shop", "akt", "status",
        "technics", "technics_edit", "material", "material_edit"
    )
    list_filter = (
        "full", "confirm", "client", "order", "boss", "shop", "akt", "status",
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
        "name", "inventory", "serial", "is_active"
    )
    list_filter = (
        "group", "category", "organization", "department",
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
        "inventory", "serial", "price", "year", "is_active"
    )
    list_filter = ("organization", "category", "status", "is_active")
    search_fields = (
        "name", "inventory", "serial"
    )
    autocomplete_fields = ("category", "organization", "technics")


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = (
        "id", "employee", "name", "unit",
        "status", "number", "code", "price", "year", "is_active"
    )
    list_filter = ("organization", "employee", "status", "unit", "is_active")
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
        "status", "rating", "date_creat"
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
        "status_sender", "status_receiver", "file_type",
        "date_creat"
    )
    list_filter = (
        "status_sender", "status_receiver",
        "file_type", "date_creat"
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