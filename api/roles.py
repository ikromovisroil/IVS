"""
Xodimga ruxsat (rol) berish — saytdagi employee_permission (main/views.py) qoidalari bilan bir xil:
 * 'permission_employee' (ko'rish va o'zgartirish) va 'change_employee' (o'zgartirish) huquqlari;
 * faqat o'z tashkiloti xodimi (all_organization bo'lsa — hammasi);
 * nishon xodim tashkiloti va so'rovchi tashkiloti turiga qarab ayrim ruxsatlar ko'rinmaydi/berilmaydi;
 * SUPER ruxsatlarni (all_organization, all_region, permission_employee, all_material_employee) faqat o'zida bor odam bera oladi;
 * "ko'rish" o'chirilsa unga bog'liq (qo'shish/tahrirlash/o'chirish...) ruxsatlar ham o'chadi;
 * ariza turlari, texnika kategoriyalari, shartnomalar, material kategoriyalari biriktiriladi.
Farqi: o'zgartirish qisman bo'lishi mumkin (faqat yuborilgan kalitlar), va yuborilgan ID lar mavjud variantlar ichida bo'lishi shart.
"""
from django.contrib.auth.models import Permission
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from core.models import AuditLog
from core.request_context import get_client_ip
from main.models import (
    Category, Contract, Goal, Liable, MaterialCategory, MaterialEmployee, OrderGoal,
)
from main.views import DEPENDENT_PERMS, PERM_CODENAMES, SUPER_PERMS, _visible_perm_fields

# (guruh, nomi) — saytdagi "ruxsatlar" oynasi bilan bir xil
LABELS = {
    "add_order": ("Ariza", "Ariza yaratish"),
    "change_order": ("Ariza", "Ariza bajarish"),
    "confirm_order": ("Ariza", "Arizani tasdiqlash"),
    "add_deed": ("Hujjatlar", "Hujjat yaratish"),
    "change_deed": ("Hujjatlar", "Hujjatni tahrirlash"),
    "all_organization": ("Ko'rish doirasi", "Barcha tashkilotlarni ko'rish"),
    "all_region": ("Ko'rish doirasi", "Barcha hududlarni ko'rish"),
    "view_technics": ("Texnika", "Texnikalarni ko'rish"),
    "add_technics": ("Texnika", "Texnikalarni qo'shish"),
    "change_technics": ("Texnika", "Texnikalarni tahrirlash"),
    "delete_technics": ("Texnika", "Texnikalarni o'chirish"),
    "view_material": ("Material", "Materiallarni ko'rish"),
    "add_material": ("Material", "Materiallarni qo'shish"),
    "change_material": ("Material", "Materiallarni tahrirlash"),
    "delete_material": ("Material", "Materiallarni o'chirish"),
    "material_service": ("Material", "Materiallarni sarflash"),
    "all_material_employee": ("Material", "Barcha xodimlarning materialini ko'rish"),
    "view_meeting": ("Uchrashuvlar (Zoom)", "Hamma uchrashuvlarni ko'rish"),
    "add_meeting": ("Uchrashuvlar (Zoom)", "Uchrashuv yaratish"),
    "delete_meeting": ("Uchrashuvlar (Zoom)", "Uchrashuvni o'chirish"),
    "view_employee": ("Xodimlar", "Xodimlarni ko'rish"),
    "add_employee": ("Xodimlar", "Xodimlarni qo'shish"),
    "change_employee": ("Xodimlar", "Xodimlarni tahrirlash"),
    "delete_employee": ("Xodimlar", "Xodimlarni o'chirish"),
    "boss_employee": ("Maxsus rollar", "Departament rahbari (boshliq)"),
    "shop_employee": ("Maxsus rollar", "Materialga javobgar shaxs"),
    "status_employee": ("Maxsus rollar", "Statistikani ko'rish"),
    "permission_employee": ("Maxsus rollar", "Xodimlarga rol berish"),
    "report_employee": ("Hisobotlar", "Hisobotlarni ko'rish"),
}


def catalog():
    groups = {}
    for key in PERM_CODENAMES:
        group, label = LABELS.get(key, ("Boshqa", key))
        groups.setdefault(group, []).append({"key": key, "label": label})
    return {
        "groups": [{"title": t, "items": items} for t, items in groups.items()],
        "dependent": DEPENDENT_PERMS,
        "super_permissions": sorted(SUPER_PERMS),
    }


def _perm_objects(key):
    app_label, codename = PERM_CODENAMES[key].split(".")
    return list(Permission.objects.filter(content_type__app_label=app_label, codename=codename))


def _direct_keys(user):
    """Foydalanuvchiga BEVOSITA berilgan ruxsatlar (saytdagi katakchalar shuni ko'rsatadi)."""
    granted = set(user.user_permissions.values_list("content_type__app_label", "codename"))
    return {k for k, v in PERM_CODENAMES.items() if tuple(v.split(".")) in granted}


def _options(current_emp, target):
    is_client = bool(current_emp.organization and current_emp.organization.type != "worker")
    goals = Goal.objects.filter(organization=current_emp.organization) if is_client else Goal.objects.all()
    mat_cats = MaterialCategory.objects.filter(organization=target.organization) if target.organization_id else MaterialCategory.objects.none()
    return {
        "goals": goals.order_by("name", "id"),
        "categories": Category.objects.select_related("group").order_by("name", "id"),
        "contracts": Contract.objects.order_by("id"),
        "material_categories": mat_cats.order_by("name", "id"),
    }


def _ids(qs):
    return list(qs.values_list("id", flat=True))


def _selected(target):
    goals = OrderGoal.goal.through.objects.filter(ordergoal__employee=target).values_list("goal_id", flat=True)
    liable = Liable.objects.filter(employee=target).first()
    return {
        "goals": sorted(set(goals)),
        "categories": sorted(_ids(liable.categorys)) if liable else [],
        "contracts": sorted(_ids(liable.contracts)) if liable else [],
        "material_categories": sorted(set(
            MaterialEmployee.category.through.objects.filter(materialemployee__employee=target)
            .values_list("materialcategory_id", flat=True)
        )),
    }


def state(request_user, current_emp, target):
    """Nishon xodimning joriy ruxsatlari va tanlash variantlari."""
    visible = _visible_perm_fields(target, current_emp)
    direct = _direct_keys(target.user)
    perms = []
    for key in PERM_CODENAMES:
        group, label = LABELS.get(key, ("Boshqa", key))
        can_set = key in visible and (key not in SUPER_PERMS or request_user.has_perm(PERM_CODENAMES[key]))
        perms.append({
            "key": key, "label": label, "group": group,
            "granted": key in direct,                                   # bevosita berilgan (o'zgartiriladigan)
            "effective": target.user.has_perm(PERM_CODENAMES[key]),     # guruh orqali ham hisobga olingan
            "editable": bool(can_set),
        })
    opts = _options(current_emp, target)
    sel = _selected(target)
    target_is_worker = target.organization_id and target.organization.type == "worker"
    return {
        "employee": {
            "id": target.id, "full_name": target.full_name,
            "organization_type": target.organization.type if target.organization_id else None,
        },
        "permissions": perms,
        "goals": {
            "enabled": "change_order" in direct,
            "options": [{"id": g.id, "name": g.name} for g in opts["goals"]], "selected": sel["goals"],
        },
        "categories": {
            "enabled": "view_technics" in direct,
            "options": [{"id": c.id, "name": c.name, "group": c.group.name if c.group_id else None} for c in opts["categories"]],
            "selected": sel["categories"],
        },
        "contracts": {
            "enabled": "report_employee" in direct,
            "options": [{"id": c.id, "name": str(c)} for c in opts["contracts"]], "selected": sel["contracts"],
        },
        "material_categories": {
            "enabled": not target_is_worker,
            "options": [{"id": m.id, "name": m.name} for m in opts["material_categories"]], "selected": sel["material_categories"],
        },
    }


def _validated_ids(data, key, options_qs):
    if key not in data:
        return None
    raw = data[key]
    if not isinstance(raw, (list, tuple)) or any(isinstance(x, bool) or not str(x).isdigit() for x in raw):
        raise ValidationError({key: "ID lar ro'yxati bo'lishi kerak"})
    wanted = {int(x) for x in raw}
    valid = set(options_qs.filter(id__in=wanted).values_list("id", flat=True))
    if wanted - valid:
        raise ValidationError({key: f"Ruxsat etilmagan yoki mavjud bo'lmagan ID lar: {sorted(wanted - valid)}"})
    return valid


@transaction.atomic
def apply(request, current_emp, target, data):
    """Ruxsatlarni qo'llaydi. {"ignored": [...]} qaytaradi (ko'rinmaydigan yoki berishga haqi yo'q kalitlar)."""
    user = request.user
    if not target.user_id:
        raise ValidationError({"detail": "Bu xodimga User biriktirilmagan"})

    raw_perms = data.get("permissions") or {}
    if not isinstance(raw_perms, dict):
        raise ValidationError({"permissions": "Obyekt bo'lishi kerak: {kalit: true|false}"})
    unknown = [k for k in raw_perms if k not in PERM_CODENAMES]
    if unknown:
        raise ValidationError({"permissions": f"Noma'lum ruxsatlar: {unknown}"})
    for k, v in raw_perms.items():
        if not isinstance(v, bool):
            raise ValidationError({"permissions": f"'{k}' qiymati true yoki false bo'lishi kerak"})

    visible = _visible_perm_fields(target, current_emp)
    direct = _direct_keys(target.user)
    final, ignored = {}, []
    for key in visible:
        final[key] = key in direct
    for key, value in raw_perms.items():
        if key not in visible or (key in SUPER_PERMS and not user.has_perm(PERM_CODENAMES[key])):
            ignored.append(key)
            continue
        final[key] = value

    for master, subs in DEPENDENT_PERMS.items():
        if master in final and not final[master]:
            for sub in subs:
                if sub in final:
                    final[sub] = False

    for key, granted in final.items():
        objs = _perm_objects(key)
        if granted:
            target.user.user_permissions.add(*objs)
        else:
            target.user.user_permissions.remove(*objs)

    opts = _options(current_emp, target)
    sel = _selected(target)
    goals = _validated_ids(data, "goals", opts["goals"])
    cats = _validated_ids(data, "categories", opts["categories"])
    contracts = _validated_ids(data, "contracts", opts["contracts"])
    mats = _validated_ids(data, "material_categories", opts["material_categories"])

    # Ariza turlari: faqat "ariza bajarish" bor bo'lsa
    new_goals = (goals if goals is not None else set(sel["goals"])) if final.get("change_order") else set()
    OrderGoal.objects.filter(employee=target).delete()
    if new_goals:
        OrderGoal.objects.create(employee=target).goal.set(new_goals)

    # Texnika kategoriyalari ("ko'rish") va shartnomalar ("hisobotlar")
    new_cats = (cats if cats is not None else set(sel["categories"])) if final.get("view_technics") else set()
    new_contracts = set()
    if final.get("report_employee"):
        new_contracts = contracts if contracts is not None else set(sel["contracts"])
        if not new_contracts:   # saytdagidek: tanlanmasa — hammasi
            new_contracts = set(Contract.objects.values_list("id", flat=True))
    Liable.objects.filter(employee=target).delete()
    if new_cats or new_contracts:
        liable = Liable.objects.create(employee=target)
        liable.categorys.set(new_cats)
        liable.contracts.set(new_contracts)

    # Material kategoriyalari: faqat worker bo'lmagan tashkilot xodimi uchun
    if target.organization_id and target.organization.type != "worker":
        new_mats = mats if mats is not None else set(sel["material_categories"])
        MaterialEmployee.objects.filter(employee=target).delete()
        if new_mats:
            MaterialEmployee.objects.create(employee=target).category.set(new_mats)

    AuditLog.objects.create(
        employee=current_emp, action="update", model="Permission", object_id=target.id,
        path=request.path, method=request.method, ip=get_client_ip(request._request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
        description=f"Ruxsatlar o'zgartirildi: xodim #{target.id}; yoqilgan: "
                    f"{sorted(k for k, v in final.items() if v)}",
    )
    return {"ignored": sorted(set(ignored))}


def check_access(request, target_org_id, current_emp, writing):
    user = request.user
    if not user.has_perm("main.permission_employee"):
        raise PermissionDenied("Ruxsatlarni boshqarish huquqi yo'q")
    if writing and not user.has_perm("main.change_employee"):
        raise PermissionDenied("Sizga ruxsat yo'q")
    if not user.has_perm("main.all_organization") and target_org_id != current_emp.organization_id:
        raise PermissionDenied("Boshqa tashkilot xodimini o'zgartira olmaysiz")
