import logging
from celery import shared_task
from django.db import transaction

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_all_employees(self):
    """
    Har kecha soat 00:30 da ishlaydigan task:
    - Gateway dan har bir xodimni tekshiradi
    - Ma'lumotlarni yangilaydi
    - Tashkilotda yo'q bo'lsa bloklaydi
    """
    from .models import Employee

    employees = Employee.objects.select_related(
        "user", "organization", "department", "directorate", "division", "rank"
    ).filter(
        pinfl__isnull=False,
        user__isnull=False,
    ).exclude(pinfl="")

    total   = employees.count()
    updated = 0
    blocked = 0
    errors  = 0

    logger.info("sync_all_employees boshlandi: %d xodim", total)

    for emp in employees.iterator(chunk_size=50):
        try:
            result = _sync_single_employee(emp)
            if result == "blocked":
                blocked += 1
            elif result == "updated":
                updated += 1
        except Exception as e:
            errors += 1
            logger.warning("PINFL %s sync xatosi: %s", emp.pinfl, e)

    logger.info(
        "sync_all_employees tugadi | yangilandi=%d | bloklandi=%d | xato=%d | jami=%d",
        updated, blocked, errors, total
    )
    return {"updated": updated, "blocked": blocked, "errors": errors, "total": total}


def _sync_single_employee(emp):
    """Bitta xodimni Gateway orqali tekshiradi va yangilaydi."""
    from .models import Rank
    from .gateway import GatewayClient
    from .sso_views import _resolve_position  # sso_views.py da

    pinfl = emp.pinfl

    # --- Gateway dan ma'lumot olish ---
    try:
        gateway_data = GatewayClient.current_citizen(pinfl)
    except Exception as e:
        raise Exception(f"Gateway xatosi: {e}")

    result    = (gateway_data or {}).get("result") or {}
    positions = result.get("positions") or []

    # --- Positions yo'q → bloklash ---
    if not positions:
        if emp.user and emp.user.is_active:
            emp.user.is_active = False
            emp.user.save(update_fields=["is_active"])
            logger.info("PINFL %s bloklandi (positions yo'q)", pinfl)
        return "blocked"

    # --- Pozitsiyani aniqlash ---
    assigned = _resolve_position(pinfl, positions)
    if not assigned:
        logger.warning("PINFL %s uchun pozitsiya aniqlanmadi", pinfl)
        return "skipped"

    with transaction.atomic():
        # Yangi ma'lumotlar
        new_first  = (result.get("name")       or "").strip()
        new_last   = (result.get("surname")    or "").strip()
        new_father = (result.get("partonimic") or "").strip()

        # O'zgarish bor-yo'qligini tekshirish
        changed = (
            emp.first_name      != new_first  or
            emp.last_name       != new_last   or
            emp.father_name     != new_father or
            emp.organization_id != getattr(assigned["organization"], "id", None) or
            emp.department_id   != getattr(assigned["department"],   "id", None) or
            emp.directorate_id  != getattr(assigned["directorate"],  "id", None) or
            emp.division_id     != getattr(assigned["division"],     "id", None)
        )

        if not changed:
            return "skipped"  # Hech narsa o'zgarmagan

        # Rank yangilash
        if not assigned["rank"] and assigned.get("_position_id"):
            assigned["rank"], _ = Rank.objects.get_or_create(
                code=assigned["_position_id"],
                defaults={
                    "name": assigned["_position"] or f"Lavozim-{assigned['_position_id']}"
                },
            )

        # Employee yangilash
        emp.first_name   = new_first
        emp.last_name    = new_last
        emp.father_name  = new_father
        emp.organization = assigned["organization"]
        emp.department   = assigned["department"]
        emp.directorate  = assigned["directorate"]
        emp.division     = assigned["division"]
        emp.rank         = assigned.get("rank")
        emp.save()

        # Bloklangan bo'lsa qayta faollashtirish
        if emp.user and not emp.user.is_active:
            emp.user.is_active = True
            emp.user.save(update_fields=["is_active"])
            logger.info("PINFL %s qayta faollashtirildi", pinfl)

        # Rol yangilash
        try:
            rol = emp.rol
            new_client = (emp.organization_id != 4)
            if rol.client != new_client:
                rol.client = new_client
                rol.save(update_fields=["client"])
        except Exception:
            pass

        logger.info("PINFL %s yangilandi", pinfl)
        return "updated"