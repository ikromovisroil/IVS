from rest_framework import serializers
from .models import *

class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "contract", "slug"]


class DepartmentSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = Department
        fields = ["id", "organization", "organization_name", "name", "slug"]


class DirectorateSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Directorate
        fields = ["id", "department", "department_name", "name", "slug"]


class DivisionSerializer(serializers.ModelSerializer):
    directorate_name = serializers.CharField(source="directorate.name", read_only=True)

    class Meta:
        model = Division
        fields = ["id", "directorate", "directorate_name", "name", "slug"]


class RankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rank
        fields = ["id", "name"]


class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ["id", "name"]


class RolSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        model = Rol
        fields = [
            "id", "employee", "employee_name",
            "client", "order", "boss", "shop", "akt", "status",
            "technics", "technics_edit", "material", "material_edit",
        ]


class EmployeeSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    directorate_name = serializers.CharField(source="directorate.name", read_only=True)
    division_name = serializers.CharField(source="division.name", read_only=True)
    rank_name = serializers.CharField(source="rank.name", read_only=True)
    region_name = serializers.CharField(source="region.name", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id", "user", "username",
            "last_name", "first_name", "father_name", "full_name",
            "organization", "organization_name",
            "department", "department_name",
            "directorate", "directorate_name",
            "division", "division_name",
            "rank", "rank_name",
            "region", "region_name",
            "phone", "pinfl",
            "date_creat", "date_edit",
        ]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class TechnicsSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    directorate_name = serializers.CharField(source="directorate.name", read_only=True)
    division_name = serializers.CharField(source="division.name", read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        model = Technics
        fields = [
            "id",
            "category", "category_name",
            "organization", "organization_name",
            "department", "department_name",
            "directorate", "directorate_name",
            "division", "division_name",
            "employee", "employee_name",
            "status",
            "name", "parametr", "inventory", "serial", "mac", "ip",
            "price", "year", "is_active",
            "date_creat", "date_edit",
        ]


class ExtraCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = StructureCategory
        fields = ["id", "name", "slug"]


class ExtraTechnicsSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    technics_name = serializers.CharField(source="technics.name", read_only=True)

    class Meta:
        model = Structure
        fields = [
            "id",
            "category", "category_name",
            "organization", "organization_name",
            "technics", "technics_name",
            "status",
            "name", "parametr", "inventory", "serial",
            "price", "year", "is_active",
            "date_creat", "date_edit",
        ]


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ["id", "name"]


class MaterialSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    unit_name = serializers.CharField(source="unit.name", read_only=True)

    class Meta:
        model = Material
        fields = [
            "id",
            "employee", "employee_name",
            "unit", "unit_name",
            "status",
            "name", "number", "code", "price", "year",
            "is_active", "date_creat", "date_edit",
        ]


class GoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Goal
        fields = ["id", "name"]


class OrderMaterialSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source="material.name", read_only=True)

    class Meta:
        model = OrderMaterial
        fields = ["id", "order", "material", "material_name", "number"]


class OrderSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.full_name", read_only=True)
    receiver_name = serializers.CharField(source="receiver.full_name", read_only=True)
    goal_name = serializers.CharField(source="goal.name", read_only=True)
    technics_name = serializers.CharField(source="technics.name", read_only=True)
    materials = OrderMaterialSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "sender", "sender_name",
            "goal", "goal_name",
            "body", "rating",
            "receiver", "receiver_name",
            "technics", "technics_name",
            "status", "receiver_seen",
            "date_creat", "date_edit",
            "date_accepted", "date_finished", "date_approved", "date_rejected",
            "materials",
        ]


class DeedSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.full_name", read_only=True)
    receiver_name = serializers.CharField(source="receiver.full_name", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = Deed
        fields = [
            "id",
            "sender", "sender_name",
            "message_sender", "status_sender", "date_sender", "sender_seen",
            "receiver", "receiver_name",
            "message_receiver", "status_receiver", "date_receiver", "receiver_seen",
            "user", "user_name",
            "message_user", "body", "file_type", "file",
            "date_creat", "date_edit",
        ]


class DeedConsentSerializer(serializers.ModelSerializer):
    deed_name = serializers.CharField(source="deed.__str__", read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        model = DeedConsent
        fields = [
            "id", "deed", "deed_name",
            "employee", "employee_name",
            "message", "status",
            "date_creat", "date_edit",
        ]


class ContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = ["id", "name", "unit", "price"]


class LiableSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    contract_name = serializers.CharField(source="contract.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Liable
        fields = [
            "id",
            "employee", "employee_name",
            "contract", "contract_name",
            "category", "category_name",
        ]