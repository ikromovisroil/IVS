# main/tasks.py
import logging
import re
import time
from celery import shared_task
from django.db import transaction
from .models import *

logger = logging.getLogger(__name__)


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
                converted = converted.upper()  # HAMMASI katta bo'lsin
            result.append(converted)
        else:
            result.append(char)
    return ''.join(result)


def has_cyrillic(text: str) -> bool:
    return bool(re.search('[а-яА-ЯёЁғқҳўҷҒҚҲЎҶ]', text or ''))


# =========================================================
# CELERY TASK
# =========================================================
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_all_employees(self):
    from .models import Employee
    from core.models import SyncLog, SyncEmployeeLog

    employees = Employee.objects.select_related(
        "user", "organization", "department", "directorate", "division"
    ).filter(
        pinfl__isnull=False,
        user__isnull=False,
        user__is_active=True,
    ).exclude(pinfl="")

    total      = employees.count()
    updated    = 0
    blocked    = 0
    skipped    = 0
    errors     = 0
    start_time = time.time()

    sync_log = SyncLog.objects.create(total=total)

    logger.info("sync_all_employees boshlandi: %d xodim", total)

    for emp in employees.iterator(chunk_size=50):
        try:
            result, changes = _sync_single_employee(emp)

            if result == "blocked":
                blocked += 1
                SyncEmployeeLog.objects.create(
                    sync      = sync_log,
                    employee  = emp,
                    pinfl     = emp.pinfl,
                    full_name = emp.full_name,
                    result    = "blocked",
                    changes   = "Gatewayda ish joyi topilmadi",
                )
            elif result == "updated":
                updated += 1
                SyncEmployeeLog.objects.create(
                    sync      = sync_log,
                    employee  = emp,
                    pinfl     = emp.pinfl,
                    full_name = emp.full_name,
                    result    = "updated",
                    changes   = changes,
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
        updated  = updated,
        blocked  = blocked,
        skipped  = skipped,
        errors   = errors,
        duration = duration,
        status   = status,
    )

    logger.info(
        "sync tugadi | yangilandi=%d | bloklandi=%d | ozgarishsiz=%d | xato=%d | jami=%d | vaqt=%ds",
        updated, blocked, skipped, errors, total, duration
    )
    return {
        "updated":  updated,
        "blocked":  blocked,
        "skipped":  skipped,
        "errors":   errors,
        "total":    total,
        "duration": duration,
    }


# =========================================================
# SYNC SINGLE EMPLOYEE
# =========================================================
def _sync_single_employee(emp):
    from .gateway import GatewayClient

    pinfl = emp.pinfl

    try:
        gateway_data = GatewayClient.current_citizen(pinfl)
    except Exception as e:
        raise Exception(f"Gateway xatosi: {e}")

    result    = (gateway_data or {}).get("result") or {}
    positions = result.get("positions") or []

    if not positions:
        _block_employee(emp, pinfl)
        return "blocked", ""

    assigned = _resolve_position(pinfl, positions)

    if not assigned:
        _block_employee(emp, pinfl)
        return "blocked", ""

    if not _has_changed(emp, assigned):
        return "skipped", ""

    with transaction.atomic():
        changes = _apply_changes(emp, assigned, result)

    return "updated", changes


# =========================================================
# RESOLVE POSITION
# =========================================================
def _resolve_position(sso_pinfl, positions):
    from .models import Organization, Department, Directorate, Division, Rank

    for pos in positions:
        org_tin     = str(pos.get("org_tin")     or "").strip()
        dep_id      = str(pos.get("dep_id")      or "").strip()
        dep_name    = cyrillic_to_latin((pos.get("dep_name") or "").strip())  # ← konvertatsiya
        position_id = str(pos.get("position_id") or "").strip()
        position    = cyrillic_to_latin((pos.get("position") or "").strip())  # ← konvertatsiya

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

                # Topilmadi → Department yaratamiz
                region = getattr(organization, "region", None)
                if not region:
                    region = Region.objects.filter(id=3).first()

                department, created = Department.objects.get_or_create(
                    code=dep_id,
                    organization=organization,
                    region=region,
                    defaults={"name": dep_name or f"Bolim-{dep_id}"},  # ← allaqachon lotin
                )
                if created:
                    logger.info("Department yaratildi: %s", department)
                data["department"] = department
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

                # Topilmadi → Directorate yaratamiz
                directorate, created = Directorate.objects.get_or_create(
                    code=dep_id,
                    department=department,
                    defaults={"name": cyrillic_to_latin(dep_name or f"Boshqarma-{dep_id}")},
                )
                if created:
                    logger.info("Directorate yaratildi: %s", directorate)
                data["directorate"] = directorate
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
def _has_changed(emp, assigned):
    return (
        emp.organization_id != getattr(assigned["organization"], "id", None) or
        emp.department_id   != getattr(assigned["department"],   "id", None) or
        emp.directorate_id  != getattr(assigned["directorate"],  "id", None) or
        emp.division_id     != getattr(assigned["division"],     "id", None) or
        emp.rank_id         != getattr(assigned.get("rank"),     "id", None)
    )


# =========================================================
# APPLY CHANGES
# =========================================================
def _apply_changes(emp, assigned, result):
    from .models import Rank

    if not assigned["rank"] and assigned.get("_position_id"):
        assigned["rank"], _ = Rank.objects.get_or_create(
            code=assigned["_position_id"],
            defaults={
                "name": assigned["_position"] or f"Lavozim-{assigned['_position_id']}"  # ← allaqachon lotin
            },
        )

    changes = []

    if emp.organization_id != getattr(assigned["organization"], "id", None):
        old = str(emp.organization) if emp.organization else "—"
        new = str(assigned["organization"]) if assigned["organization"] else "—"
        changes.append(f"Tashkilot: {old} → {new}")

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

    # Kirill → Lotin konvertatsiya qilib saqlaymiz
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

    try:
        rol = emp.rol
        new_client = (emp.organization_id != 4)
        if rol.client != new_client:
            rol.client = new_client
            rol.save(update_fields=["client"])
    except Exception:
        pass

    changes_str = " | ".join(changes)
    logger.info("PINFL %s yangilandi: %s", emp.pinfl, changes_str)
    return changes_str


# =========================================================
# BLOCK EMPLOYEE
# =========================================================
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