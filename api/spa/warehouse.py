"""
"Ombor" bo'limi (React: frontend/src/pages/technics/ va frontend/src/pages/warehouse/) uchun qo'shimcha
endpointlar — /api/v1/spa/warehouse/.

Yozish amallarining aksariyati mavjud API orqali: /api/v1/technics/ (qo'shish, tahrirlash, o'chirish, assign,
unassign, qr), /api/v1/structures/ (qo'shimcha qurilmalar), /api/v1/materials/ (qo'shish, tahrirlash, o'chirish,
give, service, report). Bu yerda faqat yetishmaganlari:

* technics/                — barn_tex ro'yxati: TechnicsViewSet bilan bir xil doira va filtrlar, lekin qidiruv
                             xodim F.I.O bo'yicha ham (saytdagidek), tartib xodim bo'yicha (jadvalda guruhlash uchun),
                             xodim lavozimi va qo'shimcha qurilmalarning kategoriyasi bilan.
* technics/stats/          — shu filtrlar bo'yicha holatlar soni.
* technics/<id>/           — bitta uskuna (xuddi shu maydonlar).
* technics/<id>/card/      — QR kod sahifasi (main/views.py:technics_detail) ma'lumotlari: har qanday kirgan xodim.
* technics/mine/           — "Texnikalarim" (main/views.py:technics_get): o'ziniki yoki boss_employee bo'lsa
                             bo'limdagi texnikalar va texnikasi yo'q xodimlar.
* structures/stats/ — shu filtrlar bo'yicha holatlar soni.
* structures/, structures/<id>/ — extra_tex ro'yxati: StructureViewSet bilan bir xil, biriktirilgan texnika egasi bilan.
* employees/               — biriktirish oynasidagi xodimlar (main/ajax_views.py:ajax_employees_org).
* employees/pinfl/         — "Xodim qo'shish" (PINFL bo'yicha, main/views.py:employe_create).
* materials/employees/     — barn_mat dagi "Xodim" ro'yxati (MaterialViewSet doirasi bilan bir xil).
* materials/summary/       — materiallar soni va umumiy narxi (shu filtrlar bo'yicha).
* materials/basket/        — "Savat" (mat_arxiv): GET ro'yxat, POST savatga qo'shish (mat_post).
* materials/basket/assign/ — savatni xodimga biriktirish (mat_arxiv_post).
* materials/basket/<id>/delete/ — savatdan o'chirish (mat_arxiv_delete).

Savat va xodim qo'shish amallari main/views.py dagi funksiyalarni o'zini chaqiradi (qoidalar takrorlanmaydi),
ular qoldirgan Django xabarlari (messages) JSON javobga aylantiriladi.
"""
import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Prefetch, Q, Sum
from django.http import QueryDict
from django.shortcuts import get_object_or_404
from django.urls import path
from rest_framework import permissions, serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.routers import SimpleRouter
from rest_framework.views import APIView

from api.permissions import StructurePermission, TechnicsPermission
from api.serializers import StructureSerializer, TechnicsSerializer
from api.spa.people import _MemoryMessages
from api.views import MaterialViewSet, StructureViewSet, TechnicsViewSet
from main import ajax_views
from main import views as legacy
from main.models import Employee, MaterialMovement, Structure, Technics

logger = logging.getLogger(__name__)


# ─────────────────────────── yordamchilar ───────────────────────────

def _employee(request):
    emp = getattr(request.user, "employee", None)
    if not emp:
        raise PermissionDenied("Employee yo'q")
    return emp


def _require(request, perm):
    if not request.user.has_perm(perm):
        raise PermissionDenied("Bu amal uchun ruxsatingiz yo'q.")


def _bridge(request, view_func, data=None, *args, **kwargs):
    """
    main/views.py dagi POST funksiyani (redirect + messages qaytaradi) o'zgarishsiz chaqiradi va natijani JSON qiladi.
    Ruxsat dekoratorlari (permission_required, login_required) o'sha funksiyaning o'zida ishlaydi.
    """
    dj = request._request
    dj.user = request.user
    post = QueryDict(mutable=True)
    for key, value in (data or {}).items():
        if value is not None:
            post[key] = str(value)
    dj.POST = post
    dj.META["HTTP_REFERER"] = "/"
    # Faqat shu view qo'shgan xabarlar: sessiyadagi eski xabarlar ok/xato natijasiga aralashmaydi va o'chmaydi
    storage = _MemoryMessages(dj)
    dj._messages = storage
    view_func(dj, *args, **kwargs)

    items = [{"level": m.level_tag, "text": str(m.message)} for m in storage._queued_messages]
    ok = any(m["level"] == "success" for m in items)
    detail = "; ".join(m["text"] for m in items if not ok or m["level"] == "success")
    return Response({"ok": ok, "detail": detail, "messages": items}, status=200 if ok else 400)


# ─────────────────────────── texnikalar ───────────────────────────

def _device(x):
    return {
        "id": x.id,
        "name": x.name,
        "category_name": x.category.name if x.category_id else None,
        "parametr": x.parametr,
        "inventory": x.inventory,
        "serial": x.serial,
        "year": x.year,
        "price": str(x.price) if x.price is not None else None,
        "status": x.status,
        "status_display": x.get_status_display(),
    }


class SpaTechnicsSerializer(TechnicsSerializer):
    employee_rank = serializers.CharField(source="employee.rank.name", read_only=True, default=None)
    extra_devices = serializers.SerializerMethodField()

    class Meta(TechnicsSerializer.Meta):
        fields = TechnicsSerializer.Meta.fields + ["employee_rank"]

    def get_extra_devices(self, obj):
        items = getattr(obj, "active_structures", None)
        if items is None:
            items = obj.structure_set.filter(is_active=True).select_related("category")
        return [_device(x) for x in items]


class _TechnicsPerm(permissions.BasePermission):
    """card va mine — har qanday kirgan xodim (saytdagidek); qolganlari TechnicsPermission."""

    def has_permission(self, request, view):
        if view.action in ("card", "mine"):
            return bool(request.user and request.user.is_authenticated)
        if view.action == "stats":
            return bool(request.user and request.user.is_authenticated and request.user.has_perm("main.view_technics"))
        return TechnicsPermission().has_permission(request, view)


def _with_devices(qs):
    return qs.select_related("employee__rank").prefetch_related(None).prefetch_related(
        Prefetch(
            "structure_set",
            queryset=Structure.objects.filter(is_active=True).select_related("category").order_by("id"),
            to_attr="active_structures",
        )
    )


class SpaTechnicsViewSet(TechnicsViewSet):
    """barn_tex ro'yxati (faqat o'qish). Doira, ruxsat va filtrlar — TechnicsViewSet niki."""

    http_method_names = ["get", "head", "options"]
    permission_classes = [_TechnicsPerm]
    filter_backends = TechnicsViewSet.filter_backends[:1]  # DjangoFilterBackend; qidiruv quyida (F.I.O bilan)

    def get_serializer_class(self):
        return SpaTechnicsSerializer

    def get_queryset(self):
        return _with_devices(super().get_queryset()).order_by("employee_id", "id")

    def filter_queryset(self, queryset):
        qs = super().filter_queryset(queryset)
        text = (self.request.query_params.get("search") or "").strip()[:120]
        for w in text.split():
            qs = qs.filter(
                Q(employee__last_name__icontains=w) | Q(employee__first_name__icontains=w)
                | Q(employee__father_name__icontains=w) | Q(name__icontains=w) | Q(inventory__icontains=w)
                | Q(serial__icontains=w) | Q(mac__icontains=w) | Q(ip__icontains=w)
            )
        return qs

    @action(detail=False, methods=["get"])
    def stats(self, request):
        self.action = "list"  # TechnicsViewSet.get_queryset: ro'yxat doirasi (Liable kategoriyalari)
        qs = self.filter_queryset(self.get_queryset()).order_by()
        counts = {row["status"]: row["n"] for row in qs.values("status").annotate(n=Count("id"))}
        return Response({
            "total": sum(counts.values()),
            **{s: counts.get(s, 0) for s in ("active", "free", "repair", "defect")},
        })

    @action(detail=True, methods=["get"])
    def card(self, request, pk=None):
        """main/views.py:technics_detail (QR kod sahifasi) — faol uskunaning asosiy ma'lumotlari."""
        tex = get_object_or_404(_with_devices(Technics.objects.select_related("category", "employee")), pk=pk, is_active=True)
        return Response({
            "id": tex.id,
            "name": tex.name,
            "category_name": tex.category.name if tex.category_id else None,
            "parametr": tex.parametr,
            "inventory": tex.inventory,
            "serial": tex.serial,
            "mac": tex.mac,
            "ip": tex.ip,
            "employee_name": tex.employee.full_name if tex.employee_id else None,
            "status": tex.status,
            "status_display": tex.get_status_display(),
            "qr_code": tex.qr_code.url if tex.qr_code else None,
            "extra_devices": [_device(x) for x in tex.active_structures],
        })

    @action(detail=False, methods=["get"])
    def mine(self, request):
        """main/views.py:technics_get — "Texnikalarim"."""
        employee = _employee(request)
        is_boss = request.user.has_perm("main.boss_employee")
        if is_boss:
            base_qs = Technics.objects.filter(
                organization=employee.organization, department=employee.department,
                region=employee.region, is_active=True,
            )
        else:
            base_qs = Technics.objects.filter(employee=employee, is_active=True)

        qs = _with_devices(base_qs.select_related("employee", "category")).order_by("employee_id", "id")
        page = Paginator(qs, 20).get_page(request.query_params.get("page", 1))

        without = []
        if is_boss:
            assigned = base_qs.exclude(employee_id=None).values_list("employee_id", flat=True).distinct()
            without = [
                {"id": e.id, "full_name": e.full_name, "rank_name": e.rank.name if e.rank_id else None}
                for e in Employee.objects.filter(
                    organization=employee.organization, department=employee.department, region=employee.region,
                ).exclude(id__in=assigned).select_related("rank").order_by("last_name", "first_name")
            ]

        return Response({
            "count": page.paginator.count,
            "is_boss": is_boss,
            "results": SpaTechnicsSerializer(page.object_list, many=True, context={"request": request}).data,
            "employees_without_technics": without,
        })


# ─────────────────────────── qo'shimcha qurilmalar ───────────────────────────

class SpaStructureSerializer(StructureSerializer):
    technics_serial = serializers.CharField(source="technics.serial", read_only=True, default=None)
    technics_inventory = serializers.CharField(source="technics.inventory", read_only=True, default=None)
    technics_employee_name = serializers.CharField(source="technics.employee.full_name", read_only=True, default=None)

    class Meta(StructureSerializer.Meta):
        fields = StructureSerializer.Meta.fields + ["technics_serial", "technics_inventory", "technics_employee_name"]


class SpaStructureViewSet(StructureViewSet):
    """extra_tex ro'yxati (faqat o'qish). Doira, ruxsat ('change_technics'), filtrlar va qidiruv — StructureViewSet niki."""

    http_method_names = ["get", "head", "options"]
    permission_classes = [StructurePermission]

    def get_serializer_class(self):
        return SpaStructureSerializer

    def get_queryset(self):
        return super().get_queryset().select_related("technics__employee")

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Shu filtrlar bo'yicha holatlar soni (ro'yxat bilan bir xil doira va filtrlar)."""
        qs = self.filter_queryset(self.get_queryset()).order_by()
        counts = {row["status"]: row["n"] for row in qs.values("status").annotate(n=Count("id"))}
        return Response({
            "total": sum(counts.values()),
            **{s: counts.get(s, 0) for s in ("active", "free", "repair", "defect")},
        })


# ─────────────────────────── xodimlar ───────────────────────────

class EmployeesView(APIView):
    """GET ?organization=&region= — main/ajax_views.py:ajax_employees_org (faol xodimlar: {results: [{id, text}]})."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        dj = request._request
        dj.user = request.user
        return ajax_views.ajax_employees_org(dj)


class EmployeeByPinflView(APIView):
    """POST {pinfl} — main/views.py:employe_create (Gateway orqali xodim yaratish; 'add_employee')."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        pinfl = (request.data.get("pinfl") or "").strip()
        try:
            return _bridge(request, legacy.employe_create, {"pinfl": pinfl})
        except DjangoPermissionDenied:
            raise
        except Exception:  # noqa: BLE001 — Gateway sozlanmagan/ishlamayotgan (people.EmployeeGatewayCreateView bilan bir xil)
            logger.exception("Gateway orqali xodim qo'shishda xatolik (pinfl=%s)", pinfl)
            return Response({"ok": False, "detail": "Tashqi tizim (Gateway) bilan aloqada xatolik yuz berdi. "
                                                    "Birozdan keyin qayta urinib ko'ring."}, status=502)


# ─────────────────────────── materiallar ───────────────────────────

class MaterialEmployeesView(APIView):
    """barn_mat dagi "Xodim" ro'yxati: all_material_employee — tashkilotdagi shop_employee xodimlar, aks holda
    o'ziga biriktirilganlar (+ o'zi, agar javobgar bo'lsa). MaterialViewSet._visible_employee_ids bilan bir xil."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require(request, "main.view_material")
        employee = _employee(request)
        ids = MaterialViewSet()._visible_employee_ids(request.user, employee)
        rows = Employee.objects.filter(id__in=ids).order_by("last_name", "first_name", "father_name")
        return Response([{"id": e.id, "full_name": e.full_name} for e in rows])


class MaterialSummaryView(APIView):
    """GET ?employee=&category=&unit=&search= — /api/v1/materials/ bilan bir xil ro'yxatning soni va umumiy narxi."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require(request, "main.view_material")
        view = MaterialViewSet(request=request, action="list", format_kwarg=None)
        qs = view.filter_queryset(view.get_queryset())
        total = qs.aggregate(s=Sum(ExpressionWrapper(
            F("number") * F("price"), output_field=DecimalField(max_digits=18, decimal_places=2),
        )))["s"] or 0
        return Response({"count": qs.count(), "total_sum": str(total)})


def _basket_row(mv):
    mat = mv.material
    price = mat.price or 0
    return {
        "id": mv.id,
        "material": mat.id,
        "name": mat.name,
        "code": mat.code,
        "price": str(mat.price) if mat.price is not None else None,
        "unit_name": mat.unit.name if mat.unit_id else None,
        "number": mv.outcome or 0,
        "available": mat.number,
        "total_sum": str((mv.outcome or 0) * price),
        "status": mv.status,
        "status_display": mv.get_status_display(),
        "date_creat": mv.date_creat,
    }


class BasketView(APIView):
    """
    GET — "Savat" (mat_arxiv): o'zi yaratgan, hali xodimga biriktirilmagan harakatlar (user=o'zi, employee=None).
    POST {material_id, number} — savatga qo'shish (mat_post).
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _require(request, "main.all_material_employee")
        employee = _employee(request)
        qs = (
            MaterialMovement.objects.filter(user=employee, employee__isnull=True)
            .select_related("material", "material__unit").order_by("-date_creat")
        )
        page = Paginator(qs, 20).get_page(request.query_params.get("page", 1))
        return Response({"count": page.paginator.count, "results": [_basket_row(mv) for mv in page.object_list]})

    def post(self, request):
        return _bridge(request, legacy.mat_post, {
            "material_id": request.data.get("material_id"), "number": request.data.get("number"),
        })


class BasketAssignView(APIView):
    """POST {employee, body} — savatdagi barcha materiallarni xodimga biriktirish (mat_arxiv_post)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        return _bridge(request, legacy.mat_arxiv_post, {
            "employe": request.data.get("employee"), "body": request.data.get("body") or "",
        })


class BasketDeleteView(APIView):
    """POST — savatdan o'chirish (mat_arxiv_delete)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        return _bridge(request, legacy.mat_arxiv_delete, {}, pk)


router = SimpleRouter()
router.register("technics", SpaTechnicsViewSet, basename="spa-warehouse-technics")
router.register("structures", SpaStructureViewSet, basename="spa-warehouse-structures")

urlpatterns = [
    path("employees/", EmployeesView.as_view(), name="spa_warehouse_employees"),
    path("employees/pinfl/", EmployeeByPinflView.as_view(), name="spa_warehouse_employee_pinfl"),
    path("materials/employees/", MaterialEmployeesView.as_view(), name="spa_warehouse_material_employees"),
    path("materials/summary/", MaterialSummaryView.as_view(), name="spa_warehouse_material_summary"),
    path("materials/basket/", BasketView.as_view(), name="spa_warehouse_basket"),
    path("materials/basket/assign/", BasketAssignView.as_view(), name="spa_warehouse_basket_assign"),
    path("materials/basket/<int:pk>/delete/", BasketDeleteView.as_view(), name="spa_warehouse_basket_delete"),
] + router.urls
