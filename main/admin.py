from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import *


# =========================
# SIMPLE MODELS
# =========================
@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "contract")
    search_fields = ("name", "contract")
    ordering = ("name",)
    exclude = ("slug",)

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "organization")
    list_filter = ("organization",)
    search_fields = ("name", "organization__name")
    autocomplete_fields = ("organization",)
    ordering = ("name",)
    exclude = ("slug",)


@admin.register(Directorate)
class DirectorateAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "department")
    list_filter = ("department", "department__organization")
    search_fields = ("name", "department__name", "department__organization__name")
    autocomplete_fields = ("department",)
    ordering = ("name",)
    exclude = ("slug",)


@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "directorate")
    list_filter = (
        "directorate",
        "directorate__department",
        "directorate__department__organization",
    )
    search_fields = (
        "name",
        "directorate__name",
        "directorate__department__name",
        "directorate__department__organization__name",
    )
    autocomplete_fields = ("directorate",)
    ordering = ("name",)
    exclude = ("slug",)


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
    list_display = ("id", "name")
    search_fields = ("name",)
    ordering = ("name",)
    exclude = ("slug",)


@admin.register(ExtraCategory)
class ExtraCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)
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


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "unit", "price")
    search_fields = ("name", "unit")
    list_filter = ("unit",)
    ordering = ("name",)


# =========================
# INLINEs
# =========================
class RolInline(admin.StackedInline):
    model = Rol
    fk_name = "employee"
    extra = 0


class ExtraTechnicsInline(admin.TabularInline):
    model = ExtraTechnics
    extra = 0
    autocomplete_fields = ("organization",)
    fields = (
        "name", "organization", "status", "parametr",
        "inventory", "serial", "price", "year", "is_active"
    )


class OrderMaterialInline(admin.TabularInline):
    model = OrderMaterial
    extra = 1
    autocomplete_fields = ("material",)


class DeedConsentInline(admin.TabularInline):
    model = DeedConsent
    extra = 1
    autocomplete_fields = ("employee",)


# =========================
# EMPLOYEE / ROLE
# =========================
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "id", "full_name", "user", "organization", "department",
        "directorate", "division", "rank", "region", "phone", "pinfl",
        "date_creat",
    )
    list_filter = (
        "organization", "department", "directorate", "division",
        "rank", "region", "date_creat",
    )
    search_fields = (
        "last_name", "first_name", "father_name",
        "user__username", "pinfl", "phone",
        "organization__name", "department__name",
        "directorate__name", "division__name",
    )
    autocomplete_fields = (
        "user", "organization", "department",
        "directorate", "division", "rank", "region",
    )
    readonly_fields = ("date_creat", "date_edit")
    inlines = (RolInline,)
    ordering = ("last_name", "first_name", "father_name")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "user", "organization", "department",
            "directorate", "division", "rank", "region"
        )

    @admin.display(description="F.I.Sh")
    def full_name(self, obj):
        return obj.full_name


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = (
        "id", "employee",
        "client", "order", "boss", "shop",
        "akt", "status", "technics", "technics_edit",
        "material", "material_edit",
    )
    list_filter = (
        "client", "order", "boss", "shop",
        "akt", "status", "technics", "technics_edit",
        "material", "material_edit",
    )
    search_fields = (
        "employee__last_name", "employee__first_name",
        "employee__father_name", "employee__user__username",
    )
    autocomplete_fields = ("employee",)


# =========================
# TECHNICS
# =========================
@admin.register(Technics)
class TechnicsAdmin(admin.ModelAdmin):
    list_display = (
        "id", "name", "category", "employee", "organization",
        "department", "directorate", "division",
        "status", "inventory", "serial", "mac", "is_active", "date_creat",
    )
    list_filter = (
        "status", "is_active", "category",
        "organization", "department", "directorate", "division",
        "date_creat",
    )
    search_fields = (
        "name", "parametr", "inventory", "serial", "mac", "ip", "year",
        "employee__last_name", "employee__first_name", "employee__father_name",
        "category__name",
        "organization__name", "department__name",
        "directorate__name", "division__name",
    )
    autocomplete_fields = (
        "category", "organization", "department",
        "directorate", "division", "employee",
    )
    readonly_fields = ("date_creat", "date_edit")
    inlines = (ExtraTechnicsInline,)
    ordering = ("name",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "category", "organization", "department",
            "directorate", "division", "employee"
        )


@admin.register(ExtraTechnics)
class ExtraTechnicsAdmin(admin.ModelAdmin):
    list_display = (
        "id", "name", "category", "technics", "organization", "status",
        "inventory", "serial", "price",
        "is_active", "date_creat",
    )
    list_filter = (
        "category", "status", "is_active", "organization", "date_creat",
    )
    search_fields = (
        "name", "parametr", "inventory", "serial", "year",
        "category__name", "technics__name", "organization__name",
    )
    autocomplete_fields = ("category", "organization", "technics")
    readonly_fields = ("date_creat", "date_edit")
    ordering = ("name",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "organization", "technics"
        )


# =========================
# MATERIAL
# =========================
@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = (
        "id", "name", "employee", "unit", "status",
        "number", "code", "price",
        "is_active", "date_creat",
    )
    list_filter = (
        "status", "is_active", "unit", "date_creat"
    )
    search_fields = (
        "name", "code", "year",
        "employee__last_name", "employee__first_name", "employee__father_name",
    )
    autocomplete_fields = ("employee", "unit")
    ordering = ("name",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("employee", "unit")


# =========================
# ORDER
# =========================
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id", "sender", "receiver", "goal", "technics",
        "status", "receiver_seen", "rating",
        "date_creat", "date_accepted", "date_finished",
        "date_approved", "date_rejected",
    )
    list_filter = (
        "status", "receiver_seen", "goal",
        "date_creat", "date_edit",
        "date_accepted", "date_finished",
        "date_approved", "date_rejected",
    )
    search_fields = (
        "body",
        "sender__last_name", "sender__first_name", "sender__father_name",
        "receiver__last_name", "receiver__first_name", "receiver__father_name",
        "goal__name",
        "technics__name",
    )
    autocomplete_fields = ("sender", "receiver", "goal", "technics")
    readonly_fields = (
        "date_creat", "date_edit",
        "date_accepted", "date_finished",
        "date_approved", "date_rejected",
    )
    inlines = (OrderMaterialInline,)
    date_hierarchy = "date_creat"
    ordering = ("-id",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "sender", "receiver", "goal", "technics"
        )


@admin.register(OrderMaterial)
class OrderMaterialAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "material", "number")
    list_filter = ("material",)
    search_fields = (
        "order__body",
        "material__name",
        "order__sender__last_name", "order__sender__first_name",
        "order__receiver__last_name", "order__receiver__first_name",
    )
    autocomplete_fields = ("order", "material")


# =========================
# DEED
# =========================
@admin.register(Deed)
class DeedAdmin(admin.ModelAdmin):
    list_display = (
        "id", "sender", "receiver", "user",
        "status_sender", "status_receiver",
        "sender_seen", "receiver_seen",
        "file_type", "date_creat",
    )
    list_filter = (
        "status_sender", "status_receiver",
        "sender_seen", "receiver_seen",
        "file_type", "date_creat", "date_edit",
    )
    search_fields = (
        "body", "message_sender", "message_receiver", "message_user",
        "sender__last_name", "sender__first_name", "sender__father_name",
        "receiver__last_name", "receiver__first_name", "receiver__father_name",
        "user__last_name", "user__first_name", "user__father_name",
    )
    autocomplete_fields = ("sender", "receiver", "user")
    readonly_fields = ("date_creat", "date_edit")
    inlines = (DeedConsentInline,)
    date_hierarchy = "date_creat"
    ordering = ("-id",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "sender", "receiver", "user"
        )


@admin.register(DeedConsent)
class DeedConsentAdmin(admin.ModelAdmin):
    list_display = ("id", "deed", "employee", "status", "date_creat")
    list_filter = ("status", "date_creat", "date_edit")
    search_fields = (
        "message",
        "employee__last_name", "employee__first_name", "employee__father_name",
        "deed__body",
    )
    autocomplete_fields = ("deed", "employee")
    readonly_fields = ("date_creat", "date_edit")
    ordering = ("-id",)


# =========================
# LIABLE
# =========================
@admin.register(Liable)
class LiableAdmin(admin.ModelAdmin):
    list_display = ("id", "employee", "contract", "category")
    list_filter = ("category", "contract")
    search_fields = (
        "employee__last_name", "employee__first_name", "employee__father_name",
        "contract__name", "category__name",
    )
    autocomplete_fields = ("employee", "contract", "category")


# =========================
# USER ichida Employee ko‘rsatish
# =========================
class EmployeeInline(admin.StackedInline):
    model = Employee
    fk_name = "user"
    extra = 0


class UserAdmin(BaseUserAdmin):
    inlines = (EmployeeInline,)


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

admin.site.register(User, UserAdmin)

admin.site.site_header = "IVS Admin"
admin.site.site_title = "IVS Admin Panel"
admin.site.index_title = "Boshqaruv paneli"