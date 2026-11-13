"""
"Hujjatlar" (reyestr) sahifasi ko'lami — veb (api/spa/people.py) va mobil (api/views.py: DeedRegistryViewSet) uchun bitta qoida.

* Tanlov (select) ro'yxati: `all_organization` bo'lsa hamma tashkilot, aks holda faqat xodimning o'z tashkiloti;
  `all_region` bo'lsa hamma hudud, aks holda faqat o'z hududi.
* Hujjatlar: `all_organization` bo'lsa hammasi, aks holda faqat imzolovchi (`sender`), qabul qiluvchi (`receiver`)
  yoki kelishuvchi (`DeedConsent`) xodim tashkilotidan bo'lgan hujjatlar.
Superuser — hammasi.
"""
from django.db.models import Exists, OuterRef, Q

from main.models import DeedConsent, Organization, Region


def _employee(user):
    return getattr(user, "employee", None)


def sees_all_organizations(user) -> bool:
    return bool(user.is_superuser or user.has_perm("main.all_organization"))


def sees_all_regions(user) -> bool:
    return bool(user.is_superuser or user.has_perm("main.all_region"))


def allowed_organizations(user):
    if sees_all_organizations(user):
        return Organization.objects.all()
    employee = _employee(user)
    if not employee or not employee.organization_id:
        return Organization.objects.none()
    return Organization.objects.filter(pk=employee.organization_id)


def allowed_regions(user):
    if sees_all_regions(user):
        return Region.objects.all()
    employee = _employee(user)
    if not employee or not employee.region_id:
        return Region.objects.none()
    return Region.objects.filter(pk=employee.region_id)


def scope_deeds(qs, user):
    """Hujjatlar to'plamini imzolovchi / kelishuvchisi xodim tashkilotidan bo'lgan hujjatlar bilan cheklaydi."""
    if sees_all_organizations(user):
        return qs
    employee = _employee(user)
    if not employee or not employee.organization_id:
        return qs.none()
    org = employee.organization_id
    consent = DeedConsent.objects.filter(deed_id=OuterRef("pk"), employee__organization_id=org)
    return qs.filter(Q(sender__organization_id=org) | Q(receiver__organization_id=org) | Exists(consent))
