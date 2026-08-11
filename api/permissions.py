from rest_framework import permissions


class TechnicsPermission(permissions.BasePermission):
    """
    Ko'rish (list/retrieve) — har qanday autentifikatsiyadan o'tgan foydalanuvchi.
    Qo'shish — 'add_technics' ruxsati kerak.
    Tahrirlash — 'change_technics' ruxsati kerak.
    O'chirish — 'delete_technics' ruxsati kerak.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if view.action == 'create':
            return request.user.is_superuser or request.user.has_perm('main.add_technics')

        if view.action in ('update', 'partial_update'):
            return request.user.is_superuser or request.user.has_perm('main.change_technics')

        if view.action == 'destroy':
            return request.user.is_superuser or request.user.has_perm('main.delete_technics')

        return True


class StructurePermission(permissions.BasePermission):
    """
    Ko'rish (list/retrieve) — har qanday autentifikatsiyadan o'tgan foydalanuvchi.
    Qo'shish — 'add_structure' ruxsati kerak.
    Tahrirlash / biriktirish — 'change_structure' ruxsati kerak.
    O'chirish — 'delete_structure' ruxsati kerak.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if view.action == 'create':
            return request.user.is_superuser or request.user.has_perm('main.add_structure')

        if view.action in ('update', 'partial_update', 'assign', 'unassign'):
            return request.user.is_superuser or request.user.has_perm('main.change_structure')

        if view.action == 'destroy':
            return request.user.is_superuser or request.user.has_perm('main.delete_structure')

        return True


class MaterialPermission(permissions.BasePermission):
    """
    Ko'rish (list/retrieve) — get_queryset orqali cheklanadi
    (shop_employee: faqat o'ziniki, all_material_employee: tashkilotdagi barchasi).
    Qo'shish — 'shop_employee' yoki 'add_material' ruxsati kerak.
    Tahrirlash — 'shop_employee' yoki 'change_material' ruxsati kerak.
    O'chirish — 'shop_employee' yoki 'delete_material' ruxsati kerak.
    Berish (give) — alohida, action ichida 'all_material_employee' tekshiriladi.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if view.action == 'create':
            return (
                request.user.is_superuser
                or request.user.has_perm('main.shop_employee')
                or request.user.has_perm('main.add_material')
            )

        if view.action in ('update', 'partial_update'):
            return (
                request.user.is_superuser
                or request.user.has_perm('main.shop_employee')
                or request.user.has_perm('main.change_material')
            )

        if view.action == 'destroy':
            return (
                request.user.is_superuser
                or request.user.has_perm('main.shop_employee')
                or request.user.has_perm('main.delete_material')
            )

        # list, retrieve, give — get_queryset yoki action ichida tekshiriladi
        return True


class OrderPermission(permissions.BasePermission):
    """
    Ko'rish/Yaratish — employee profiliga ega har qanday xodim.
    Qabul qilish (accept) / Yakunlash (finish) / Material qo'shish (add_material)
    — 'change_order' ruxsati kerak.
    Hal qilish (decide) / Yakuniy qabul (accepted) — obyekt darajasida
    (view ichida) sender/user/confirm_order tekshiriladi.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if not getattr(request.user, 'employee', None):
            return False

        if view.action in ('accept', 'finish', 'add_material'):
            return request.user.is_superuser or request.user.has_perm('main.change_order')

        return True


class OrderMaterialPermission(permissions.BasePermission):
    """
    Ko'rish — employee profiliga ega har qanday xodim (get_queryset orqali cheklanadi).
    Tahrirlash/O'chirish — faqat arizaning receiver'i.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, 'employee', None) is not None


class OrderGoalPermission(permissions.BasePermission):
    """
    Ko'rish — get_queryset orqali cheklanadi (o'z tashkiloti).
    Yaratish/Tahrirlash/O'chirish — tegishli standart Django permission kerak.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if view.action == 'create':
            return request.user.is_superuser or request.user.has_perm('main.add_ordergoal')

        if view.action in ('update', 'partial_update'):
            return request.user.is_superuser or request.user.has_perm('main.change_ordergoal')

        if view.action == 'destroy':
            return request.user.is_superuser or request.user.has_perm('main.delete_ordergoal')

        return True


class MaterialUserPermission(permissions.BasePermission):
    """
    Ko'rish — get_queryset orqali cheklanadi (o'z tashkiloti).
    Yaratish/Tahrirlash/O'chirish — tegishli standart Django permission kerak.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if view.action == 'create':
            return request.user.is_superuser or request.user.has_perm('main.add_materialuser')

        if view.action in ('update', 'partial_update'):
            return request.user.is_superuser or request.user.has_perm('main.change_materialuser')

        if view.action == 'destroy':
            return request.user.is_superuser or request.user.has_perm('main.delete_materialuser')

        return True


class DeedPermission(permissions.BasePermission):
    """Har qanday employee profiliga ega xodim — ko'rish, qo'shish, tahrirlash, o'chirish."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, 'employee', None) is not None


class DeedConsentPermission(permissions.BasePermission):
    """Har qanday employee profiliga ega xodim — ko'rish, qo'shish, tahrirlash, o'chirish."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, 'employee', None) is not None


class LiablePermission(permissions.BasePermission):
    """
    Ko'rish — har qanday employee profiliga ega xodim.
    Yaratish/Tahrirlash/O'chirish — tegishli standart Django permission kerak.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if not getattr(request.user, 'employee', None):
            return False

        if view.action == 'create':
            return request.user.is_superuser or request.user.has_perm('main.add_liable')

        if view.action in ('update', 'partial_update'):
            return request.user.is_superuser or request.user.has_perm('main.change_liable')

        if view.action == 'destroy':
            return request.user.is_superuser or request.user.has_perm('main.delete_liable')

        return True