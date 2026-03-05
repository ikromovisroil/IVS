from django.contrib import admin
from django.utils.html import format_html

from .models import *
# ----------------------------
# Base helpers
# ----------------------------
class ReadonlyDatesAdmin(admin.ModelAdmin):
    readonly_fields = ("date_creat", "date_edit")
    list_per_page = 50

# ----------------------------
# Organization tree models
# ----------------------------
@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {}  # AutoSlugMixin save() ishlaydi
    ordering = ("name",)
    exclude = ("slug",)



@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "organization", "slug")
    list_filter = ("organization",)
    search_fields = ("name", "slug", "organization__name")
    autocomplete_fields = ("organization",)
    ordering = ("name",)
    exclude = ("slug",)


@admin.register(Directorate)
class DirectorateAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "department", "get_organization", "slug")
    list_filter = ("department__organization", "department")
    search_fields = ("name", "slug", "department__name", "department__organization__name")
    autocomplete_fields = ("department",)
    ordering = ("name",)
    exclude = ("slug",)

    @admin.display(description="Tashkilot", ordering="department__organization__name")
    def get_organization(self, obj):
        return obj.department.organization if obj.department else None


@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "directorate", "get_department", "get_organization", "slug")
    list_filter = ("directorate__department__organization", "directorate__department", "directorate")
    search_fields = (
        "name", "slug",
        "directorate__name",
        "directorate__department__name",
        "directorate__department__organization__name",
    )
    autocomplete_fields = ("directorate",)
    ordering = ("name",)
    exclude = ("slug",)

    @admin.display(description="Departament", ordering="directorate__department__name")
    def get_department(self, obj):
        return obj.directorate.department if obj.directorate else None

    @admin.display(description="Tashkilot", ordering="directorate__department__organization__name")
    def get_organization(self, obj):
        if obj.directorate and obj.directorate.department:
            return obj.directorate.department.organization
        return None


# ----------------------------
# Simple reference models
# ----------------------------
@admin.register(Rank)
class RankAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug")
    search_fields = ("name", "slug")
    ordering = ("name",)
    exclude = ("slug",)


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)
    ordering = ("name",)


# ----------------------------
# Employee / Role
# ----------------------------
class RolInline(admin.StackedInline):
    model = Rol
    extra = 0
    can_delete = False
    fk_name = "employee"


@admin.register(Employee)
class EmployeeAdmin(ReadonlyDatesAdmin):
    list_display = (
        "id",
        "full_name_admin",
        "user",
        "pinfl",
        "phone",
        "organization",
        "department",
        "directorate",
        "division",
        "rank",
        "region",
    )
    list_filter = ("organization", "department", "directorate", "division", "rank", "region")
    search_fields = (
        "last_name", "first_name", "father_name",
        "pinfl", "phone",
        "user__username",
        "organization__name", "department__name", "directorate__name", "division__name",
    )
    autocomplete_fields = (
        "user",
        "organization", "department", "directorate", "division",
        "rank", "region",
    )
    inlines = (RolInline,)



    @admin.display(description="F.I.Sh")
    def full_name_admin(self, obj):
        return obj.full_name


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = (
        "id", "employee",
        "client", "order",
        "boss", "shop", "akt",
        "technics", "technics_edit",
        "material", "material_edit",
    )
    list_filter = (
        "client", "boss", "shop", "akt",
        "technics", "technics_edit",
        "material", "material_edit",
    )
    search_fields = ("employee__last_name", "employee__first_name", "employee__father_name", "employee__user__username")
    autocomplete_fields = ("employee",)


# ----------------------------
# Technics / Material
# ----------------------------
@admin.register(Technics)
class TechnicsAdmin(ReadonlyDatesAdmin):
    list_display = (
        "id", "name", "category", "status",
        "inventory", "serial", "mac", "ip",
        "employee",
        "organization", "department",
        "price", "year",
        "date_creat",
    )
    list_filter = ("status", "category", "organization", "department", "year")
    search_fields = (
        "name", "parametr", "inventory", "serial", "mac", "ip",
        "employee__last_name", "employee__first_name",
        "organization__name", "department__name",
        "category__name",
    )
    autocomplete_fields = ("category", "organization", "department", "employee")



@admin.register(ExtraTechnics)
class ExtraTechnicsAdmin(ReadonlyDatesAdmin):
    list_display = ("id", "organization", "name", "technics", "status", "inventory", "serial", "price", "year", "date_creat")
    list_filter = ("status", "year")
    search_fields = ("name", "inventory", "serial", "technics__name")
    autocomplete_fields = ("technics",)


@admin.register(Material)
class MaterialAdmin(ReadonlyDatesAdmin):
    list_display = ("id", "name", "status", "number", "unit", "code", "employee", "price", "year", "date_creat")
    list_filter = ("status", "unit", "year")
    search_fields = ("name", "code", "employee__last_name", "employee__first_name")
    autocomplete_fields = ("employee", "unit")


# ----------------------------
# Order + OrderMaterial inline
# ----------------------------
class OrderMaterialInline(admin.TabularInline):
    model = OrderMaterial
    extra = 0
    autocomplete_fields = ("material",)
    fields = ("material", "number")
    show_change_link = True


@admin.register(Order)
class OrderAdmin(ReadonlyDatesAdmin):
    list_display = (
        "id",
        "short_body",
        "sender",
        "receiver",
        "technics",
        "goal",
        "status",
        "receiver_seen",
        "date_creat",
    )
    list_filter = ("status", "receiver_seen", "goal", "date_creat")
    search_fields = (
        "body",
        "sender__last_name", "sender__first_name",
        "receiver__last_name", "receiver__first_name",
        "technics__name", "technics__serial", "technics__inventory",
        "goal__name",
    )
    autocomplete_fields = ("sender", "receiver", "technics", "goal")
    inlines = (OrderMaterialInline,)

    readonly_fields = ReadonlyDatesAdmin.readonly_fields + (
        "date_accepted", "date_finished", "date_approved", "date_rejected",
    )


    @admin.display(description="Izoh")
    def short_body(self, obj):
        if not obj.body:
            return ""
        return (obj.body[:60] + "…") if len(obj.body) > 60 else obj.body


@admin.register(OrderMaterial)
class OrderMaterialAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "material", "number")
    list_filter = ("material",)
    search_fields = ("order__body", "material__name")
    autocomplete_fields = ("order", "material")


# ----------------------------
# Deed + DeedConsent inline
# ----------------------------
class DeedConsentInline(admin.TabularInline):
    model = DeedConsent
    extra = 0
    autocomplete_fields = ("employee",)
    fields = ("employee", "status", "message", "date_creat")
    readonly_fields = ("date_creat",)
    show_change_link = True


@admin.register(Deed)
class DeedAdmin(ReadonlyDatesAdmin):
    list_display = (
        "id",
        "sender",
        "receiver",
        "user",
        "status_sender",
        "status_receiver",
        "sender_seen",
        "receiver_seen",
        "file_link",
        "date_creat",
    )
    list_filter = ("status_sender", "status_receiver", "sender_seen", "receiver_seen", "date_creat")
    search_fields = (
        "message_sender", "message_receiver", "message_user",
        "sender__last_name", "sender__first_name",
        "receiver__last_name", "receiver__first_name",
        "user__last_name", "user__first_name",
        "file",
    )
    autocomplete_fields = ("sender", "receiver", "user")
    inlines = (DeedConsentInline,)


    @admin.display(description="Fayl")
    def file_link(self, obj):
        if not obj.file:
            return "-"
        return format_html('<a href="{}" target="_blank">ochish</a>', obj.file.url)


@admin.register(DeedConsent)
class DeedConsentAdmin(ReadonlyDatesAdmin):
    list_display = ("id", "deed", "employee", "status", "date_creat")
    list_filter = ("status", "date_creat")
    search_fields = ("message", "employee__last_name", "employee__first_name", "deed__id")
    autocomplete_fields = ("deed", "employee")
