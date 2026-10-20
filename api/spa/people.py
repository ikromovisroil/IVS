"""
"Xodimlar", "Profil", "Hujjatlar" va "Bildirishnomalar" bo'limlari (frontend/src/pages/people) uchun qo'shimcha endpointlar.

Mavjud /api/v1/ yetarli bo'lgan joyda (xodimlar ro'yxati/CRUD/ruxsatlar, tuzilma, lavozimlar, bildirishnomalar,
xodimlar eksporti) shu endpointlar ishlatiladi. Bu yerda faqat yetishmaganlari:

  GET  profile/                          — joriy foydalanuvchi profili (main/views.py: profil)
  POST employees/gateway-create/         — PINFL bo'yicha Gateway orqali xodim qo'shish (main/views.py: employe_create)
  GET  files/filters/                    — "Hujjatlar" sahifasi filtrlari: barcha tashkilot va hududlar (files)
  GET  files/                            — "Hujjatlar" qidiruvi (main/views.py: files)
  POST files/<id>/toggle-user-edit/      — yaratuvchiga tahrirlash ruxsati (main/ajax_views.py: toggle_user_edit)
  GET  files/<id>/attachments/           — ilovalarni yuklab olish (main/views.py: deed_attachments)

Yozish amallari eski Django view'larini to'g'ridan-to'g'ri chaqiradi (`_call_legacy`): ruxsat va biznes-mantiq
bitta joyda qoladi, view'ning `messages` xabari JSON javobga aylantiriladi.
"""
import copy
import json
import logging

from django.contrib import messages as dj_messages
from django.contrib.messages.storage.base import BaseStorage
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.db.models import Prefetch, Q
from django.http import HttpResponseRedirect, QueryDict
from django.urls import path
from django.utils.datastructures import MultiValueDict
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from main.models import Deed, DeedConsent, Organization, Region

from ..pagination import StandardResultsPagination

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- yordamchilar

class _MemoryMessages(BaseStorage):
    """Eski view'ning messages.success/info xabarlarini sessiyaga emas, xotiraga yozadi."""

    def _get(self, *args, **kwargs):
        return [], True

    def _store(self, messages, response, *args, **kwargs):
        return []


def _call_legacy(request, view, data=None, method="POST", **kwargs):
    """
    Eski (sayt) view'ini DRF so'rovi bilan chaqiradi. CSRF DRF SessionAuthentication'da tekshirilgan.
    Qaytaradi: (javob, [(daraja, matn), ...]).
    """
    req = copy.copy(request._request)
    req.method = method
    post = QueryDict(mutable=True)
    for key, value in (data or {}).items():
        if isinstance(value, (list, tuple)):
            post.setlist(key, [str(v) for v in value])
        elif value is not None:
            post[key] = str(value)
    req._post = post
    req._files = MultiValueDict()
    req.csrf_processing_done = True
    req.user = request.user   # JWT bilan kirilganda ham
    req.META = {**req.META}
    req.META.pop("HTTP_REFERER", None)
    storage = _MemoryMessages(req)
    req._messages = storage
    response = view(req, **kwargs)
    return response, [(m.level, str(m.message)) for m in storage._queued_messages]


def _messages_response(msgs, ok_status=200):
    """success → ok_status, aks holda (info/xato) → 400."""
    if not msgs:
        return Response({"detail": "Amal bajarilmadi."}, status=400)
    level, text = msgs[-1]
    return Response({"detail": text}, status=ok_status if level == dj_messages.SUCCESS else 400)


def _employee(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")
    return employee


def _name(obj):
    return getattr(obj, "name", None) if obj else None


def _dt(value):
    return value.isoformat() if value else None


# --------------------------------------------------------------------------- profil

class ProfileView(APIView):
    """Joriy foydalanuvchi profili: saytdagi "Profil" sahifasidagi ma'lumotlar."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        e = _employee(request)
        return Response({
            "id": e.id,
            "username": request.user.username,
            "full_name": e.full_name,
            "last_name": e.last_name,
            "first_name": e.first_name,
            "father_name": e.father_name,
            "rank_name": _name(e.rank),
            "organization_name": _name(e.organization),
            "organization_type": e.organization.type if e.organization_id else None,
            "department_name": _name(e.department),
            "directorate_name": _name(e.directorate),
            "division_name": _name(e.division),
            "region_name": _name(e.region),
            "phone": e.phone,
            "email": request.user.email or None,
            "pinfl": e.pinfl,
            "date_joined": _dt(request.user.date_joined),
            "last_login": _dt(request.user.last_login),
        })


# --------------------------------------------------------------------------- xodim qo'shish (Gateway)

class EmployeeGatewayCreateView(APIView):
    """PINFL bo'yicha Gateway'dan F.I.O va ish joyini olib xodim yaratadi ('add_employee'; qoidalar employe_create da)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from main.views import employe_create

        pinfl = str(request.data.get("pinfl") or "").strip()
        try:
            _, msgs = _call_legacy(request, employe_create, {"pinfl": pinfl})
        except DjangoPermissionDenied:
            raise
        except Exception:  # noqa: BLE001 — Gateway sozlanmagan/ishlamayotgan bo'lsa (masalan, GATEWAY_BASE_URL yo'q)
            logger.exception("Gateway orqali xodim qo'shishda xatolik (pinfl=%s)", pinfl)
            return Response({"detail": "Tashqi tizim (Gateway) bilan aloqada xatolik yuz berdi. "
                                       "Birozdan keyin qayta urinib ko'ring."}, status=502)
        return _messages_response(msgs, ok_status=201)


# --------------------------------------------------------------------------- hujjatlar

DEED_STATUSES = dict(Deed._meta.get_field("status").choices)


def _person(emp):
    if not emp:
        return None
    return {
        "id": emp.id,
        "full_name": emp.full_name,
        "organization_name": _name(emp.organization),
        "rank_name": _name(emp.rank),
    }


def _overall(d):
    """Saytdagi "Holati" ustuni: rad etilgan / tasdiqlangan / kutilmoqda."""
    if d.receiver_id:
        if "rejected" in (d.status_sender, d.status_receiver):
            return "rejected"
        if d.status_sender == "approved" and d.status_receiver == "approved":
            return "approved"
        return "pending"
    if d.status_sender == "rejected":
        return "rejected"
    if d.status_sender == "approved":
        return "approved"
    return "pending"


def _deed_json(d):
    try:
        file_url = d.file.url if d.file else None
    except ValueError:
        file_url = None
    return {
        "id": d.id,
        "code": d.code,
        "status": d.status,
        "status_display": DEED_STATUSES.get(d.status, d.status),
        "organization_name": _name(d.organization),
        # Hudud filtri (user_region) bilan bir xil: yaratilgan paytdagi hudud; eski yozuvlarda — muallifning hozirgi hududi
        "region_name": _name(d.user_region) if d.user_region_id else (_name(d.user.region) if d.user_id else None),
        "date_creat": _dt(d.date_creat),
        "file_url": file_url,
        "attachments_count": len(d.deedfiles_set.all()),
        "user_edit": d.user_edit,
        "overall": _overall(d),
        "user": _person(d.user),
        "message_user": d.message_user,
        "sender": _person(d.sender),
        "status_sender": d.status_sender,
        "date_sender": _dt(d.date_sender),
        "message_sender": d.message_sender,
        "receiver": _person(d.receiver),
        "status_receiver": d.status_receiver if d.receiver_id else None,
        "date_receiver": _dt(d.date_receiver),
        "message_receiver": d.message_receiver,
        "consents": [
            {
                "id": c.id,
                "employee": _person(c.employee),
                "status": c.status,
                "date_edit": _dt(c.date_edit) if c.status in ("approved", "rejected") else None,
                "message": c.message,
            }
            for c in d.deedconsent_set.all()
        ],
    }


class FilesFiltersView(APIView):
    """Saytdagi "Hujjatlar" sahifasi kabi: barcha tashkilotlar va hududlar (sahifa hamma xodimga ochiq)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _employee(request)
        return Response({
            "organizations": list(Organization.objects.order_by("id").values("id", "name")),
            "regions": list(Region.objects.order_by("id").values("id", "name")),
            "statuses": [{"value": k, "label": v} for k, v in DEED_STATUSES.items()],
        })


class FilesView(APIView):
    """
    "Hujjatlar" qidiruvi — main/views.py: files() bilan bir xil: xodim profili bo'lgan har kim; hech bir filtr
    berilmasa bo'sh ro'yxat. Filtrlar: name (F.I.O / kod / ariza raqami), organization, region, status, date1, date2.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _employee(request)
        p = request.query_params
        name = (p.get("name") or "").strip()[:120]
        date1 = (p.get("date1") or "").strip()
        date2 = (p.get("date2") or "").strip()
        status = (p.get("status") or "").strip()
        region_id = (p.get("region") or "").strip()
        org_id = (p.get("organization") or "").strip()

        qs = Deed.objects.none()
        if name or date1 or date2 or status or region_id or org_id:
            qs = (
                Deed.objects.distinct()
                .select_related(
                    "organization", "user", "user__region", "user__organization", "user__rank", "user_region",
                    "sender", "sender__organization", "sender__rank",
                    "receiver", "receiver__organization", "receiver__rank",
                )
                .prefetch_related(
                    Prefetch("deedconsent_set", queryset=DeedConsent.objects.select_related(
                        "employee", "employee__organization", "employee__rank").order_by("id")),
                    "deedfiles_set",
                )
                .order_by("-id")
            )
            if name:
                person = Q()
                for term in name.split():
                    person &= (
                        Q(sender__last_name__icontains=term) | Q(sender__first_name__icontains=term)
                        | Q(sender__father_name__icontains=term)
                        | Q(receiver__last_name__icontains=term) | Q(receiver__first_name__icontains=term)
                        | Q(receiver__father_name__icontains=term)
                        | Q(user__last_name__icontains=term) | Q(user__first_name__icontains=term)
                        | Q(user__father_name__icontains=term)
                    )
                flt = Q(code__icontains=name) | person
                flt |= Q(orders__id=int(name)) if name.isdigit() else Q(orders__id__icontains=name)
                qs = qs.filter(flt)
            if org_id:
                qs = qs.filter(organization_id=int(org_id) if org_id.isdigit() else None)
            if region_id:
                qs = qs.filter(user_region_id=int(region_id) if region_id.isdigit() else None)
            if status:
                qs = qs.filter(status=status)
            for value, lookup in ((date1, "date_creat__date__gte"), (date2, "date_creat__date__lte")):
                if value:
                    try:
                        qs = qs.filter(**{lookup: value})
                    except Exception:  # noqa: BLE001 — noto'g'ri sana — saytdagidek e'tiborsiz
                        pass

        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response([_deed_json(d) for d in page])


class FileToggleUserEditView(APIView):
    """Yaratuvchiga hujjatni tahrirlash ruxsatini yoqish/o'chirish ('change_deed'; saytdagi toggle_user_edit)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        from main.ajax_views import toggle_user_edit

        response, _ = _call_legacy(request, toggle_user_edit, {}, deed_id=pk)
        data = json.loads(response.content or b"{}")
        return Response(data, status=response.status_code)


class FileAttachmentsView(APIView):
    """Hujjat ilovalari: bitta bo'lsa o'zi, bir nechta bo'lsa ZIP (saytdagi deed_attachments)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        from main.views import deed_attachments

        response, msgs = _call_legacy(request, deed_attachments, method="GET", pk=pk)
        if isinstance(response, HttpResponseRedirect):
            return Response({"detail": msgs[-1][1] if msgs else "Ilova fayllar topilmadi"}, status=404)
        return response


urlpatterns = [
    path("profile/", ProfileView.as_view(), name="spa_people_profile"),
    path("employees/gateway-create/", EmployeeGatewayCreateView.as_view(), name="spa_people_gateway_create"),
    path("files/filters/", FilesFiltersView.as_view(), name="spa_people_files_filters"),
    path("files/", FilesView.as_view(), name="spa_people_files"),
    path("files/<int:pk>/toggle-user-edit/", FileToggleUserEditView.as_view(), name="spa_people_file_toggle"),
    path("files/<int:pk>/attachments/", FileAttachmentsView.as_view(), name="spa_people_file_attachments"),
]
