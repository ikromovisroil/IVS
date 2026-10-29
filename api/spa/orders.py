"""
"Arizalar" (ATM arizalari) bo'limi uchun React interfeysi endpointlari: /api/v1/spa/orders/...

Asosiy amallar mavjud /api/v1/orders/ da (ro'yxat ?role=..., yaratish, accept, assignees, finish, decide,
available-materials, badges). Bu yerda faqat yetishmaganlari:

  GET  goals/                    — ATM ariza maqsadlari (saytdagidek hamma uchun worker goal'lar)
  GET  organizations/            — "Ariza berish" (boshqa xodim nomidan) uchun tashkilotlar ('add_order')
  GET  organizations/<id>/employees/ — o'sha tashkilotning foydalanuvchi hududidagi xodimlari ('add_order')
  GET  <id>/                     — ariza tafsilotlari (muallif va mas'ul xodim ma'lumotlari bilan)
  GET  <id>/technics/            — ariza muallifining texnikalari (yakunlash oynasi uchun)
  POST materials/<id>/delete/    — arizaga biriktirilgan materialni o'chirish (omborga qaytariladi)
  GET  <id>/deed/                — akt (dalolatnoma) sahifasi uchun: imzolovchilar va hujjat matni
  POST <id>/deed/                — aktni imzolashga yuborish

Ruxsat va biznes-mantiq main/order_views.py va main/ajax_views.py dagi funksiyalardan olinadi.
"""
import base64
import binascii
import html as html_lib
import logging

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import path
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from main import ajax_views
from main.html_pdf import HtmlPdfError
from main.models import Employee, Goal, Order, Organization
from main.order_views import ORDER_DEED_BODY_TEMPLATE, create_order_act, order_deed_context, order_deed_queryset
from main.push_views import notify_deed_sender
from main.sanitizers import sanitize_deed_body
from api.serializers import OrderSerializer
from api.views import OrderViewSet

# DRF istisnolari oxirida import qilinadi (api/views.py dagi izohga qarang)
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError  # noqa: E402


def _employee(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")
    return employee


def _require(request, perm):
    if not request.user.has_perm(perm):
        raise PermissionDenied("Sizga ruxsat yo'q")


def _person(e):
    if not e:
        return None
    return {
        "id": e.id,
        "full_name": e.full_name,
        "rank": e.rank.name if e.rank_id else None,
        "organization": e.organization.name if e.organization_id else None,
        "department": e.department.name if e.department_id else None,
        "directorate": e.directorate.name if e.directorate_id else None,
        "division": e.division.name if e.division_id else None,
        "phone": e.phone or None,
    }


def _legacy(request, **params):
    """main/ dagi eski view'ni chaqirish uchun Django so'rovi: DRF aniqlagan foydalanuvchi va GET parametrlari bilan
    (sessiyasiz autentifikatsiyada ham @login_required o'tadi)."""
    django_request = request._request
    django_request.user = request.user
    if params:
        django_request.GET = django_request.GET.copy()
        for k, v in params.items():
            django_request.GET[k] = v
    return django_request


def _visible_order_qs(request):
    """/api/v1/orders/{id}/ dagi ko'rish qoidalari (OrderViewSet.get_queryset, retrieve)."""
    view = OrderViewSet()
    view.request = request
    view.action = "retrieve"
    view.format_kwarg = None
    view.kwargs = {}
    return view.get_queryset()


class GoalsView(APIView):
    """order_sender / order_sender_user: Goal.objects.filter(organization__type="worker")."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _employee(request)
        rows = Goal.objects.filter(organization__type="worker").order_by("id").values("id", "name")
        return Response(list(rows))


class OrganizationsView(APIView):
    """order_sender_user: barcha tashkilotlar ('add_order')."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _employee(request)
        _require(request, "main.add_order")
        return Response(list(Organization.objects.order_by("id").values("id", "name")))


class OrganizationEmployeesView(APIView):
    """ajax_employees_org_user_region: tashkilotning foydalanuvchi hududidagi faol xodimlari."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        _require(request, "main.add_order")
        return ajax_views.ajax_employees_org_user_region(_legacy(request, organization=str(pk)))


class OrderDetailView(APIView):
    """Ariza tafsilotlari oynasi: OrderSerializer + muallif va mas'ul xodimning lavozimi, bo'limi, telefoni."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        _employee(request)
        order = _visible_order_qs(request).filter(pk=pk).first()
        if not order:
            raise NotFound("Ariza topilmadi")
        related = ("rank", "organization", "department", "directorate", "division")
        people = {
            e.id: e for e in Employee.objects.select_related(*related)
            .filter(id__in=[i for i in (order.sender_id, order.receiver_id, order.user_id) if i])
        }
        data = OrderSerializer(order, context={"request": request}).data
        data["sender_info"] = _person(people.get(order.sender_id))
        data["receiver_info"] = _person(people.get(order.receiver_id))
        data["user_info"] = _person(people.get(order.user_id))
        return Response(data)


class OrderTechnicsView(APIView):
    """ajax_sender_technics: ariza muallifiga biriktirilgan (yoki uning bo'limidagi egasiz) texnikalar.
    Faqat arizani bajarayotgan xodim (yakunlash oynasi)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        employee = _employee(request)
        _require(request, "main.change_order")
        order = get_object_or_404(Order, pk=pk)
        if order.receiver_id != employee.id:
            raise PermissionDenied("Sizga ruxsat yo'q")
        return ajax_views.ajax_sender_technics(_legacy(request, sender_id=str(order.sender_id or "")))


class OrderMaterialDeleteView(APIView):
    """ordermaterial_delete: faqat arizaning bajaruvchisi, process/finished holatida; material omborga qaytadi."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        _require(request, "main.change_order")
        return ajax_views.ordermaterial_delete(_legacy(request), pk)




def _deed_order(request, pk):
    """order_receiver_deed dagi tekshiruvlar: change_order, worker tashkiloti, arizani o'zi bajargan, muallif bor."""
    employee = _employee(request)
    _require(request, "main.change_order")
    if not employee.organization or employee.organization.type == "client":
        raise PermissionDenied("Sizga ruxsat yo'q")
    order = get_object_or_404(Order.objects.select_related("sender", "sender__organization", "receiver"), pk=pk)
    if order.receiver_id != employee.id:
        raise PermissionDenied("Sizga ruxsat yo'q")
    if not order.sender_id:
        raise ValidationError({"detail": "Ariza jo'natuvchisi yo'q"})
    return employee, order


class OrderDeedView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        """Akt sahifasi: imzolovchi xodimlar (muallif tashkiloti) va hujjat matni — eski sahifa bilan bitta shablondan
        (templates/main/partials/order_deed_body.html, order_views.order_deed_context)."""
        _deed_order(request, pk)
        order = order_deed_queryset().get(pk=pk)
        context = order_deed_context(order)
        # Eski sahifada matn textarea ichida turadi — brauzer ko'rsatadigan qiymat bilan bir xil bo'lishi uchun unescape
        body = sanitize_deed_body(html_lib.unescape(render_to_string(ORDER_DEED_BODY_TEMPLATE, context)).strip())
        employees = context["employees"].order_by("last_name", "first_name", "father_name", "id")
        return Response({
            "order": {
                "id": order.id,
                "sender_name": order.sender.full_name,
                "organization_name": order.sender.organization.name if order.sender.organization_id else None,
            },
            "employees": [
                {"id": e.id, "full_name": e.full_name, "rank": e.rank.name if e.rank_id else None}
                for e in employees
            ],
            "body": body,
        })

    def post(self, request, pk):
        """order_receiver_deed_post: {"sender": id, "message": str?, "body_encoded": base64(utf-8 HTML)}"""
        employee, order = _deed_order(request, pk)
        # Faqat rad etilgan akt qayta yuboriladi; imzolanayotgan yoki imzolangan akt bor bo'lsa — ikkinchisi yaratilmaydi
        active = order.deeds.filter(status="act").exclude(Q(status_sender="rejected") | Q(status_receiver="rejected"))
        if active.exists():
            raise ValidationError({"detail": "Bu ariza uchun akt allaqachon imzolashga yuborilgan"})
        sender_id = str(request.data.get("sender") or "").strip()
        message = (request.data.get("message") or "").strip() or None

        body = ""
        body_encoded = (request.data.get("body_encoded") or "").strip()
        if body_encoded:
            try:
                body = base64.b64decode(body_encoded).decode("utf-8").strip()
            except (binascii.Error, UnicodeDecodeError, ValueError):
                body = ""
        if body:
            body = sanitize_deed_body(body)

        sender = (
            Employee.objects.filter(id=sender_id, organization=order.sender.organization).first()
            if sender_id.isdigit() else None
        )
        if not sender:
            raise ValidationError({"sender": "Imzolovchi xodim tanlanmadi"})
        if not body:
            raise ValidationError({"body": "Hujjat matni bo'sh bo'lmasin"})

        try:
            deed = create_order_act(order, employee, sender, body, message)
        except HtmlPdfError as e:
            raise ValidationError({"detail": f"Hujjat yaratilmadi: {e}. Qayta urinib ko'ring"})

        try:
            notify_deed_sender(deed)
        except Exception:  # bildirishnoma yuborilmasa ham hujjat yaratilgan
            logging.getLogger(__name__).exception("Akt bildirishnomasi yuborilmadi")

        return Response(
            {"id": deed.id, "file": request.build_absolute_uri(deed.file.url) if deed.file else None},
            status=201,
        )


urlpatterns = [
    path("goals/", GoalsView.as_view(), name="spa_orders_goals"),
    path("organizations/", OrganizationsView.as_view(), name="spa_orders_organizations"),
    path("organizations/<int:pk>/employees/", OrganizationEmployeesView.as_view(), name="spa_orders_org_employees"),
    path("materials/<int:pk>/delete/", OrderMaterialDeleteView.as_view(), name="spa_orders_material_delete"),
    path("<int:pk>/", OrderDetailView.as_view(), name="spa_orders_detail"),
    path("<int:pk>/technics/", OrderTechnicsView.as_view(), name="spa_orders_technics"),
    path("<int:pk>/deed/", OrderDeedView.as_view(), name="spa_orders_deed"),
]
