from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User

from .models import *


# ============================
# GROUP O‘CHIRILDI
# ============================

admin.site.unregister(Group)


# ============================
# USER ADMIN + EMPLOYEE INLINE
# ============================

class EmployeeInline(admin.StackedInline):
    model = Employee
    can_delete = False
    fk_name = "user"
    extra = 0
    verbose_name = "Xodim"
    verbose_name_plural = "Xodim ma'lumotlari"
    fields = [
        "last_name",
        "first_name",
        "father_name",
        "region",
        "division",
        "directorate",
        "department",
        "organization",
        "rank",
        "status",
        "phone",
        "pinfl",
    ]


class UserAdmin(BaseUserAdmin):
    inlines = (EmployeeInline,)
    list_display = ("username", "is_active", "is_staff")
    list_filter = ("is_staff", "is_active")


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# ============================
# ORGANIZATION ADMIN
# ============================

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "org_type", "is_active")
    list_filter = ("org_type", "is_active")
    search_fields = ("name",)
    exclude = ("slug",)


# ============================
# REGION ADMIN
# ============================

@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


# ============================
# DEPARTMENT ADMIN
# ============================

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "organization")
    list_filter = ("organization",)
    search_fields = ("name",)
    exclude = ("slug",)


# ============================
# DIRECTORATE ADMIN
# ============================

@admin.register(Directorate)
class DirectorateAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "department")
    list_filter = ("department",)
    search_fields = ("name",)
    exclude = ("slug",)


# ============================
# DIVISION ADMIN
# ============================

@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "directorate")
    list_filter = ("directorate",)
    search_fields = ("name",)
    exclude = ("slug",)


# ============================
# RANK ADMIN
# ============================

@admin.register(Rank)
class RankAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


# ============================
# EMPLOYEE ADMIN
# ============================

from django.contrib import admin
from .models import *


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "full_name",
        "pinfl",
        "organization",
        "department",
        "directorate",
        "division",
        "region",
        "rank",
        "status",
    )

    list_filter = (
        "organization",
        "department",
        "directorate",
        "division",
        "region",
        "rank",
        "status",
    )

    search_fields = (
        "last_name",
        "first_name",
        "father_name",
        "phone",
        "pinfl",
    )

    exclude = ("slug",)

    # Admin sarlavhasi va tartiblash
    def full_name_display(self, obj):
        return obj.full_name or "—"

    full_name_display.short_description = "F.I.Sh"
    full_name_display.admin_order_field = "last_name"



# ============================
# CATEGORY ADMIN
# ============================

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)
    exclude = ("slug",)


# ============================
# Manitor ADMIN
# ============================
@admin.register(Manitor)
class ManitorAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "technics",
        "name",
        "inventory",
        "serial",
        "year",
        "number",
        "price",
        "date_creat",
    )
    list_filter = ("technics", "year")
    search_fields = (
        "name",
        "serial",
        "inventory",
        "technics__name",  # FK bo‘lgani uchun __name ishlatamiz
    )


@admin.register(Technics)
class TechnicsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "category",
        "employee",
        "status",
        "inventory",
        "serial",
    )
    list_filter = ("category", "status")
    search_fields = ("name", "inventory", "serial")


# ============================
# MATERIAL ADMIN
# ============================

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "employee", "technics", "status", "inventory")
    list_filter = ("status",)
    search_fields = ("name", "inventory")


# ============================
# TOPIC & GOAL ADMIN
# ============================

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "topic")
    list_filter = ("topic",)
    search_fields = ("name",)


# ============================
# ORDER MATERIAL INLINE
# ============================

class OrderMaterialInline(admin.TabularInline):
    model = OrderMaterial
    extra = 0


# ============================
# ORDER ADMIN
# ============================

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderMaterialInline]

    list_display = (
        "id",
        "sender",
        "receiver",
        "goal",
        "status",
        "date_creat",
    )

    list_filter = ("status", "goal")
    search_fields = (
        "body",
        "sender__last_name",
        "sender__first_name",
        "receiver__last_name",
        "receiver__first_name",
    )


# ============================
# DEED ADMIN
# ============================

@admin.register(Deed)
class DeedAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "sender",
        "receiver",
        "status",
        "sender_seen",
        "date_creat",
    )

    list_filter = ("status", "sender_seen")

    search_fields = (
        "sender__last_name",
        "sender__first_name",
        "receiver__last_name",
        "receiver__first_name",
    )
