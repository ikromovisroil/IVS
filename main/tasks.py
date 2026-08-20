# main/tasks.py
import logging
import re
import time
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from .models import *

logger = logging.getLogger(__name__)


# =========================================================
# KONSTANTALAR
# =========================================================
DEFAULT_REGION_ID = 3

SYNC_LOCK_KEY = "sync_all_employees_lock"
SYNC_LOCK_TIMEOUT = 60 * 60  # 1 soat


# =========================================================
# KIRILL → LOTIN KONVERTATSIYA
# =========================================================
CYRILLIC_TO_LATIN = {
    'а': 'a',  'б': 'b',  'в': 'v',  'г': 'g',  'д': 'd',
    'е': 'e',  'ё': 'yo', 'ж': 'j',  'з': 'z',  'и': 'i',
    'й': 'y',  'к': 'k',  'л': 'l',  'м': 'm',  'н': 'n',
    'о': 'o',  'п': 'p',  'р': 'r',  'с': 's',  'т': 't',
    'у': 'u',  'ф': 'f',  'х': 'x',  'ц': 'ts', 'ч': 'ch',
    'ш': 'sh', 'щ': 'sh', 'ъ': "ʼ",  'ы': 'i',  'ь': '',
    'э': 'e',  'ю': 'yu', 'я': 'ya',
    'ғ': "gʼ", 'қ': 'q',  'ҳ': 'h',  'ў': "oʼ", 'ҷ': 'j',
}


def cyrillic_to_latin(text: str) -> str:
    if not text:
        return text
    result = []
    for char in text:
        lower = char.lower()
        if lower in CYRILLIC_TO_LATIN:
            converted = CYRILLIC_TO_LATIN[lower]
            if char.isupper() and converted:
                converted = converted.upper()
            result.append(converted)
        else:
            result.append(char)
    return ''.join(result)


def has_cyrillic(text: str) -> bool:
    return bool(re.search('[а-яА-ЯёЁғқҳўҷҒҚҲЎҶ]', text or ''))


# =========================================================
# CELERY TASK
# =========================================================
# ✅ Bu task hech qachon bazaga avtomatik yozmaydi:
#   - Employee'ning organization/department/directorate/division/rank
#     maydonlarini o'zgartirmaydi.
#   - Xodimni bloklamaydi/deaktiv qilmaydi.
#   - Yangi Department/Directorate yozuvlarini YARATMAYDI (bu avvalgi
#     versiyada eng katta muammo edi - "faqat ko'rsatish" rejimida ham
#     tizimga yangi Department/Directorate qo'shib qo'yardi).
# Faqat Gateway'dagi ma'lumot bilan bazadagi ma'lumot orasidagi FARQNI
# aniqlaydi va shu farqni SyncLog/SyncEmployeeLog orqali "xabar"
# sifatida yozib qo'yadi. Xodimni tahrirlash, bloklash yoki yangi
# Department/Directorate yaratish - FAQAT admin tomonidan qo'lda
# amalga oshiriladi.
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_all_employees(self, apply_changes=False):
    from .models import Employee
    from core.models import SyncLog, SyncEmployeeLog

    if not cache.add(SYNC_LOCK_KEY, "locked", timeout=SYNC_LOCK_TIMEOUT):
        logger.warning("sync_all_employees allaqachon ishlamoqda, bu ishga tushish o'tkazib yuborildi")
        return {"skipped_run": True}

    try:
        employees = Employee.objects.select_related(
            "user", "organization", "department", "directorate", "division"
        ).filter(
            pinfl__isnull=False,
            user__isnull=False,
        ).exclude(pinfl="")

        total       = employees.count()
        changed     = 0
        would_block = 0
        skipped     = 0
        errors      = 0
        start_time  = time.time()

        sync_log = SyncLog.objects.create(total=total)

        logger.info(
            "sync_all_employees boshlandi: %d xodim (apply_changes=%s)",
            total, apply_changes
        )

        for emp in employees.iterator(chunk_size=50):
            try:
                result, changes = _sync_single_employee(emp, apply_changes=apply_changes)

                if result == "would_block":
                    would_block += 1
                    SyncEmployeeLog.objects.create(
                        sync      = sync_log,
                        employee  = emp,
                        pinfl     = emp.pinfl,
                        full_name = emp.full_name,
                        result    = "blocked",
                        changes   = "Gatewayda ish joyi topilmadi (avtomatik bloklanmadi - qo'lda ko'rib chiqing)",
                    )
                elif result == "changed":
                    changed += 1
                    SyncEmployeeLog.objects.create(
                        sync      = sync_log,
                        employee  = emp,
                        pinfl     = emp.pinfl,
                        full_name = emp.full_name,
                        result    = "updated",
                        changes   = f"[Aniqlandi, avtomatik qo'llanilmadi] {changes}",
                    )
                elif result == "applied":
                    changed += 1
                    SyncEmployeeLog.objects.create(
                        sync      = sync_log,
                        employee  = emp,
                        pinfl     = emp.pinfl,
                        full_name = emp.full_name,
                        result    = "updated",
                        changes   = changes,
                    )
                elif result == "blocked":
                    would_block += 1
                    SyncEmployeeLog.objects.create(
                        sync      = sync_log,
                        employee  = emp,
                        pinfl     = emp.pinfl,
                        full_name = emp.full_name,
                        result    = "blocked",
                        changes   = "Gatewayda ish joyi topilmadi",
                    )
                else:
                    skipped += 1

            except Exception as e:
                errors += 1
                logger.warning("PINFL %s sync xatosi: %s", emp.pinfl, e)
                SyncEmployeeLog.objects.create(
                    sync      = sync_log,
                    employee  = emp,
                    pinfl     = emp.pinfl,
                    full_name = emp.full_name,
                    result    = "error",
                    error_msg = str(e),
                )

        duration = int(time.time() - start_time)

        if errors == 0:
            status = "success"
        elif errors < total:
            status = "partial"
        else:
            status = "failed"

        SyncLog.objects.filter(pk=sync_log.pk).update(
            updated  = changed,
            blocked  = would_block,
            skipped  = skipped,
            errors   = errors,
            duration = duration,
            status   = status,
        )

        logger.info(
            "sync tugadi | aniqlangan_farq=%d | bloklanishi_kerak=%d | ozgarishsiz=%d | xato=%d | jami=%d | vaqt=%ds | apply_changes=%s",
            changed, would_block, skipped, errors, total, duration, apply_changes
        )
        return {
            "apply_changes": apply_changes,
            "changed":       changed,
            "would_block":   would_block,
            "skipped":       skipped,
            "errors":        errors,
            "total":         total,
            "duration":      duration,
        }

    finally:
        cache.delete(SYNC_LOCK_KEY)


# =========================================================
# SYNC SINGLE EMPLOYEE
# =========================================================
def _sync_single_employee(emp, apply_changes=False):
    from .gateway import GatewayClient

    pinfl = emp.pinfl

    try:
        gateway_data = GatewayClient.current_citizen(pinfl)
    except Exception as e:
        raise Exception(f"Gateway xatosi: {e}")

    result    = (gateway_data or {}).get("result") or {}
    positions = result.get("positions") or []

    if not positions:
        if apply_changes:
            _block_employee(emp, pinfl)
            return "blocked", ""
        return "would_block", ""

    # ✅ FIX: create_missing=False - hech qanday yangi Department/Directorate
    # yozuvi yaratilmaydi, faqat MAVJUDLARI qidiriladi.
    assigned = _resolve_position(pinfl, positions, create_missing=False)

    if not assigned:
        # Bu holat FAQAT org_tin butunlay hech qaysi Organization/Department
        # bilan mos kelmasa yuz beradi (tizimda bu tashkilot umuman yo'q) -
        # haqiqatan "ish joyi aniqlanmadi" degani.
        if apply_changes:
            _block_employee(emp, pinfl)
            return "blocked", ""
        return "would_block", ""

    if not _has_changed(emp, assigned, result=result):
        return "skipped", ""

    # Har doim faqat MATN ko'rinishida farqni hisoblaymiz - DBga yozmaymiz
    changes = _describe_changes(emp, assigned, result=result)

    if not apply_changes:
        return "changed", changes

    # apply_changes=True bo'lganda ham, agar department/directorate topilmagan
    # (faqat nomi/kodi ma'lum, lekin bazada mavjud emas) bo'lsa - buni ham
    # avtomatik yaratmaymiz, chunki bu qo'lda tekshirilishi kerak bo'lgan
    # holat. Shunday holatda "applied" emas, balki xabar bilan qaytaramiz.
    if assigned.get("_dep_unresolved"):
        note = (
            f"{changes} | DIQQAT: Departament/Boshqarma bazada topilmadi "
            f"(kod={assigned.get('_dep_id')!r}, nomi={assigned.get('_dep_name')!r}) - "
            f"avval uni qo'lda yarating, keyin qayta urinib ko'ring."
        )
        return "changed", note

    with transaction.atomic():
        changes = _apply_changes(emp, assigned, result=result)

    return "applied", changes


# =========================================================
# RESOLVE POSITION
# =========================================================
def _get_default_region():
    return Region.objects.filter(id=DEFAULT_REGION_ID).first()


def _resolve_position(sso_pinfl, positions, create_missing=False):
    """
    Gateway'dan kelgan positions ro'yxati bo'yicha xodimning tashkiliy
    joylashuvini ANIQLASHGA harakat qiladi.

    create_missing=False (STANDART, tavsiya etiladi):
        Department/Directorate topilmasa - HECH NARSA yaratilmaydi.
        Qaytarilgan data'da mos maydon None qoladi va
        "_dep_unresolved": True, "_dep_id"/"_dep_name" belgilanadi -
        bu keyinchalik xabarda "qo'lda yarating" deb ko'rsatish uchun
        ishlatiladi.

    create_missing=True:
        Eski xatti-harakat - topilmasa avtomatik yaratadi. Faqat
        maxsus/kelajakdagi "to'liq avtomatik" senariylar uchun
        qoldirilgan, ODATDAGI sync jarayonida ISHLATILMAYDI.
    """
    from .models import Organization, Department, Directorate, Division, Rank

    for pos in positions:
        org_tin     = str(pos.get("org_tin")     or "").strip()
        dep_id      = str(pos.get("dep_id")      or "").strip()
        dep_name    = cyrillic_to_latin((pos.get("dep_name") or "").strip())
        position_id = str(pos.get("position_id") or "").strip()
        position    = cyrillic_to_latin((pos.get("position") or "").strip())

        if not org_tin:
            continue

        rank = None
        if position_id:
            rank = Rank.objects.filter(code=position_id).first()

        data = {
            "organization": None,
            "department":   None,
            "directorate":  None,
            "division":     None,
            "rank":         rank,
            "_position_id": position_id,
            "_position":    position,
            "_dep_id":      dep_id,
            "_dep_name":    dep_name,
            "_dep_unresolved": False,
        }

        # HOLAT A: Organization.inn == org_tin
        organization = Organization.objects.filter(inn=org_tin).first()
        if organization:
            data["organization"] = organization

            if dep_id:
                division = Division.objects.filter(
                    code=dep_id,
                    directorate__department__organization=organization
                ).first()
                if division:
                    data["division"]    = division
                    data["directorate"] = division.directorate
                    data["department"]  = division.directorate.department if division.directorate else None
                    return data

                directorate = Directorate.objects.filter(
                    code=dep_id,
                    department__organization=organization
                ).first()
                if directorate:
                    data["directorate"] = directorate
                    data["department"]  = directorate.department
                    return data

                department = Department.objects.filter(
                    code=dep_id,
                    organization=organization
                ).first()
                if department:
                    data["department"] = department
                    return data

                # Department topilmadi
                if create_missing:
                    region = getattr(organization, "region", None)
                    if not region:
                        region = _get_default_region()

                    department, created = Department.objects.get_or_create(
                        code=dep_id,
                        organization=organization,
                        region=region,
                        defaults={"name": dep_name or f"Bolim-{dep_id}"},
                    )
                    if created:
                        logger.info("Department yaratildi: %s", department)
                    data["department"] = department
                    return data
                else:
                    # Hech narsa yaratmaymiz - faqat "topilmadi" deb belgilaymiz
                    data["_dep_unresolved"] = True
                    return data

            return data

        # HOLAT B: Department.inn == org_tin
        department = Department.objects.filter(inn=org_tin).first()
        if department:
            data["department"]   = department
            data["organization"] = department.organization

            if dep_id:
                directorate = Directorate.objects.filter(
                    code=dep_id,
                    department=department
                ).first()
                if directorate:
                    data["directorate"] = directorate
                    return data

                # Directorate topilmadi
                if create_missing:
                    directorate, created = Directorate.objects.get_or_create(
                        code=dep_id,
                        department=department,
                        defaults={"name": cyrillic_to_latin(dep_name or f"Boshqarma-{dep_id}")},
                    )
                    if created:
                        logger.info("Directorate yaratildi: %s", directorate)
                    data["directorate"] = directorate
                    return data
                else:
                    # Hech narsa yaratmaymiz - faqat "topilmadi" deb belgilaymiz
                    data["_dep_unresolved"] = True
                    return data

            return data

        logger.warning(
            "PINFL %s → org_tin=%s hech qaysi modelga mos kelmadi",
            sso_pinfl, org_tin
        )

    return None


# =========================================================
# HAS CHANGED
# =========================================================
def _has_changed(emp, assigned, result=None):
    structure_changed = (
        emp.organization_id != getattr(assigned["organization"], "id", None) or
        emp.department_id   != getattr(assigned["department"],   "id", None) or
        emp.directorate_id  != getattr(assigned["directorate"],  "id", None) or
        emp.division_id     != getattr(assigned["division"],     "id", None) or
        emp.rank_id         != getattr(assigned.get("rank"),     "id", None)
    )

    if structure_changed:
        return True

    # Department/Directorate hali "topilmadi" holatida bo'lsa ham,
    # bu ADMIN uchun muhim signal - shuning uchun "o'zgargan" deb
    # hisoblaymiz, shunda SyncEmployeeLog'da ko'rinadi.
    if assigned.get("_dep_unresolved"):
        return True

    if result:
        new_first  = cyrillic_to_latin((result.get("name")       or "").strip())
        new_last   = cyrillic_to_latin((result.get("surname")    or "").strip())
        new_father = cyrillic_to_latin((result.get("partonimic") or "").strip())
        name_changed = (
            (emp.first_name or "") != new_first or
            (emp.last_name or "") != new_last or
            (emp.father_name or "") != new_father
        )
        if name_changed:
            return True

    return False


def _describe_changes(emp, assigned, result=None):
    """Faqat matn ko'rinishida nima o'zgarishini hisoblaydi - DBga
    HECH NARSA yozmaydi. Bu funksiya har doim shu tarzda ishlaydi,
    apply_changes True yoki False bo'lishidan qat'iy nazar."""
    changes = []

    if result:
        new_first  = cyrillic_to_latin((result.get("name")       or "").strip())
        new_last   = cyrillic_to_latin((result.get("surname")    or "").strip())
        new_father = cyrillic_to_latin((result.get("partonimic") or "").strip())

        if (emp.first_name or "") != new_first:
            changes.append(f"Ism: {emp.first_name or '—'} → {new_first or '—'}")
        if (emp.last_name or "") != new_last:
            changes.append(f"Familiya: {emp.last_name or '—'} → {new_last or '—'}")
        if (emp.father_name or "") != new_father:
            changes.append(f"Otasining ismi: {emp.father_name or '—'} → {new_father or '—'}")

    if emp.organization_id != getattr(assigned["organization"], "id", None):
        old = str(emp.organization) if emp.organization else "—"
        new = str(assigned["organization"]) if assigned["organization"] else "—"
        changes.append(f"Tashkilot: {old} → {new}")

    if assigned.get("_dep_unresolved"):
        changes.append(
            f"Departament/Boshqarma BAZADA TOPILMADI "
            f"(Gateway kod={assigned.get('_dep_id')!r}, nomi={assigned.get('_dep_name')!r}) "
            f"- avval qo'lda yarating"
        )
    else:
        if emp.department_id != getattr(assigned["department"], "id", None):
            old = str(emp.department) if emp.department else "—"
            new = str(assigned["department"]) if assigned["department"] else "—"
            changes.append(f"Departament: {old} → {new}")

        if emp.directorate_id != getattr(assigned["directorate"], "id", None):
            old = str(emp.directorate) if emp.directorate else "—"
            new = str(assigned["directorate"]) if assigned["directorate"] else "—"
            changes.append(f"Boshqarma: {old} → {new}")

        if emp.division_id != getattr(assigned["division"], "id", None):
            old = str(emp.division) if emp.division else "—"
            new = str(assigned["division"]) if assigned["division"] else "—"
            changes.append(f"Bo'lim: {old} → {new}")

    if emp.rank_id != getattr(assigned.get("rank"), "id", None):
        old = str(emp.rank) if emp.rank else "—"
        new = str(assigned["rank"]) if assigned.get("rank") else "—"
        changes.append(f"Lavozim: {old} → {new}")

    return " | ".join(changes)


# =========================================================
# APPLY CHANGES
# =========================================================
# ⚠️ DIQQAT: Bu funksiya endi celery beat jadvalidan AVTOMATIK
# chaqirilmaydi. Faqat kelajakda admin paneldan "Qo'llash" degan
# tugma qo'shilsa va sync_all_employees(apply_changes=True) yoki
# shunga o'xshash alohida chaqiruv qilinsa ishlaydi. Bunda ham,
# agar department/directorate topilmagan (_dep_unresolved) bo'lsa,
# _sync_single_employee bu funksiyani chaqirmaydi - avval xabar
# qaytaradi ("qo'lda yarating").
def _apply_changes(emp, assigned, result=None):
    from .models import Rank

    if not assigned["rank"] and assigned.get("_position_id"):
        assigned["rank"], _ = Rank.objects.get_or_create(
            code=assigned["_position_id"],
            defaults={
                "name": assigned["_position"] or f"Lavozim-{assigned['_position_id']}"
            },
        )

    changes_str = _describe_changes(emp, assigned, result=result)

    if result:
        emp.first_name  = cyrillic_to_latin((result.get("name")       or "").strip())
        emp.last_name   = cyrillic_to_latin((result.get("surname")    or "").strip())
        emp.father_name = cyrillic_to_latin((result.get("partonimic") or "").strip())

    emp.organization = assigned["organization"]
    emp.department   = assigned["department"]
    emp.directorate  = assigned["directorate"]
    emp.division     = assigned["division"]
    emp.rank         = assigned.get("rank")
    emp.save()

    if emp.user and not emp.user.is_active:
        emp.user.is_active = True
        emp.user.save(update_fields=["is_active"])
        logger.info("PINFL %s qayta faollashtirildi", emp.pinfl)

    logger.info("PINFL %s yangilandi: %s", emp.pinfl, changes_str)
    return changes_str


# =========================================================
# BLOCK EMPLOYEE
# =========================================================
# ⚠️ DIQQAT: Bu funksiya endi celery beat jadvalidan AVTOMATIK
# chaqirilmaydi. Faqat apply_changes=True bilan alohida chaqirilganda
# ishlaydi (masalan kelajakda admin paneldan qo'lda tasdiqlash orqali).
def _block_employee(emp, pinfl):
    from .models import Technics

    with transaction.atomic():
        Technics.objects.filter(
            employee=emp,
            is_active=True
        ).update(employee=None)

        if emp.user and emp.user.is_active:
            emp.user.is_active = False
            emp.user.save(update_fields=["is_active"])

        emp.organization = None
        emp.department = None
        emp.directorate = None
        emp.division = None
        emp.region = None
        emp.rank = None
        emp.save(update_fields=["organization", "department", "directorate", "division", "region", "rank"])

    logger.info("PINFL %s bloklandi", pinfl)