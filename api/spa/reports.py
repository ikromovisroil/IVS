"""
"Hisobotlar" bo'limi (frontend/src/pages/reports/) uchun endpointlar: /api/v1/spa/reports/...

Eski sahifalar (templates/main/{document,svod,reestr,akt,service}.html) hujjat matnini brauzerda yig'adi:
filtrlar → main/ajax_views.py dagi AJAX funksiyalar (materiallar, texnikalar, xodimlar) → TinyMCE → PDF yoki
"Imzolashga yuborish" (main/views.py: document_post, svod_post, reest_post, akt_post, service_post).

Bu modul hisob-kitobni TAKRORLAMAYDI: AJAX va POST endpointlari main/ dagi o'sha view funksiyalarini to'g'ridan-to'g'ri
chaqiradi (ruxsat, filtrlar va Deed yaratish o'sha yerda). Faqat sahifa konteksti (ro'yxatlar, ruxsatlar) va
POST natijasini (redirect + django messages) JSON ko'rinishiga keltirish shu yerda.
"""

from django.contrib import messages as dj_messages
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from api.spa.people import _MemoryMessages
from main import ajax_views, views as main_views
from main.models import Employee, Organization, Region

KINDS = ("document", "svod", "reestr", "akt", "service")


# ─── Ruxsatlar: main/views.py dagi *_get funksiyalar va templates/base.html menyusi bilan bir xil ───

def _employee(user):
    return getattr(user, "employee", None)


def _is_worker(employee):
    return bool(employee and employee.organization and employee.organization.type == "worker")


def allowed_reports(user):
    """Qaysi hisobot sahifalari ochiladi (menyu sharti + view ichidagi tekshiruv)."""
    emp = _employee(user)
    if not emp:
        return {k: False for k in KINDS}
    worker = _is_worker(emp) or user.is_superuser      # superuser (admin) tashkilotidan qat'i nazar, menyudagidek
    svod = user.has_perm("main.shop_employee") or user.has_perm("main.report_employee")
    # Hisobotlar bo'limi faqat xizmat ko'rsatuvchi (worker, ATM/IVS) tashkilot xodimlariga: eski menyu ("Hisobotlar" butunlay
    # worker sharti ichida) bilan bir xil. Mijoz tashkilot xodimiga shu ruxsatlar berilgan bo'lsa ham ko'rinmaydi.
    return {
        # document_get: worker tashkilot + Employee.can_make_document (kamida bitta shartnoma)
        "document": worker and emp.can_make_document,
        # svod_get / reestr_get: worker tashkilot + shop_employee yoki report_employee
        "svod": worker and svod,
        "reestr": worker and svod,
        # akt_get: worker tashkilot + main.change_order
        "akt": worker and user.has_perm("main.change_order"),
        # service_get: main.material_service + worker tashkilot
        "service": worker and user.has_perm("main.material_service"),
    }


def _check(user, kind):
    if kind not in KINDS:
        raise NotFound()
    if not allowed_reports(user)[kind]:
        raise PermissionDenied("Ruxsat yo'q")
    return _employee(user)


# ─── Serializatsiya ───

def _emp(e):
    return {
        "id": e.id,
        "full_name": e.full_name,
        "rank": e.rank.name if e.rank_id else "",
        "organization_id": e.organization_id,
        "region_id": e.region_id,
    }


def _emps(qs):
    return [_emp(e) for e in qs.select_related("rank", "user")]


def _orgs(qs):
    return list(qs.only("id", "name", "contract").order_by("id").values("id", "name", "contract"))


def _regions(user, emp):
    qs = Region.objects.only("id", "name").order_by("id")
    if not user.has_perm("main.all_region"):
        qs = qs.filter(id=emp.region_id)
    return list(qs.values("id", "name"))


class ReportsMetaView(APIView):
    """GET /spa/reports/ — ko'rinadigan hisobotlar va joriy xodim (menyu, tablar, /reports yo'naltirishi uchun)."""

    def get(self, request):
        emp = _employee(request.user)
        return Response({
            "reports": allowed_reports(request.user),
            "has_full_region": request.user.has_perm("main.all_region"),
            "employee": None if not emp else {
                "id": emp.id,
                "full_name": emp.full_name,
                "rank": emp.rank.name if emp.rank_id else "",
                "region_id": emp.region_id,
                "region_name": emp.region.name if emp.region_id else "",
                "organization_id": emp.organization_id,
                "organization_name": emp.organization.name if emp.organization_id else "",
            },
        })


class ReportFormView(APIView):
    """GET /spa/reports/<kind>/form/ — eski *_get view kontekstidagi ro'yxatlar (tashkilot, hudud, imzolovchilar)."""

    def get(self, request, kind):
        emp = _check(request.user, kind)
        user = request.user
        data = {
            "has_full_region": user.has_perm("main.all_region"),
            "user_region": emp.region_id,
        }

        if kind == "document":
            data["organizations"] = _orgs(Organization.objects.all())
            data["regions"] = _regions(user, emp)
            # document_get: emp_bos_sender
            data["senders"] = _emps(Employee.objects.filter(Q(department_id=283) | Q(department_id=298, region=emp.region)))
        elif kind == "svod":
            # Xizmat ko'rsatuvchi (ATM) tashkilot Svodga kirmaydi
            data["organizations"] = _orgs(Organization.objects.exclude(type="worker"))
            data["regions"] = _regions(user, emp)
            data["senders"] = _emps(Employee.objects.filter(department_id=283))
            data["agreements"] = _emps(Employee.objects.filter(organization_id=4))
        elif kind == "reestr":
            data["organizations"] = _orgs(Organization.objects.all())
            data["regions"] = _regions(user, emp)
            own = _emps(Employee.objects.filter(organization_id=emp.organization_id))
            data["senders"] = own
            data["agreements"] = own
        elif kind == "akt":
            data["organizations"] = _orgs(Organization.objects.all())
            data["regions"] = _regions(user, emp)
        elif kind == "service":
            workers = _emps(Employee.objects.filter(organization__type="worker"))
            data["senders"] = workers
            data["agreements"] = workers
            data["my_org"] = {"id": emp.organization_id, "name": emp.organization.name} if emp.organization_id else None
            data["my_region"] = {"id": emp.region_id, "name": emp.region.name} if emp.region_id else None
            today = timezone.localdate()
            data["report_year"] = today.year
            data["report_quarter"] = main_views.quarter_roman(today.month)
        return Response(data)


# ─── Eski AJAX funksiyalariga o'tkazgich (natija o'zgarishsiz qaytadi) ───

AJAX = {
    "departments": ajax_views.ajax_load_departments,
    "signatories": ajax_views.ajax_dep_signatory,
    "negotiators": ajax_views.ajax_dep_negotiator,
    "agreements": ajax_views.ajax_agreements_employees,
    "document-preview": ajax_views.ajax_document_preview,
    "akt-materials": ajax_views.ajax_akt_materials,
    "svod-materials": ajax_views.ajax_svod_materials,
    "reestr-materials": ajax_views.ajax_reestr_materials,
    "service-materials": ajax_views.ajax_service_materials,
}


# Ma'lumot endpointi qaysi hisobot ruxsatini talab qiladi (ro'yxat endpointlari — kamida bitta hisobot ochiq bo'lsa)
DATA_KIND = {
    "document-preview": "document",
    "svod-materials": "svod",
    "reestr-materials": "reestr",
    "akt-materials": "akt",
    "service-materials": "service",
}


class ReportDataView(APIView):
    """GET /spa/reports/data/<name>/?... — main/ajax_views.py dagi funksiyaning javobi (JSON) aynan qaytadi."""

    def get(self, request, name):
        fn = AJAX.get(name)
        if fn is None:
            raise NotFound()
        kind = DATA_KIND.get(name)
        if kind:
            _check(request.user, kind)
        elif not any(allowed_reports(request.user).values()):
            raise PermissionDenied("Ruxsat yo'q")
        return fn(request._request)


class ReportPdfView(APIView):
    """POST /spa/reports/pdf/ (body_html, orientation, filename) — main.ajax_views.download_pdf (PDF fayl)."""

    def post(self, request):
        return ajax_views.download_pdf(request._request)


SUBMIT = {
    "document": main_views.document_post,
    "svod": main_views.svod_post,
    "reestr": main_views.reest_post,
    "akt": main_views.akt_post,
    "service": main_views.service_post,
}


class ReportSubmitView(APIView):
    """
    POST /spa/reports/<kind>/submit/ (multipart: body_encoded, sender, receiver, agreements[], message, attachments, ...)
    — main/views.py dagi *_post funksiyasi. U xatoni django messages + redirect bilan bildiradi; shu yerda JSON ga
    aylantiriladi: muvaffaqiyat (redirect "contact_user" ga) → 201, aks holda → 400 {"detail": xabar}.
    """

    def post(self, request, kind):
        _check(request.user, kind)
        raw = request._request
        # Faqat shu view qo'shgan xabarlar: sessiyadagi eski (o'qilmagan) xabarlar natijaga aralashmaydi va o'chmaydi
        storage = _MemoryMessages(raw)
        raw._messages = storage
        response = SUBMIT[kind](raw)

        texts = [(m.level, str(m.message)) for m in storage._queued_messages]
        errors = [t for lvl, t in texts if lvl >= dj_messages.ERROR]
        success = [t for lvl, t in texts if lvl == dj_messages.SUCCESS]

        ok = isinstance(response, HttpResponseRedirect) and response.url == reverse("contact_user") and not errors
        if ok:
            return Response({"detail": success[0] if success else "Imzolashga yuborildi"}, status=201)
        return Response({"detail": errors[0] if errors else "Hujjat yuborilmadi"}, status=400)


urlpatterns = [
    path("", ReportsMetaView.as_view()),
    path("pdf/", ReportPdfView.as_view()),
    path("data/<str:name>/", ReportDataView.as_view()),
    path("<str:kind>/form/", ReportFormView.as_view()),
    path("<str:kind>/submit/", ReportSubmitView.as_view()),
]
