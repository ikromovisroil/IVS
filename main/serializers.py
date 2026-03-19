from rest_framework import serializers
from main.models import *


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = "__all__"


class DepartmentSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = Department
        fields = "__all__"


class DirectorateSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Directorate
        fields = "__all__"


class DivisionSerializer(serializers.ModelSerializer):
    directorate_name = serializers.CharField(source="directorate.name", read_only=True)

    class Meta:
        model = Division
        fields = "__all__"


class RankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rank
        fields = "__all__"


class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = "__all__"


class RolSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        model = Rol
        fields = "__all__"


class EmployeeSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    directorate_name = serializers.CharField(source="directorate.name", read_only=True)
    division_name = serializers.CharField(source="division.name", read_only=True)
    rank_name = serializers.CharField(source="rank.name", read_only=True)
    region_name = serializers.CharField(source="region.name", read_only=True)
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Employee
        fields = "__all__"
        read_only_fields = ("date_creat", "date_edit", "full_name")


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = "__all__"


class CategorySerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = Category
        fields = "__all__"


class TechnicsSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    directorate_name = serializers.CharField(source="directorate.name", read_only=True)
    division_name = serializers.CharField(source="division.name", read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    qr_code_url = serializers.SerializerMethodField()
    absolute_url = serializers.SerializerMethodField()

    class Meta:
        model = Technics
        fields = "__all__"
        read_only_fields = ("date_creat", "date_edit", "qr_code")

    def get_qr_code_url(self, obj):
        request = self.context.get("request")
        if obj.qr_code and request:
            return request.build_absolute_uri(obj.qr_code.url)
        elif obj.qr_code:
            return obj.qr_code.url
        return None

    def get_absolute_url(self, obj):
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.get_absolute_url())
        return obj.get_absolute_url()


class StructureCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = StructureCategory
        fields = "__all__"


class StructureSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    technics_name = serializers.CharField(source="technics.name", read_only=True)

    class Meta:
        model = Structure
        fields = "__all__"
        read_only_fields = ("date_creat", "date_edit")


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = "__all__"


class MaterialCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialCategory
        fields = "__all__"


class MaterialSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    unit_name = serializers.CharField(source="unit.name", read_only=True)

    class Meta:
        model = Material
        fields = "__all__"
        read_only_fields = ("date_creat", "date_edit")


class GoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Goal
        fields = "__all__"


class OrderMaterialSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source="material.name", read_only=True)

    class Meta:
        model = OrderMaterial
        fields = "__all__"


class OrderSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.full_name", read_only=True)
    receiver_name = serializers.CharField(source="receiver.full_name", read_only=True)
    goal_name = serializers.CharField(source="goal.name", read_only=True)
    technics_name = serializers.CharField(source="technics.name", read_only=True)
    materials = OrderMaterialSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = "__all__"
        read_only_fields = (
            "date_creat", "date_edit",
            "date_accepted", "date_finished", "date_approved", "date_rejected"
        )


class DeedSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.full_name", read_only=True)
    receiver_name = serializers.CharField(source="receiver.full_name", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Deed
        fields = "__all__"
        read_only_fields = ("date_creat", "date_edit", "code")

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        elif obj.file:
            return obj.file.url
        return None


class DeedConsentSerializer(serializers.ModelSerializer):
    deed_code = serializers.CharField(source="deed.code", read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        model = DeedConsent
        fields = "__all__"
        read_only_fields = ("date_creat", "date_edit")


class ContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = "__all__"


class LiableSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    contract_name = serializers.CharField(source="contract.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Liable
        fields = "__all__"