# !!! DIQQAT !!!
# Quyidagi import yo'lini o'zingizning asosiy (models.py joylashgan) app nomiga
# moslab o'zgartiring. Masalan agar app nomi "main" bo'lsa - shu holicha qoldiring,
# agar "core", "inventory" va h.k. bo'lsa - shunga almashtiring.
from main.models import (
    Organization, Region, Department, Directorate, Division, Rank, Rol,
    Employee, Group, Category, Technics, StructureCategory, Structure,
    Unit, MaterialCategory, Material, MaterialEmployee, Goal, Order,
    OrderMaterial, OrderGoal, MaterialUser, Deed, DeedConsent, Contract,
    Liable, MaterialMovement,
)
from rest_framework import serializers


# ---------- Tuzilma (spravochnik) modellari ----------

class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = '__all__'


class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = '__all__'


class DepartmentSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)

    class Meta:
        model = Department
        fields = '__all__'


class DirectorateSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = Directorate
        fields = '__all__'


class DivisionSerializer(serializers.ModelSerializer):
    directorate_name = serializers.CharField(source='directorate.name', read_only=True)

    class Meta:
        model = Division
        fields = '__all__'


class RankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rank
        fields = '__all__'


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = '__all__'


class CategorySerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True)

    class Meta:
        model = Category
        fields = '__all__'


class StructureCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = StructureCategory
        fields = '__all__'


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = '__all__'


class MaterialCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialCategory
        fields = '__all__'


class GoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Goal
        fields = '__all__'


class ContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = '__all__'


# ---------- Rol ----------

class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rol
        fields = '__all__'


# ---------- Xodim ----------

class EmployeeSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    directorate_name = serializers.CharField(source='directorate.name', read_only=True)
    division_name = serializers.CharField(source='division.name', read_only=True)
    rank_name = serializers.CharField(source='rank.name', read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)
    rol = RolSerializer(read_only=True)

    class Meta:
        model = Employee
        fields = '__all__'


class EmployeeShortSerializer(serializers.ModelSerializer):
    """Boshqa serializerlar ichida nested ko'rsatish uchun qisqartirilgan variant."""
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Employee
        fields = ['id', 'full_name', 'phone']


# ---------- Texnika ----------

class TechnicsSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    directorate_name = serializers.CharField(source='directorate.name', read_only=True)
    division_name = serializers.CharField(source='division.name', read_only=True)
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    qr_code_url = serializers.SerializerMethodField()

    class Meta:
        model = Technics
        fields = '__all__'
        read_only_fields = ['qr_code']

    def get_qr_code_url(self, obj):
        request = self.context.get('request')
        if obj.qr_code and hasattr(obj.qr_code, 'url'):
            return request.build_absolute_uri(obj.qr_code.url) if request else obj.qr_code.url
        return None


class StructureSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Structure
        fields = '__all__'


# ---------- Material ----------

class MaterialSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)

    class Meta:
        model = Material
        fields = '__all__'


class MaterialEmployeeSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = MaterialEmployee
        fields = '__all__'


class MaterialMovementSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    material_name = serializers.CharField(source='material.name', read_only=True)
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = MaterialMovement
        fields = '__all__'


# ---------- Ariza (Order) ----------

class OrderMaterialSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source='material.name', read_only=True)
    material_price = serializers.DecimalField(source='material.price', max_digits=12, decimal_places=2, read_only=True)
    given_summa = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = OrderMaterial
        fields = '__all__'


class OrderSerializer(serializers.ModelSerializer):
    materials = OrderMaterialSerializer(many=True, read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    goal_name = serializers.CharField(source='goal.name', read_only=True)
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    receiver_name = serializers.CharField(source='receiver.full_name', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    technics_name = serializers.CharField(source='technics.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Order
        fields = '__all__'


class OrderCreateSerializer(serializers.ModelSerializer):
    """Ariza yaratish/tahrirlash uchun soddalashtirilgan serializer (nested materials'siz)."""

    class Meta:
        model = Order
        fields = '__all__'


class OrderGoalSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    goal_name = serializers.CharField(source='goal.name', read_only=True)

    class Meta:
        model = OrderGoal
        fields = '__all__'


class MaterialUserSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    receiver_name = serializers.CharField(source='receiver.full_name', read_only=True)

    class Meta:
        model = MaterialUser
        fields = '__all__'


# ---------- Xujat (Deed) ----------

class DeedConsentSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = DeedConsent
        fields = '__all__'


class DeedSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    receiver_name = serializers.CharField(source='receiver.full_name', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    status_sender_display = serializers.CharField(source='get_status_sender_display', read_only=True)
    status_receiver_display = serializers.CharField(source='get_status_receiver_display', read_only=True)
    consents = DeedConsentSerializer(many=True, read_only=True, source='deedconsent_set')

    class Meta:
        model = Deed
        fields = '__all__'
        read_only_fields = ['code']


class LiableSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    contract_name = serializers.CharField(source='contract.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Liable
        fields = '__all__'