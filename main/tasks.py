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


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_all_employees(self):
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

        logger.info("sync_all_employees boshlandi (faqat info rejimida): %d xodim", total)

        for emp in employees.iterator(chunk_size=50):
            try:
                result, changes = _check_single_employee(emp)

                if result == "would_block":
                    would_block += 1
                    SyncEmployeeLog.objects.create(
                        sync      = sync_log,
                        employee  = emp,
                        pinfl     = emp.pinfl,
                        full_name = emp.full_name,
                        result    = "blocked",
                        changes   = "DIQQAT: Gatewayda ish joyi topilmadi. Xodim AVTOMATIK bloklanmadi - qo'lda ko'rib chiqing va kerak bo'lsa qo'lda bloklang.",
                    )
                elif result == "changed":
                    changed += 1
                    SyncEmployeeLog.objects.create(
                        sync      = sync_log,
                        employee  = emp,
                        pinfl     = emp.pinfl,
                        full_name = emp.full_name,
                        result    = "updated",
                        changes   = f"DIQQAT: Farq aniqlandi, AVTOMATIK o'zgartirilmadi (faqat ma'lumot uchun): {changes}",
                    )
                else:
                    skipped += 1

            except Exception as e:
                errors += 1
                logger.warning("PINFL %s tekshiruv xatosi: %s", emp.pinfl, e)
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
            "sync tugadi (faqat info) | aniqlangan_farq=%d | bloklanishi_kerak=%d | ozgarishsiz=%d | xato=%d | jami=%d | vaqt=%ds",
            changed, would_block, skipped, errors, total, duration
        )
        return {
            "changed":     changed,
            "would_block": would_block,
            "skipped":     skipped,
            "errors":      errors,
            "total":       total,
            "duration":    duration,
        }

    finally:
        cache.delete(SYNC_LOCK_KEY)


# =========================================================
# CHECK SINGLE EMPLOYEE (read-only, hech narsa saqlamaydi)
# =========================================================
def _check_single_employee(emp):
    from .gateway import GatewayClient

    pinfl = emp.pinfl

    try:
        gateway_data = GatewayClient.current_citizen(pinfl)
    except Exception as e:
        raise Exception(f"Gateway xatosi: {e}")

    result = (gateway_data or {}).get("result") or {}
    positions = result.get("positions") or []

    if not positions:
        return "would_block", ""

    assigned = _resolve_position(pinfl, positions)

    if not assigned:
        return "would_block", ""

    if not _has_changed(emp, assigned, result=result):
        return "skipped", ""

    changes = _describe_changes(emp, assigned, result=result)

    # FAQAT TEKSHIRADI VA XABAR BERADI - BAZAGA HECH NARSA YOZILMAYDI
    return "changed", changes


def _get_default_region():
    return Region.objects.filter(id=DEFAULT_REGION_ID).first()


def _resolve_position(sso_pinfl, positions):

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

                # Department topilmadi - HECH NARSA YARATMAYMIZ,
                # faqat "topilmadi" deb belgilaymiz
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

                # Directorate topilmadi - HECH NARSA YARATMAYMIZ,
                # faqat "topilmadi" deb belgilaymiz
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