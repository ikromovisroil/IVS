from rest_framework import serializers
from .models import *


# ---- SIMPLE SERIALIZERS ---- #

class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = '__all__'


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = '__all__'


class DirectorateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Directorate
        fields = '__all__'


class DivisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Division
        fields = '__all__'


class RankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rank
        fields = '__all__'


class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = '__all__'


# ---- EMPLOYEE ---- #

class EmployeeSerializer(serializers.ModelSerializer):
    user_fullname = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = Employee
        fields = '__all__'


# ---- CATEGORY ---- #

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


# ---- TECHNICS ---- #

class TechnicsSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.get_full_name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Technics
        fields = '__all__'


# ---- MATERIAL ---- #

class MaterialSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.get_full_name", read_only=True)

    class Meta:
        model = Material
        fields = '__all__'


# ---- TOPIC ---- #

class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = '__all__'


# ---- GOAL ---- #

class GoalSerializer(serializers.ModelSerializer):
    topic_name = serializers.CharField(source="topic.name", read_only=True)

    class Meta:
        model = Goal
        fields = '__all__'


# ---- ORDER MATERIAL ---- #

class OrderMaterialSerializer(serializers.ModelSerializer):
    technics_name = serializers.CharField(source="technics.name", read_only=True)
    material_name = serializers.CharField(source="material.name", read_only=True)

    class Meta:
        model = OrderMaterial
        fields = '__all__'


# ---- ORDER ---- #

class OrderSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.user.get_full_name", read_only=True)
    receiver_name = serializers.CharField(source="receiver.user.get_full_name", read_only=True)
    materials = OrderMaterialSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = '__all__'



class DeedSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.user.get_full_name", read_only=True)
    receiver_name = serializers.CharField(source="receiver.user.get_full_name", read_only=True)

    class Meta:
        model = Deed
        fields = '__all__'
