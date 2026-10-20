"""
"Xabarlar" bo'limi (React: frontend/src/pages/messages/) uchun qo'shimcha endpointlar — /api/v1/spa/messages/.

Mavjud /api/v1/deeds/ (yaratish, tahrirlash, rad etish, kelishuvchilar) va /api/v1/deed-consents/ (kelishish)
ishlatiladi. Bu yerda faqat yetishmaganlari:

* deeds/?box=...           — eski sahifalardagi ro'yxatlar (Imzolashga yuborish / Imzolash uchun / Kelishish uchun
                             va ularning arxivi) — /api/v1/deeds/?role=... bilan bir xil queryset, lekin jadval va
                             "Dalolatnoma holati" oynasi uchun qo'shimcha maydonlar (hudud, tashkilot, lavozim).
* deeds/<id>/              — bitta hujjat (xuddi shu maydonlar bilan).
* deeds/<id>/edit-options/ — deed_edit sahifasidagi tanlash ro'yxatlari.
* deeds/<id>/approve/      — E-IMZO bilan tasdiqlashni boshlash (main/views.py:deed_action "approve" bilan bir xil:
                             sessiyaga PENDING_APPROVE yoziladi, brauzer /sso/start/approve/ ga o'tadi). Imzolagach
                             main/sso_views.py:eimzo_return foydalanuvchini SPA sahifasiga qaytaradi.
* flash/                   — eimzo_return qoldirgan Django xabarlarini (messages) o'qish.
* counts/                  — menyudagi nishonlar (main/context_processors.py:contact_badge_counts).
* organizations/, employees/, workers/, agreements/ — "Hujjatlar yaratish" oynasidagi ro'yxatlar
                             (contact_user va main/ajax_views.py dagi ajax_* bilan bir xil).
* status/<code>/<id>/      — deed_status (QR kod bo'yicha ochiladigan holat sahifasi), kirishsiz ham ishlaydi.
"""
from django.conf import settings
from django.contrib import messages as dj_messages
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.urls import path
from rest_framework import permissions, serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import DeedConsentPermission
from api.serializers import DeedSerializer
from api.views import DeedViewSet, _visible_deeds
from main import ajax_views
from main.context_processors import contact_badge_counts
from main.models import Deed, DeedConsent, Employee, Organization
from main.views import validate_pdf_file

# Ro'yxat turi → DeedViewSet._apply_role dagi rol (contact_user, contact_user_arxiv, contact, ...)
BOXES = {
    "send": "created_active",
    "send_archive": "created_archive",
    "sign": "to_sign",
    "sign_archive": "signed",
    "agree": "to_agree",
    "agree_archive": "agreed",
}


def _person(emp):
    if not emp:
        return None
    return {
        "id": emp.id,
        "full_name": emp.full_name,
        "organization_name": emp.organization.name if emp.organization_id else None,
        "rank_name": emp.rank.name if emp.rank_id else None,
        "region_name": emp.region.name if emp.region_id else None,
    }


class MessagesDeedSerializer(DeedSerializer):
    """DeedSerializer + eski jadval va "Dalolatnoma holati" oynasidagi qo'shimcha ma'lumot."""

    user_info = serializers.SerializerMethodField()
    sender_info = serializers.SerializerMethodField()
    receiver_info = serializers.SerializerMethodField()

    class Meta(DeedSerializer.Meta):
        fields = DeedSerializer.Meta.fields + ["user_info", "sender_info", "receiver_info"]
        read_only_fields = fields

    def get_user_info(self, deed):
        return _person(deed.user)

    def get_sender_info(self, deed):
        return _person(deed.sender)

    def get_receiver_info(self, deed):
        return _person(deed.receiver)


PERSON_RELATED = []
for _p in ("user", "sender", "receiver"):
    PERSON_RELATED += [_p, f"{_p}__organization", f"{_p}__rank", f"{_p}__region"]


class MessagesDeedViewSet(DeedViewSet):
    """DeedViewSet (ko'rish doirasi _visible_deeds va rollar _apply_role) — faqat ro'yxat va bitta hujjat,
    kengaytirilgan maydonlar bilan."""

    def get_serializer_class(self):
        return MessagesDeedSerializer

    def get_queryset(self):
        qs = _visible_deeds(self.request.user).select_related("organization", *PERSON_RELATED).prefetch_related(
            "orders", "deedfiles_set",
            Prefetch("deedconsent_set", queryset=DeedConsent.objects.select_related(
                "employee", "employee__organization", "employee__rank").order_by("id")),
        )
        if self.action == "list":
            box = (self.request.query_params.get("box") or "").strip()
            if box not in BOXES:
                raise ValidationError({"box": "Mumkin: " + ", ".join(BOXES)})
            qs = self._apply_role(qs, BOXES[box], _employee(self.request))
        return qs.distinct().order_by("-id")


deed_list = MessagesDeedViewSet.as_view({"get": "list"})
deed_detail = MessagesDeedViewSet.as_view({"get": "retrieve"})


def _employee(request):
    emp = getattr(request.user, "employee", None)
    if not emp:
        raise PermissionDenied("Employee yo'q")
    return emp


class CountsView(APIView):
    """Menyudagi "Imzolash uchun" / "Kelishish uchun" sonlari (keshsiz — amal bajarilgach darhol yangilanadi)."""

    permission_classes = [DeedConsentPermission]

    def get(self, request):
        data = contact_badge_counts.__wrapped__(request._request)
        return Response({"sign": data["contact_badge_count"], "agree": data["contact_agrement_badge_count"]})


class ApproveStartSerializer(serializers.Serializer):
    message = serializers.CharField(required=False, allow_blank=True, default="")
    return_to = serializers.CharField(required=False, allow_blank=True, default="/messages/sign")

    def validate_return_to(self, value):
        value = (value or "").strip() or "/messages/sign"
        # Faqat shu bo'lim sahifasiga qaytarish (ochiq redirect bo'lmasin)
        if not value.startswith("/messages") or value.startswith("//") or "\\" in value:
            raise serializers.ValidationError("Noto'g'ri manzil")
        return value


class ApproveStartView(APIView):
    """
    E-IMZO bilan tasdiqlashni boshlash — main/views.py:deed_action (action=approve) bilan bir xil tekshiruvlar.
    Javob: {"redirect": "/sso/start/approve/"} — brauzer shu manzilga o'tadi (sso_start_approve → E-IMZO →
    eimzo_return → return_to).
    """

    permission_classes = [DeedConsentPermission]

    def post(self, request, pk):
        emp = _employee(request)
        ser = ApproveStartSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        deed = get_object_or_404(Deed, pk=pk)

        if deed.receiver_id == emp.id:
            role, current = "receiver", deed.status_receiver
        elif deed.sender_id == emp.id:
            role, current = "sender", deed.status_sender
        else:
            raise PermissionDenied("Sizga ruxsat yo'q")
        if current != "viewed":
            raise ValidationError({"detail": "Bu dalolatnoma holatida amal bajarib bo'lmaydi"})

        ok, error = validate_pdf_file(deed.file)
        if not ok:
            raise ValidationError({"detail": error})

        request.session["PENDING_APPROVE"] = {
            "deed_id": deed.id,
            "role": role,
            "message": ser.validated_data["message"].strip(),
            # return_to — React yo'li (/messages/...); yangi interfeys /app/ ostida (config/spa.py)
            "redirect_url": request.build_absolute_uri(settings.SPA_URL.rstrip("/") + ser.validated_data["return_to"]),
        }
        request.session.modified = True
        return Response({"redirect": "/sso/start/approve/"})


class FlashView(APIView):
    """Django messages (eimzo_return va boshqa eski sahifalar qoldirgan) — o'qilgach o'chadi."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        out = []
        for m in dj_messages.get_messages(request._request):
            tags = m.tags or ""
            tone = "error" if "error" in tags else "success" if "success" in tags else "info"
            out.append({"text": str(m.message), "tone": tone})
        return Response(out)


class OrganizationsView(APIView):
    """contact_user dagi "Hujjatlar qaysi tashkilotga tegishli" ro'yxati — barcha tashkilotlar."""

    permission_classes = [DeedConsentPermission]

    def get(self, request):
        return Response(list(Organization.objects.order_by("id").values("id", "name", "type")))


class LegacyAjaxView(APIView):
    """main/ajax_views.py dagi tayyor JSON funksiyani chaqiradi (mantiq takrorlanmaydi)."""

    permission_classes = [DeedConsentPermission]
    func = None

    def get(self, request):
        return type(self).func(request._request)


class EmployeesView(LegacyAjaxView):
    """?organization= — imzolovchi xodimlar (ajax_employees_org_user): {"results": [{id, text}]}"""

    func = staticmethod(ajax_views.ajax_employees_org_user)


class WorkersView(LegacyAjaxView):
    """Xizmat ko'rsatuvchi xodimlar (ajax_employees_worker): {"results": [{id, text}]}"""

    func = staticmethod(ajax_views.ajax_employees_worker)


class AgreementsView(LegacyAjaxView):
    """?org_id= — kelishuvchilar (ajax_agreements_employees): [{id, full_name, rank}]"""

    func = staticmethod(ajax_views.ajax_agreements_employees)


def _options(qs):
    return [
        {"id": e.id, "full_name": e.full_name, "rank_name": e.rank.name if e.rank_id else None}
        for e in qs.select_related("rank").order_by("last_name", "first_name", "father_name")
    ]


class EditOptionsView(APIView):
    """deed_edit dagi ro'yxatlar: imzolovchi (uning tashkiloti), qabul qiluvchi (uning tashkiloti),
    kelishuvchilar (imzolovchi, qabul qiluvchi va yaratuvchi tashkilotlari)."""

    permission_classes = [DeedConsentPermission]

    def get(self, request, pk):
        emp = _employee(request)
        deed = get_object_or_404(Deed.objects.select_related("sender", "receiver"), pk=pk)
        if deed.user_id != emp.id:
            raise PermissionDenied("Sizga ruxsat yo'q")
        sender_org = deed.sender.organization_id if deed.sender_id else None
        receiver_org = deed.receiver.organization_id if deed.receiver_id else None
        org_ids = [x for x in (sender_org, receiver_org, emp.organization_id) if x]
        none = Employee.objects.none()
        return Response({
            "sender": _options(Employee.objects.filter(organization_id=sender_org) if sender_org else none),
            "receiver": _options(Employee.objects.filter(organization_id=receiver_org) if receiver_org else none),
            "agreements": _options(Employee.objects.filter(organization_id__in=org_ids).distinct() if org_ids else none),
            "selected_agreements": list(DeedConsent.objects.filter(deed_id=deed.id).values_list("employee_id", flat=True)),
        })


class PublicStatusSerializer(MessagesDeedSerializer):
    """deed_status sahifasidagi ma'lumot: matnsiz va amal bayroqlarisiz."""

    class Meta(MessagesDeedSerializer.Meta):
        fields = [
            "id", "code", "file", "status", "status_display", "organization_name", "date_creat", "message_user",
            "status_sender", "date_sender", "message_sender", "status_receiver", "date_receiver", "message_receiver",
            "receiver", "consents", "user_info", "sender_info", "receiver_info",
        ]
        read_only_fields = fields


class StatusView(APIView):
    """deed_status — kod va ID bo'yicha (eski sahifa kabi kirishsiz ham ochiladi)."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, code, pk):
        deed = get_object_or_404(
            Deed.objects.select_related("organization", *PERSON_RELATED).prefetch_related(
                Prefetch("deedconsent_set", queryset=DeedConsent.objects.select_related(
                    "employee", "employee__organization", "employee__rank").order_by("id"))
            ),
            pk=pk, code=code,
        )
        return Response(PublicStatusSerializer(deed, context={"request": request}).data)


urlpatterns = [
    path("counts/", CountsView.as_view()),
    path("flash/", FlashView.as_view()),
    path("organizations/", OrganizationsView.as_view()),
    path("employees/", EmployeesView.as_view()),
    path("workers/", WorkersView.as_view()),
    path("agreements/", AgreementsView.as_view()),
    path("deeds/", deed_list),
    path("deeds/<int:pk>/", deed_detail),
    path("deeds/<int:pk>/edit-options/", EditOptionsView.as_view()),
    path("deeds/<int:pk>/approve/", ApproveStartView.as_view()),
    path("status/<str:code>/<int:pk>/", StatusView.as_view()),
]
