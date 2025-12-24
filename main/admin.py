from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group

from .models import *

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
        "region",
        "division",
        "directorate",
        "department",
        "organization",
        "rank",
        "status",
        "phone",
    ]


class UserAdmin(BaseUserAdmin):
    inlines = (EmployeeInline, )


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# ============================
# ORGANIZATION ADMIN
# ============================

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('id',"name", "org_type")
    list_filter = ("org_type",)
    search_fields = ("name", "org_type")
    exclude = ("slug",)



# ============================
# STRUCTURE ADMIN
# ============================

@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ('id',"name",)
    search_fields = ("name",)


# ============================
# DEPARTMENT ADMIN
# ============================

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('id',"name", "organization",)
    list_filter = ("organization",)
    search_fields = ("name",)
    exclude = ("slug",)


# ============================
# DIRECTORATE ADMIN
# ============================

@admin.register(Directorate)
class DirectorateAdmin(admin.ModelAdmin):
    list_display = ('id',"name", "department",)
    list_filter = ("department",)
    search_fields = ("name",)
    exclude = ("slug",)



# ============================
# DIVISION ADMIN
# ============================

@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ('id',"name", "directorate",)
    list_filter = ("directorate",)
    search_fields = ("name",)
    exclude = ("slug",)



# ============================
# RANK ADMIN
# ============================

@admin.register(Rank)
class RankAdmin(admin.ModelAdmin):
    list_display = ('id',"name",)
    search_fields = ("name",)


# ============================
# EMPLOYEE ADMIN
# ============================

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user_full_name",
        "region",
        "division",
        "directorate",
        "department",
        "organization",
        "rank",
        "status",
    )
    list_filter = ("region", "division", "directorate",
                   "department", "organization", "rank", "status")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "phone"
    )
    exclude = ("slug",)

    def user_full_name(self, obj):
        if obj.user:
            return obj.user.get_full_name()
        return "-"

    user_full_name.short_description = "F.I.Sh"
    user_full_name.admin_order_field = "user__first_name"


# ============================
# CATEGORY ADMIN
# ============================

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id',"name",)
    search_fields = ("name",)
    exclude = ("slug",)



# ============================
# TECHNICS ADMIN
# ============================

@admin.register(Technics)
class TechnicsAdmin(admin.ModelAdmin):
    list_display = ('id',"name", "category", "employee", "status", "inventory", "serial")
    list_filter = ("category", "status")
    search_fields = ("name", "inventory", "serial")


# ============================
# MATERIAL ADMIN
# ============================

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('id',"name", "employee", "technics", "status", "inventory")
    list_filter = ("status",)
    search_fields = ("name", "inventory")


# ============================
# TOPIC & GOAL ADMIN
# ============================

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('id',"name",)
    search_fields = ("name",)


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ('id',"name", "topic")
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
    list_display = ("id", "sender", "receiver", "goal", "status", "date_creat")
    list_filter = ("status", "goal")
    search_fields = ("body", "sender__user__username", "receiver__user__username")


# ============================
# DEED ADMIN
# ============================

@admin.register(Deed)
class DeedAdmin(admin.ModelAdmin):
    list_display = ("id", "sender", "receiver", "status", "sender_seen", "date_creat")
    list_filter = ("status", "sender_seen")
    search_fields = ("sender__user__username", "receiver__user__username")

