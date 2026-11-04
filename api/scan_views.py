"""
QR skaner (mobil ilovalar): POST /api/v1/scan/ {"text": "<QR matni>"}.

Ilova kamera bilan o'qigan matnni yuboradi, server uni tanib, tegishli ma'lumotni qaytaradi:

* texnika QR'i  (`<SITE_BASE_URL>/technics/<id>/`)            -> {"type": "technics", ...}
* hujjat QR'i   (`<SITE_BASE_URL>/deed/status/<kod>/<id>/`)   -> {"type": "deed", ...}

Ma'lumot saytdagi QR sahifalari (main/views.py: technics_detail, deed_status) bilan bir xil. Tahrirlash va biriktirish
huquqi `can_edit` bayrog'ida: ilova tugmalarni shu bilan ko'rsatadi, amallarning o'zi mavjud /technics/ endpointlari orqali
(PATCH, assign, unassign) bajariladi va u yerda ruxsat qayta tekshiriladi.
"""
import re
from urllib.parse import urlparse

from django.conf import settings
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from main.models import Deed, Technics

from .serializers import TechnicsSerializer
from .spa.warehouse import _with_devices, technics_card
from .views import TechnicsViewSet, _visible_deeds

TECHNICS_PATH = re.compile(r"^/technics/(\d+)/?$")
DEED_PATH = re.compile(r"^/deed/status/([A-Za-z0-9]+)/(\d+)/?$")
UNKNOWN = "Bu QR kod IMV tizimiga tegishli emas"


class ScanThrottle(UserRateThrottle):
    scope = "scan"

    def get_rate(self):
        return "60/min"       # hujjat kodini taxmin qilib topishga urinishni cheklaydi


class ScanSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=2000)


def _allowed_hosts():
    hosts = set()
    base = urlparse(getattr(settings, "SITE_BASE_URL", "") or "").netloc.lower()
    if base:
        hosts.add(base)
    for host in settings.ALLOWED_HOSTS:
        if host and host != "*" and not host.startswith("."):
            hosts.add(host.lower())
    return hosts


def _parse(text):
    """QR matnidan ('technics', (id,)) yoki ('deed', (kod, id)); tanilmasa None. Faqat o'z domenimizdagi havola qabul qilinadi."""
    parsed = urlparse(text.strip())
    if parsed.scheme or parsed.netloc:
        if parsed.scheme not in ("http", "https") or parsed.netloc.lower() not in _allowed_hosts():
            return None
    match = TECHNICS_PATH.match(parsed.path)
    if match:
        return "technics", (int(match.group(1)),)
    match = DEED_PATH.match(parsed.path)
    if match:
        return "deed", (match.group(1), int(match.group(2)))
    return None


def _person(employee):
    if not employee:
        return None
    return {
        "full_name": employee.full_name,
        "organization_name": employee.organization.name if employee.organization_id else None,
    }


class ScanView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScanThrottle]

    def post(self, request):
        ser = ScanSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        parsed = _parse(ser.validated_data["text"])
        if parsed is None:
            return Response({"detail": UNKNOWN, "type": "unknown"}, status=status.HTTP_400_BAD_REQUEST)
        kind, args = parsed
        return self._technics(request, *args) if kind == "technics" else self._deed(request, *args)

    def _technics(self, request, pk):
        tex = _with_devices(Technics.objects.select_related("category", "employee")).filter(pk=pk, is_active=True).first()
        if tex is None:
            return Response({"detail": "Texnika topilmadi", "type": "technics"}, status=status.HTTP_404_NOT_FOUND)

        # Tahrirlash/biriktirish/bo'shatish: 'change_technics' va texnika tashkilot/hudud doirasida (TechnicsViewSet bilan bir xil)
        can_edit = False
        detail = None
        if request.user.has_perm("main.change_technics"):
            view = TechnicsViewSet()
            view.request, view.action, view.kwargs, view.format_kwarg = request, "partial_update", {}, None
            editable = view.get_queryset().filter(pk=pk).first()
            if editable is not None:
                can_edit = True
                detail = TechnicsSerializer(editable, context={"request": request}).data
        return Response({
            "type": "technics",
            "technics": {**technics_card(tex), "employee": tex.employee_id},
            "can_edit": can_edit,
            "detail": detail,       # tahrirlash oynasini to'ldirish uchun (faqat can_edit bo'lsa)
        })

    def _deed(self, request, code, pk):
        deed = (
            Deed.objects.select_related("user__organization", "sender__organization", "receiver__organization")
            .prefetch_related("deedconsent_set__employee__organization")
            .filter(pk=pk, code=code).first()
        )
        if deed is None:
            return Response({"detail": "Hujjat topilmadi", "type": "deed"}, status=status.HTTP_404_NOT_FOUND)

        # Hujjat PDF'i va to'liq ochish faqat ishtirokchiga; boshqalar faqat holatni ko'radi (QR orqali tekshirish)
        can_open = _visible_deeds(request.user).filter(pk=deed.pk).exists()
        signers = [{"role": "sender", "person": _person(deed.sender), "status": deed.status_sender,
                    "status_display": deed.get_status_sender_display(), "date": deed.date_sender,
                    "message": deed.message_sender}]
        if deed.receiver_id:
            signers.append({"role": "receiver", "person": _person(deed.receiver), "status": deed.status_receiver,
                            "status_display": deed.get_status_receiver_display(), "date": deed.date_receiver,
                            "message": deed.message_receiver})
        consents = [{
            "person": _person(c.employee), "status": c.status, "status_display": c.get_status_display(),
            "date": c.date_edit if c.status in ("approved", "rejected") else None, "message": c.message,
        } for c in deed.deedconsent_set.all()]
        return Response({
            "type": "deed",
            "deed": {
                "id": deed.id,
                "code": deed.code,
                "kind": deed.status,
                "kind_display": deed.get_status_display(),
                "created_by": _person(deed.user),
                "date_creat": deed.date_creat,
                "message_user": deed.message_user,
                "signers": signers,
                "consents": consents,
                "file": request.build_absolute_uri(deed.file.url) if can_open and deed.file else None,
            },
            "can_open": can_open,       # true bo'lsa ilova GET /deeds/{id}/ bilan to'liq ochadi (imzolash, kelishish)
        })
