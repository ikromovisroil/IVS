from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from main.models import (
    Organization, Region, Department, Directorate, Division, Rank, Rol,
    Employee, Group, Category, Technics, StructureCategory, Structure,
    Unit, MaterialCategory, Material, MaterialEmployee, Goal, Order,
    OrderMaterial, OrderGoal, MaterialUser, Deed, DeedConsent, Contract,
    Liable, MaterialMovement,
)
from .serializers import (
    OrganizationSerializer, RegionSerializer, DepartmentSerializer,
    DirectorateSerializer, DivisionSerializer, RankSerializer, RolSerializer,
    EmployeeSerializer, GroupSerializer, CategorySerializer,
    TechnicsSerializer, StructureCategorySerializer, StructureSerializer,
    UnitSerializer, MaterialCategorySerializer, MaterialSerializer,
    MaterialEmployeeSerializer, GoalSerializer, OrderSerializer,
    OrderCreateSerializer, OrderMaterialSerializer, OrderGoalSerializer,
    MaterialUserSerializer, DeedSerializer, DeedConsentSerializer,
    ContractSerializer, LiableSerializer, MaterialMovementSerializer,
)


class BaseModelViewSet(viewsets.ModelViewSet):
    """Umumiy sozlamalarga ega asosiy ViewSet."""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]


# ---------- Tuzilma (spravochnik) ----------

class OrganizationViewSet(BaseModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    search_fields = ['name', 'inn']


class RegionViewSet(BaseModelViewSet):
    queryset = Region.objects.all()
    serializer_class = RegionSerializer
    search_fields = ['name']


class DepartmentViewSet(BaseModelViewSet):
    queryset = Department.objects.select_related('organization', 'region').all()
    serializer_class = DepartmentSerializer
    filterset_fields = ['organization', 'region']
    search_fields = ['name', 'code', 'inn']


class DirectorateViewSet(BaseModelViewSet):
    queryset = Directorate.objects.select_related('department').all()
    serializer_class = DirectorateSerializer
    filterset_fields = ['department']
    search_fields = ['name', 'code']


class DivisionViewSet(BaseModelViewSet):
    queryset = Division.objects.select_related('directorate').all()
    serializer_class = DivisionSerializer
    filterset_fields = ['directorate']
    search_fields = ['name', 'code']


class RankViewSet(BaseModelViewSet):
    queryset = Rank.objects.all()
    serializer_class = RankSerializer
    search_fields = ['name', 'code']


class GroupViewSet(BaseModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    search_fields = ['name']


class CategoryViewSet(BaseModelViewSet):
    queryset = Category.objects.select_related('group').all()
    serializer_class = CategorySerializer
    filterset_fields = ['group']
    search_fields = ['name']


class StructureCategoryViewSet(BaseModelViewSet):
    queryset = StructureCategory.objects.all()
    serializer_class = StructureCategorySerializer
    search_fields = ['name']


class UnitViewSet(BaseModelViewSet):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    search_fields = ['name']


class MaterialCategoryViewSet(BaseModelViewSet):
    queryset = MaterialCategory.objects.all()
    serializer_class = MaterialCategorySerializer
    search_fields = ['name']


class GoalViewSet(BaseModelViewSet):
    queryset = Goal.objects.all()
    serializer_class = GoalSerializer
    filterset_fields = ['type']
    search_fields = ['name']


class ContractViewSet(BaseModelViewSet):
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer
    search_fields = ['name']


# ---------- Rol ----------

class RolViewSet(BaseModelViewSet):
    queryset = Rol.objects.select_related('employee').all()
    serializer_class = RolSerializer
    filterset_fields = ['employee']


# ---------- Xodim ----------

class EmployeeViewSet(BaseModelViewSet):
    queryset = Employee.objects.select_related(
        'organization', 'department', 'directorate', 'division', 'rank', 'region', 'rol'
    ).all()
    serializer_class = EmployeeSerializer
    filterset_fields = ['organization', 'department', 'directorate', 'division', 'rank', 'region']
    search_fields = ['last_name', 'first_name', 'father_name', 'phone', 'pinfl']
    ordering_fields = ['date_creat', 'last_name']


# ---------- Texnika ----------

class TechnicsViewSet(BaseModelViewSet):
    queryset = Technics.objects.select_related(
        'group', 'category', 'region', 'organization', 'department',
        'directorate', 'division', 'employee'
    ).all()
    serializer_class = TechnicsSerializer
    filterset_fields = [
        'group', 'category', 'region', 'organization', 'department',
        'directorate', 'division', 'employee', 'status', 'is_active',
    ]
    search_fields = ['name', 'inventory', 'serial', 'mac', 'ip']
    ordering_fields = ['date_creat', 'price']


class StructureViewSet(BaseModelViewSet):
    queryset = Structure.objects.select_related('category', 'organization', 'region', 'technics').all()
    serializer_class = StructureSerializer
    filterset_fields = ['category', 'organization', 'region', 'status', 'is_active']
    search_fields = ['name', 'inventory', 'serial']


# ---------- Material ----------

class MaterialViewSet(BaseModelViewSet):
    queryset = Material.objects.select_related('category', 'organization', 'employee', 'unit').all()
    serializer_class = MaterialSerializer
    filterset_fields = ['category', 'organization', 'employee', 'unit', 'is_active']
    search_fields = ['name', 'code']


class MaterialEmployeeViewSet(BaseModelViewSet):
    queryset = MaterialEmployee.objects.select_related('employee', 'category').all()
    serializer_class = MaterialEmployeeSerializer
    filterset_fields = ['employee', 'category']


class MaterialMovementViewSet(BaseModelViewSet):
    queryset = MaterialMovement.objects.select_related('user', 'material', 'employee').all()
    serializer_class = MaterialMovementSerializer
    filterset_fields = ['user', 'material', 'employee', 'status']
    ordering_fields = ['date_creat']


# ---------- Ariza (Order) ----------

class OrderViewSet(BaseModelViewSet):
    queryset = Order.objects.select_related(
        'organization', 'goal', 'sender', 'receiver', 'user', 'technics'
    ).prefetch_related('materials').all()
    filterset_fields = ['organization', 'goal', 'sender', 'receiver', 'user', 'status']
    ordering_fields = ['date_creat', 'date_edit']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return OrderCreateSerializer
        return OrderSerializer


class OrderMaterialViewSet(BaseModelViewSet):
    queryset = OrderMaterial.objects.select_related('order', 'user', 'material').all()
    serializer_class = OrderMaterialSerializer
    filterset_fields = ['order', 'user', 'material']


class OrderGoalViewSet(BaseModelViewSet):
    queryset = OrderGoal.objects.select_related('employee', 'goal').all()
    serializer_class = OrderGoalSerializer
    filterset_fields = ['employee', 'goal']


class MaterialUserViewSet(BaseModelViewSet):
    queryset = MaterialUser.objects.select_related('sender', 'receiver').all()
    serializer_class = MaterialUserSerializer
    filterset_fields = ['sender', 'receiver']


# ---------- Xujat (Deed) ----------

class DeedViewSet(BaseModelViewSet):
    queryset = Deed.objects.select_related('sender', 'receiver', 'user', 'order').all()
    serializer_class = DeedSerializer
    filterset_fields = ['sender', 'receiver', 'user', 'order', 'status', 'status_sender', 'status_receiver']
    search_fields = ['code']


class DeedConsentViewSet(BaseModelViewSet):
    queryset = DeedConsent.objects.select_related('deed', 'employee').all()
    serializer_class = DeedConsentSerializer
    filterset_fields = ['deed', 'employee', 'status']


class LiableViewSet(BaseModelViewSet):
    queryset = Liable.objects.select_related('employee', 'contract', 'category').all()
    serializer_class = LiableSerializer
    filterset_fields = ['employee', 'contract', 'category']