from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from main.models import *

from .serializers import (
    OrganizationSerializer, DepartmentSerializer, DirectorateSerializer,
    DivisionSerializer, RankSerializer, RegionSerializer,
    RolSerializer, EmployeeSerializer, GroupSerializer, CategorySerializer,
    TechnicsSerializer, StructureCategorySerializer, StructureSerializer,
    UnitSerializer, MaterialSerializer,
    GoalSerializer, OrderSerializer, OrderMaterialSerializer,
    DeedSerializer, DeedConsentSerializer, ContractSerializer, LiableSerializer
)


class BaseModelViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]


class OrganizationViewSet(BaseModelViewSet):
    queryset = Organization.objects.all().order_by("-id")
    serializer_class = OrganizationSerializer
    search_fields = ["name", "contract"]
    ordering_fields = "__all__"
    filterset_fields = ["name"]


class DepartmentViewSet(BaseModelViewSet):
    queryset = Department.objects.select_related("organization").all().order_by("-id")
    serializer_class = DepartmentSerializer
    search_fields = ["name", "organization__name"]
    ordering_fields = "__all__"
    filterset_fields = ["organization"]


class DirectorateViewSet(BaseModelViewSet):
    queryset = Directorate.objects.select_related("department").all().order_by("-id")
    serializer_class = DirectorateSerializer
    search_fields = ["name", "department__name"]
    ordering_fields = "__all__"
    filterset_fields = ["department"]


class DivisionViewSet(BaseModelViewSet):
    queryset = Division.objects.select_related("directorate").all().order_by("-id")
    serializer_class = DivisionSerializer
    search_fields = ["name", "directorate__name"]
    ordering_fields = "__all__"
    filterset_fields = ["directorate"]


class RankViewSet(BaseModelViewSet):
    queryset = Rank.objects.all().order_by("-id")
    serializer_class = RankSerializer
    search_fields = ["name"]
    ordering_fields = "__all__"
    filterset_fields = ["name"]


class RegionViewSet(BaseModelViewSet):
    queryset = Region.objects.all().order_by("-id")
    serializer_class = RegionSerializer
    search_fields = ["name"]
    ordering_fields = "__all__"
    filterset_fields = ["name"]


class RolViewSet(BaseModelViewSet):
    queryset = Rol.objects.select_related("employee").all().order_by("-id")
    serializer_class = RolSerializer
    search_fields = ["employee__last_name", "employee__first_name", "employee__father_name"]
    ordering_fields = "__all__"
    filterset_fields = [
        "employee", "client", "order", "boss", "shop", "akt", "status",
        "technics", "technics_edit", "material", "material_edit"
    ]


class EmployeeViewSet(BaseModelViewSet):
    queryset = Employee.objects.select_related(
        "user", "organization", "department", "directorate", "division", "rank", "region"
    ).all().order_by("-id")
    serializer_class = EmployeeSerializer
    search_fields = [
        "last_name", "first_name", "father_name",
        "pinfl", "phone", "user__username",
        "organization__name", "department__name",
        "directorate__name", "division__name"
    ]
    ordering_fields = "__all__"
    filterset_fields = [
        "organization", "department", "directorate", "division",
        "rank", "region", "user"
    ]


class GroupViewSet(BaseModelViewSet):
    queryset = Group.objects.all().order_by("-id")
    serializer_class = GroupSerializer
    search_fields = ["name"]
    ordering_fields = "__all__"
    filterset_fields = ["name"]


class CategoryViewSet(BaseModelViewSet):
    queryset = Category.objects.select_related("group").all().order_by("-id")
    serializer_class = CategorySerializer
    search_fields = ["name", "group__name"]
    ordering_fields = "__all__"
    filterset_fields = ["group"]


class TechnicsViewSet(BaseModelViewSet):
    queryset = Technics.objects.select_related(
        "group", "category", "organization", "department",
        "directorate", "division", "employee"
    ).all().order_by("-id")
    serializer_class = TechnicsSerializer
    search_fields = [
        "name", "parametr", "inventory", "serial", "mac", "ip",
        "year", "group__name", "category__name", "employee__last_name",
        "employee__first_name", "organization__name"
    ]
    ordering_fields = "__all__"
    filterset_fields = [
        "group", "category", "organization", "department",
        "directorate", "division", "employee", "status", "is_active"
    ]


class StructureCategoryViewSet(BaseModelViewSet):
    queryset = StructureCategory.objects.all().order_by("-id")
    serializer_class = StructureCategorySerializer
    search_fields = ["name"]
    ordering_fields = "__all__"
    filterset_fields = ["name"]


class StructureViewSet(BaseModelViewSet):
    queryset = Structure.objects.select_related(
        "category", "organization", "technics"
    ).all().order_by("-id")
    serializer_class = StructureSerializer
    search_fields = [
        "name", "parametr", "inventory", "serial",
        "year", "category__name", "organization__name", "technics__name"
    ]
    ordering_fields = "__all__"
    filterset_fields = ["category", "organization", "technics", "status", "is_active"]


class UnitViewSet(BaseModelViewSet):
    queryset = Unit.objects.all().order_by("-id")
    serializer_class = UnitSerializer
    search_fields = ["name"]
    ordering_fields = "__all__"
    filterset_fields = ["name"]



class MaterialViewSet(BaseModelViewSet):
    queryset = Material.objects.select_related(
        "organization", "employee", "unit"
    ).all().order_by("-id")
    serializer_class = MaterialSerializer
    search_fields = [
        "name", "code", "year", "organization__name",
        "employee__last_name", "employee__first_name",
        "unit__name"
    ]
    ordering_fields = "__all__"
    filterset_fields = [
        "organization", "employee", "unit", "status", "is_active"
    ]


class GoalViewSet(BaseModelViewSet):
    queryset = Goal.objects.all().order_by("-id")
    serializer_class = GoalSerializer
    search_fields = ["name"]
    ordering_fields = "__all__"
    filterset_fields = ["name"]


class OrderViewSet(BaseModelViewSet):
    queryset = Order.objects.select_related(
        "sender", "goal", "receiver", "technics"
    ).prefetch_related("materials__material").all().order_by("-id")
    serializer_class = OrderSerializer
    search_fields = [
        "body", "sender__last_name", "sender__first_name",
        "receiver__last_name", "receiver__first_name",
        "goal__name", "technics__name", "status"
    ]
    ordering_fields = "__all__"
    filterset_fields = ["sender", "goal", "receiver", "technics", "status", "receiver_seen", "rating"]


class OrderMaterialViewSet(BaseModelViewSet):
    queryset = OrderMaterial.objects.select_related("order", "material").all().order_by("-id")
    serializer_class = OrderMaterialSerializer
    search_fields = ["order__body", "material__name"]
    ordering_fields = "__all__"
    filterset_fields = ["order", "material"]


class DeedViewSet(BaseModelViewSet):
    queryset = Deed.objects.select_related("sender", "receiver", "user").all().order_by("-id")
    serializer_class = DeedSerializer
    search_fields = [
        "code", "body", "message_sender", "message_receiver", "message_user",
        "sender__last_name", "receiver__last_name", "user__last_name"
    ]
    ordering_fields = "__all__"
    filterset_fields = [
        "sender", "receiver", "user",
        "status_sender", "status_receiver",
        "sender_seen", "receiver_seen", "file_type"
    ]


class DeedConsentViewSet(BaseModelViewSet):
    queryset = DeedConsent.objects.select_related("deed", "employee").all().order_by("-id")
    serializer_class = DeedConsentSerializer
    search_fields = ["deed__code", "employee__last_name", "employee__first_name", "message", "status"]
    ordering_fields = "__all__"
    filterset_fields = ["deed", "employee", "status"]


class ContractViewSet(BaseModelViewSet):
    queryset = Contract.objects.all().order_by("-id")
    serializer_class = ContractSerializer
    search_fields = ["name", "unit"]
    ordering_fields = "__all__"
    filterset_fields = ["name", "unit"]


class LiableViewSet(BaseModelViewSet):
    queryset = Liable.objects.select_related("employee", "contract", "category").all().order_by("-id")
    serializer_class = LiableSerializer
    search_fields = [
        "employee__last_name", "employee__first_name",
        "contract__name", "category__name"
    ]
    ordering_fields = "__all__"
    filterset_fields = ["employee", "contract", "category"]