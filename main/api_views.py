from rest_framework.viewsets import ModelViewSet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import *
from .serializers import *
from .filters import TechnicsFilter, EmployeeFilter


# ---- SIMPLE CRUD ---- #
class OrganizationViewSet(ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer


class DepartmentViewSet(ModelViewSet):
    queryset = Department.objects.select_related("organization")
    serializer_class = DepartmentSerializer
    filterset_fields = ['organization']


class DirectorateViewSet(ModelViewSet):
    queryset = Directorate.objects.select_related("department")
    serializer_class = DirectorateSerializer
    filterset_fields = ['department']


class DivisionViewSet(ModelViewSet):
    queryset = Division.objects.select_related("directorate")
    serializer_class = DivisionSerializer
    filterset_fields = ['directorate']


class RankViewSet(ModelViewSet):
    queryset = Rank.objects.all()
    serializer_class = RankSerializer


class StructureViewSet(ModelViewSet):
    queryset = Region.objects.all()
    serializer_class = RegionSerializer


# ---- EMPLOYEE ---- #
class EmployeeViewSet(ModelViewSet):
    queryset = Employee.objects.select_related(
        "user", "structure", "division", "directorate", "department", "organization", "rank"
    )
    serializer_class = EmployeeSerializer

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = EmployeeFilter
    search_fields = ['user__first_name', 'user__last_name', 'phone']
    ordering_fields = ['id', 'date_creat']
    ordering = ['-date_creat']


# ---- CATEGORY ---- #
class CategoryViewSet(ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


# ---- TECHNICS ---- #
class TechnicsViewSet(ModelViewSet):
    queryset = Technics.objects.select_related(
        "category",
        "employee",
        "employee__organization",
        "employee__department",
        "employee__directorate",
        "employee__division",
    )
    serializer_class = TechnicsSerializer

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = TechnicsFilter

    search_fields = ['name', 'serial', 'inventory', 'ip']
    ordering_fields = ['name', 'date_creat', 'price']
    ordering = ['-date_creat']


# ---- MATERIAL ---- #
class MaterialViewSet(ModelViewSet):
    queryset = Material.objects.select_related("employee", "technics")
    serializer_class = MaterialSerializer
    filterset_fields = ['employee', 'technics']


# ---- TOPIC & GOAL ---- #
class TopicViewSet(ModelViewSet):
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer


class GoalViewSet(ModelViewSet):
    queryset = Goal.objects.select_related("topic")
    serializer_class = GoalSerializer
    filterset_fields = ['topic']


# ---- ORDER ---- #
class OrderViewSet(ModelViewSet):
    queryset = Order.objects.select_related("sender", "receiver", "goal")
    serializer_class = OrderSerializer

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'sender', 'receiver']
    search_fields = ['body', 'sender__user__first_name', 'receiver__user__last_name']
    ordering_fields = ['id', 'date_creat']
    ordering = ['-date_creat']


class OrderMaterialViewSet(ModelViewSet):
    queryset = OrderMaterial.objects.all()
    serializer_class = OrderMaterialSerializer
    filterset_fields = ['order', 'technics', 'material']


# ---- DEED ---- #
class DeedViewSet(ModelViewSet):
    queryset = Deed.objects.select_related("sender", "receiver")
    serializer_class = DeedSerializer
    filterset_fields = ['sender', 'receiver', 'status']

