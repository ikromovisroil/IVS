from rest_framework import permissions


class TechnicsPermission(permissions.BasePermission):
    """
    Saytdagi (main/views.py) bilan bir xil:
    Ko'rish (list/retrieve/qr) — 'view_technics'.
    Qo'shish — 'add_technics'.
    Tahrirlash va biriktirish/bo'shatish — 'change_technics'.
    O'chirish — 'delete_technics'.
    Superuser hammasiga ega (has_perm).
    """

    ACTION_PERMS = {
        'list': 'main.view_technics',
        'retrieve': 'main.view_technics',
        'qr': 'main.view_technics',
        'create': 'main.add_technics',
        'update': 'main.change_technics',
        'partial_update': 'main.change_technics',
        'assign': 'main.change_technics',
        'unassign': 'main.change_technics',
        'destroy': 'main.delete_technics',
    }

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        perm = self.ACTION_PERMS.get(view.action)
        # Noma'lum action (masalan OPTIONS) — hech narsa ochilmaydi
        return bool(perm) and request.user.has_perm(perm)


class StructurePermission(permissions.BasePermission):
    """
    Saytdagi (extra_tex*) bilan bir xil — qo'shimcha qurilmalar TEXNIKA huquqlari bilan boshqariladi:
    Ko'rish (list/retrieve) — 'change_technics' (saytda extra_tex sahifasi shuni talab qiladi).
    Qo'shish — 'add_technics'. Tahrirlash, biriktirish, ajratish — 'change_technics'.
    O'chirish — 'delete_technics'.
    """

    ACTION_PERMS = {
        'list': 'main.change_technics',
        'retrieve': 'main.change_technics',
        'create': 'main.add_technics',
        'update': 'main.change_technics',
        'partial_update': 'main.change_technics',
        'assign': 'main.change_technics',
        'unassign': 'main.change_technics',
        'destroy': 'main.delete_technics',
    }

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        perm = self.ACTION_PERMS.get(view.action)
        return bool(perm) and request.user.has_perm(perm)


class MaterialPermission(permissions.BasePermission):
    """
    Saytdagi (main/views.py) bilan bir xil:
    Ko'rish (list/retrieve) — 'view_material' (qaysi materiallar ko'rinishi get_queryset da cheklanadi).
    Qo'shish — 'add_material'.
    Tahrirlash — 'change_material'.
    O'chirish — 'delete_material'.
    Xodimga berish (give) — 'change_material' (saytdagi material_attach kabi).
    Sarflash (service) — 'material_service'.
    """

    ACTION_PERMS = {
        'list': 'main.view_material',
        'retrieve': 'main.view_material',
        'create': 'main.add_material',
        'update': 'main.change_material',
        'partial_update': 'main.change_material',
        'destroy': 'main.delete_material',
        'give': 'main.change_material',
        'service': 'main.material_service',
        'report': 'main.view_material',
        'report_employees': 'main.view_material',
    }

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        perm = self.ACTION_PERMS.get(view.action)
        return bool(perm) and request.user.has_perm(perm)


class EmployeePermission(permissions.BasePermission):
    """
    Saytdagi (main/views.py) bilan bir xil:
    Ko'rish (list/retrieve) — 'view_employee' (doira get_queryset da: o'z tashkiloti).
    Qo'shish — 'add_employee'. Tahrirlash — 'change_employee'. O'chirish — 'delete_employee'.
    """

    ACTION_PERMS = {
        'list': 'main.view_employee',
        'retrieve': 'main.view_employee',
        'create': 'main.add_employee',
        'update': 'main.change_employee',
        'partial_update': 'main.change_employee',
        'destroy': 'main.delete_employee',
        'activate': 'main.delete_employee',
        'manage_permissions': 'main.permission_employee',
    }

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        perm = self.ACTION_PERMS.get(view.action)
        return bool(perm) and request.user.has_perm(perm)


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

        if view.action in ('accept', 'reject', 'finish', 'available_materials', 'assignees'):
            return request.user.is_superuser or request.user.has_perm('main.change_order')

        if view.action == 'confirm':
            return request.user.is_superuser or request.user.has_perm('main.confirm_order')

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


class DeedPermission(permissions.BasePermission):
    """
    Saytdagi (main/views.py) bilan bir xil:
    Yaratish — 'add_deed'. 'user_edit' ni almashtirish — 'change_deed'.
    Qolgan amallar (ko'rish, tahrirlash, rad etish, kelishuvchilar) — employee profili bo'lishi yetarli;
    kim nima qila olishi view ichida (yaratuvchi / imzolovchi / kelishuvchi) tekshiriladi.
    O'chirish yo'q (saytda ham hujjat o'chirilmaydi).
    """

    ACTION_PERMS = {
        'create': 'main.add_deed',
        'toggle_user_edit': 'main.change_deed',
    }

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, 'employee', None) is None:
            return False
        perm = self.ACTION_PERMS.get(view.action)
        return request.user.has_perm(perm) if perm else True


class DeedConsentPermission(permissions.BasePermission):
    """Kelishuvchi yozuvlari: employee profili bo'lishi shart; qoidalar view ichida."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, 'employee', None) is not None


class PermissionManagerPermission(permissions.BasePermission):
    """
    Rol bilan bog'liq ma'lumotlar (ariza turlari, shartnomalar, material kategoriyalari, javobgarlik, biriktirish):
    saytda ular faqat ruxsatlar oynasida (permission_employee) ko'rinadi va o'zgaradi. Faqat o'qish.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, 'employee', None) is None:
            return False
        return request.user.has_perm('main.permission_employee')


class MaterialMovementPermission(permissions.BasePermission):
    """Material harakati jurnali — 'view_material' (saytdagi hisobot kabi)."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, 'employee', None) is None:
            return False
        return request.user.has_perm('main.view_material')

