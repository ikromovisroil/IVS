from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    Organization, Department, Directorate, Division,
    Rank, Region, Rol, Employee,
    Category, Technics,
    ExtraCategory, ExtraTechnics,
    Unit, Material,
    Goal, Order, OrderMaterial,
    Deed, DeedConsent,
    Contract, Liable
)

from .serializers import (
    OrganizationSerializer, DepartmentSerializer, DirectorateSerializer, DivisionSerializer,
    RankSerializer, RegionSerializer, RolSerializer, EmployeeSerializer,
    CategorySerializer, TechnicsSerializer,
    ExtraCategorySerializer, ExtraTechnicsSerializer,
    UnitSerializer, MaterialSerializer,
    GoalSerializer, OrderSerializer, OrderMaterialSerializer,
    DeedSerializer, DeedConsentSerializer,
    ContractSerializer, LiableSerializer
)


class BaseModelViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]


class OrganizationViewSet(BaseModelViewSet):
    queryset = Organization.objects.all().order_by("name")
    serializer_class = OrganizationSerializer
    search_fields = ["name", "contract"]
    ordering_fields = ["id", "name"]


class DepartmentViewSet(BaseModelViewSet):
    queryset = Department.objects.select_related("organization").all().order_by("name")
    serializer_class = DepartmentSerializer
    filterset_fields = ["organization"]
    search_fields = ["name", "organization__name"]
    ordering_fields = ["id", "name"]


class DirectorateViewSet(BaseModelViewSet):
    queryset = Directorate.objects.select_related("department", "department__organization").all().order_by("name")
    serializer_class = DirectorateSerializer
    filterset_fields = ["department"]
    search_fields = ["name", "department__name"]
    ordering_fields = ["id", "name"]


class DivisionViewSet(BaseModelViewSet):
    queryset = Division.objects.select_related(
        "directorate", "directorate__department", "directorate__department__organization"
    ).all().order_by("name")
    serializer_class = DivisionSerializer
    filterset_fields = ["directorate"]
    search_fields = ["name", "directorate__name"]
    ordering_fields = ["id", "name"]


class RankViewSet(BaseModelViewSet):
    queryset = Rank.objects.all().order_by("name")
    serializer_class = RankSerializer
    search_fields = ["name"]
    ordering_fields = ["id", "name"]


class RegionViewSet(BaseModelViewSet):
    queryset = Region.objects.all().order_by("name")
    serializer_class = RegionSerializer
    search_fields = ["name"]
    ordering_fields = ["id", "name"]


class RolViewSet(BaseModelViewSet):
    queryset = Rol.objects.select_related("employee").all().order_by("id")
    serializer_class = RolSerializer
    filterset_fields = [
        "employee", "client", "order", "boss", "shop", "akt",
        "status", "technics", "technics_edit", "material", "material_edit"
    ]
    ordering_fields = ["id"]


class EmployeeViewSet(BaseModelViewSet):
    queryset = Employee.objects.select_related(
        "user", "organization", "department", "directorate", "division", "rank", "region"
    ).all().order_by("id")
    serializer_class = EmployeeSerializer
    filterset_fields = ["organization", "department", "directorate", "division", "rank", "region"]
    search_fields = ["last_name", "first_name", "father_name", "pinfl", "phone", "user__username"]
    ordering_fields = ["id", "last_name", "first_name", "date_creat"]


class CategoryViewSet(BaseModelViewSet):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer
    search_fields = ["name"]
    ordering_fields = ["id", "name"]


class TechnicsViewSet(BaseModelViewSet):
    queryset = Technics.objects.select_related(
        "category", "organization", "department", "directorate", "division", "employee"
    ).all().order_by("id")
    serializer_class = TechnicsSerializer
    filterset_fields = ["category", "organization", "department", "directorate", "division", "employee", "status", "is_active"]
    search_fields = ["name", "inventory", "serial", "mac", "ip", "parametr"]
    ordering_fields = ["id", "name", "date_creat", "date_edit"]


class ExtraCategoryViewSet(BaseModelViewSet):
    queryset = ExtraCategory.objects.all().order_by("name")
    serializer_class = ExtraCategorySerializer
    search_fields = ["name"]
    ordering_fields = ["id", "name"]


class ExtraTechnicsViewSet(BaseModelViewSet):
    queryset = ExtraTechnics.objects.select_related("category", "organization", "technics").all().order_by("id")
    serializer_class = ExtraTechnicsSerializer
    filterset_fields = ["category", "organization", "technics", "status", "is_active"]
    search_fields = ["name", "inventory", "serial", "parametr"]
    ordering_fields = ["id", "name", "date_creat", "date_edit"]


class UnitViewSet(BaseModelViewSet):
    queryset = Unit.objects.all().order_by("name")
    serializer_class = UnitSerializer
    search_fields = ["name"]
    ordering_fields = ["id", "name"]


class MaterialViewSet(BaseModelViewSet):
    queryset = Material.objects.select_related("employee", "unit").all().order_by("id")
    serializer_class = MaterialSerializer
    filterset_fields = ["employee", "unit", "status", "is_active"]
    search_fields = ["name", "code"]
    ordering_fields = ["id", "name", "date_creat", "date_edit"]


class GoalViewSet(BaseModelViewSet):
    queryset = Goal.objects.all().order_by("name")
    serializer_class = GoalSerializer
    search_fields = ["name"]
    ordering_fields = ["id", "name"]


class OrderViewSet(BaseModelViewSet):
    queryset = Order.objects.select_related(
        "sender", "receiver", "goal", "technics"
    ).prefetch_related("materials__material").all().order_by("-id")
    serializer_class = OrderSerializer
    filterset_fields = ["sender", "receiver", "goal", "technics", "status", "receiver_seen"]
    search_fields = ["body", "sender__last_name", "receiver__last_name", "technics__name"]
    ordering_fields = ["id", "date_creat", "date_edit", "date_accepted", "date_finished"]


class OrderMaterialViewSet(BaseModelViewSet):
    queryset = OrderMaterial.objects.select_related("order", "material").all().order_by("id")
    serializer_class = OrderMaterialSerializer
    filterset_fields = ["order", "material"]
    search_fields = ["material__name"]
    ordering_fields = ["id"]


class DeedViewSet(BaseModelViewSet):
    queryset = Deed.objects.select_related("sender", "receiver", "user").all().order_by("-id")
    serializer_class = DeedSerializer
    filterset_fields = [
        "sender", "receiver", "user",
        "status_sender", "status_receiver",
        "sender_seen", "receiver_seen", "file_type"
    ]
    search_fields = ["body", "message_sender", "message_receiver", "message_user"]
    ordering_fields = ["id", "date_creat", "date_edit", "date_sender", "date_receiver"]


class DeedConsentViewSet(BaseModelViewSet):
    queryset = DeedConsent.objects.select_related("deed", "employee").all().order_by("-id")
    serializer_class = DeedConsentSerializer
    filterset_fields = ["deed", "employee", "status"]
    search_fields = ["message", "employee__last_name", "employee__first_name"]
    ordering_fields = ["id", "date_creat", "date_edit"]


class ContractViewSet(BaseModelViewSet):
    queryset = Contract.objects.all().order_by("name")
    serializer_class = ContractSerializer
    search_fields = ["name", "unit"]
    ordering_fields = ["id", "name", "price"]


class LiableViewSet(BaseModelViewSet):
    queryset = Liable.objects.select_related("employee", "contract", "category").all().order_by("id")
    serializer_class = LiableSerializer
    filterset_fields = ["employee", "contract", "category"]
    search_fields = ["employee__last_name", "contract__name", "category__name"]
    ordering_fields = ["id"]