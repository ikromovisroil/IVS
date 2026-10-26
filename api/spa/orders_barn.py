"""
Omborxona (material) arizalari — yangi React interfeysi (frontend/src/pages/orders-barn) uchun qo'shimcha endpointlar.
/api/v1/spa/orders-barn/ ostida ulanadi.

Ro'yxatlar va holat o'zgarishlari mavjud /api/v1/orders/ da (?role=barn_*, /accept/, /reject/, /finish/,
/confirm/, /decide/). Bu yerda faqat yetishmaganlari:

  GET    orders/<id>/                    — ariza tafsilotlari (eski modaldagi xodim bloklari, material qoldig'i/rasmi)
  POST   order-materials/<id>/delete/    — arizadagi materialni o'chirish (main.ajax_views.ordermaterial_delete)
  GET    cart/                           — savat (OrderMaterial, order=None) — eski order_sender_basket_barn
  POST   cart/toggle/  {material}        — savatga qo'shish / olib tashlash — eski add_material_to_cart
  DELETE cart/<id>/                      — savatdan o'chirish — eski delete_material_from_cart
  POST   cart/submit/  {goal, body, numbers: {item_id: son}} — savatdan ariza yaratish — eski create_order_sender_from
"""
import json

from django.shortcuts import get_object_or_404
from django.urls import path
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import OrderSerializer
from api.views import OrderViewSet
from main.ajax_views import ordermaterial_delete
from main.order_views import CartEmptyError, create_order_from_cart
from main.models import Employee, Goal, Material, MaterialEmployee, OrderMaterial
from main.push_views import notify_eligible_employees_new_order


def _client_employee(request):
    """Eski barn sahifalaridagi shart: xodim profili bor va ATM (worker) xodimi emas."""
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")
    if getattr(employee.organization, "type", None) == "worker":
        raise PermissionDenied("Sizga ruxsat yo'q")
    return employee


def _selectable_materials(employee):
    """Mijoz tanlay oladigan materiallar — order_sender_material_barn / orders/selectable-materials bilan bir xil."""
    category_ids = MaterialEmployee.category.through.objects.filter(
        materialemployee__employee=employee
    ).values_list("materialcategory_id", flat=True)
    return Material.objects.filter(organization=employee.organization, is_active=True, category_id__in=category_ids)


def _media(f):
    return f.url if f else None


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
        "phone": e.phone,
    }


class OrderDetailView(APIView):
    """Ariza tafsilotlari. Kim ko'ra olishi /api/v1/orders/{id}/ bilan bir xil (OrderViewSet.get_queryset)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        _client_employee(request)
        view = OrderViewSet(request=request, action="retrieve", format_kwarg=None, args=(), kwargs={"pk": pk})
        order = get_object_or_404(view.get_queryset().filter(goal__organization__type="client"), pk=pk)
        data = dict(OrderSerializer(order, context=view.get_serializer_context()).data)
        ids = {role: getattr(order, f"{role}_id") for role in ("sender", "receiver", "user")}
        people = Employee.objects.select_related(
            "rank", "organization", "department", "directorate", "division"
        ).in_bulk([i for i in ids.values() if i])
        data["people"] = {role: _person(people.get(i)) for role, i in ids.items()}
        extra = {
            om.id: om for om in OrderMaterial.objects.filter(order=order).select_related("material")
        }
        for m in data["materials"]:
            om = extra.get(m["id"])
            mat = om.material if om and om.material_id else None
            m["stock"] = mat.number if mat else None
            m["image"] = _media(mat.image) if mat else None
        return Response(data)


class OrderMaterialDeleteView(APIView):
    """
    Arizadagi materialni o'chirish (bajaruvchi; process/finished). Mantiq to'liq eski
    main.ajax_views.ordermaterial_delete da: berilgan miqdor omborga qaytadi va harakat jurnaliga yoziladi.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        _client_employee(request)
        res = ordermaterial_delete(request._request, pk)
        payload = json.loads(res.content or b"{}")
        if res.status_code == 403:
            raise PermissionDenied("Sizda bu materialni o'chirish huquqi yo'q")
        if res.status_code >= 400:
            raise ValidationError({"detail": payload.get("message") or "Material o'chirilmadi"})
        return Response({"status": "ok"})


class CartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        employee = _client_employee(request)
        items = (
            OrderMaterial.objects.filter(order__isnull=True, user=employee, material__isnull=False)
            .select_related("material", "material__unit").order_by("-id")
        )
        return Response([
            {
                "id": it.id,
                "material": it.material_id,
                "name": it.material.name,
                "unit_name": it.material.unit.name if it.material.unit_id else None,
                "image": _media(it.material.image),
                "stock": it.material.number,
                "number": it.number,
            }
            for it in items
        ])


class CartToggleView(APIView):
    """Savatga qo'shish yoki (bor bo'lsa) olib tashlash. Faqat sizga ruxsat etilgan materiallar."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        employee = _client_employee(request)
        try:
            material_id = int(request.data.get("material"))
        except (TypeError, ValueError):
            raise ValidationError({"material": "Noto'g'ri material ID"})
        material = _selectable_materials(employee).filter(pk=material_id).first()
        if not material:
            raise ValidationError({"material": "Material topilmadi yoki sizga ruxsat etilmagan"})

        item = OrderMaterial.objects.filter(order=None, user=employee, material=material).first()
        if item:
            item.delete()
            return Response({"action": "removed", "in_cart": False, "message": "Savatdan olib tashlandi"})
        OrderMaterial.objects.create(order=None, user=employee, material=material, number=1)
        return Response({"action": "added", "in_cart": True, "message": "Savatga saqlandi"})


class CartItemView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        employee = _client_employee(request)
        get_object_or_404(OrderMaterial, pk=pk, order__isnull=True, user=employee).delete()
        return Response(status=204)


class CartSubmitView(APIView):
    """
    Savatdan ariza yaratish (eski create_order_sender_from): savatdagi qatorlar arizaga o'tadi, soni yangilanadi.
    Ariza turi — o'z tashkilotining (client) maqsadlari (/me/ dagi orders.material_goals).
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        employee = _client_employee(request)
        body = (request.data.get("body") or "").strip() or None
        try:
            goal_id = int(request.data.get("goal"))
        except (TypeError, ValueError):
            raise ValidationError({"goal": "Ariza turi tanlanmadi"})
        goal = Goal.objects.filter(
            pk=goal_id, organization__type="client", organization_id=employee.organization_id
        ).first()
        if not goal:
            raise ValidationError({"goal": "Ariza turi noto'g'ri"})

        numbers = request.data.get("numbers") or {}
        if not isinstance(numbers, dict):
            raise ValidationError({"numbers": "Noto'g'ri format"})
        parsed = {}
        for key, value in numbers.items():
            try:
                n = int(value)
            except (TypeError, ValueError):
                raise ValidationError({"numbers": "Soni butun son bo'lishi kerak"})
            if n < 1:
                raise ValidationError({"numbers": "Soni kamida 1 bo'lishi kerak"})
            parsed[str(key)] = n

        allowed = set(_selectable_materials(employee).values_list("id", flat=True))

        def check(items):
            bad = [it.material.name for it in items if it.material_id not in allowed]
            if bad:
                raise ValidationError({"detail": f"Savatdagi material endi mavjud emas: {', '.join(bad)}"})

        try:
            order = create_order_from_cart(employee, goal, body, {int(k): n for k, n in parsed.items() if k.isdigit()}, check)
        except CartEmptyError:
            raise ValidationError({"detail": "Savat bo'sh — ariza yaratib bo'lmaydi"})

        try:
            notify_eligible_employees_new_order(order)
        except Exception:  # bildirishnoma yuborilmasa ham ariza yaratilgan bo'lib qoladi
            import logging
            logging.getLogger(__name__).exception("Yangi ariza bildirishnomasi yuborilmadi")

        return Response({"id": order.id, "message": "Ariza yuborildi"}, status=201)


urlpatterns = [
    path("orders/<int:pk>/", OrderDetailView.as_view(), name="spa_barn_order_detail"),
    path("order-materials/<int:pk>/delete/", OrderMaterialDeleteView.as_view(), name="spa_barn_om_delete"),
    path("cart/", CartView.as_view(), name="spa_barn_cart"),
    path("cart/toggle/", CartToggleView.as_view(), name="spa_barn_cart_toggle"),
    path("cart/submit/", CartSubmitView.as_view(), name="spa_barn_cart_submit"),
    path("cart/<int:pk>/", CartItemView.as_view(), name="spa_barn_cart_item"),
]
