from rest_framework import serializers
from main.models import *


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name', 'contract', 'inn', 'type']


class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ['id', 'name']


class DepartmentSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)

    class Meta:
        model = Department
        fields = ['id', 'organization_id', 'organization_name', 'region', 'region_name', 'code', 'inn', 'name']


class DirectorateSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = Directorate
        fields = ['id', 'department', 'department_name', 'code', 'name']


class DivisionSerializer(serializers.ModelSerializer):
    directorate_name = serializers.CharField(source='directorate.name', read_only=True)

    class Meta:
        model = Division
        fields = ['id', 'directorate', 'directorate_name', 'code', 'name']


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['id', 'name']


class ContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = ['id', 'name', 'unit', 'price']


class CategorySerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True)
    contract_name = serializers.CharField(source='contract.name', read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'group', 'group_name', 'contract', 'contract_name', 'name']


class TechnicsSerializer(serializers.ModelSerializer):
    """Ko'rish uchun — to'liq ma'lumot (read-only)."""
    group_name = serializers.CharField(source='group.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    directorate_name = serializers.CharField(source='directorate.name', read_only=True)
    division_name = serializers.CharField(source='division.name', read_only=True)
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Technics
        fields = [
            'id', 'group', 'group_name', 'category', 'category_name',
            'region', 'region_name', 'organization', 'organization_name',
            'department', 'department_name', 'directorate', 'directorate_name',
            'division', 'division_name', 'employee', 'employee_name',
            'status', 'status_display', 'name', 'parametr', 'inventory',
            'serial', 'mac', 'ip', 'price', 'year', 'address',
            'is_active', 'qr_code', 'date_creat', 'date_edit',
        ]


class TechnicsCreateUpdateSerializer(serializers.ModelSerializer):
    """Qo'shish va tahrirlash uchun — faqat texnika ma'lumotlari."""

    class Meta:
        model = Technics
        fields = [
            'group', 'category', 'organization', 'region',
            'name', 'parametr', 'inventory', 'serial',
            'mac', 'ip', 'price', 'year', 'address',
        ]


class TechnicsAssignSerializer(serializers.ModelSerializer):
    """Biriktirish uchun — faqat tashkiliy struktura va xodim."""

    class Meta:
        model = Technics
        fields = ['employee', 'department', 'directorate', 'division']


class StructureCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = StructureCategory
        fields = ['id', 'name']


class StructureSerializer(serializers.ModelSerializer):
    """Ko'rish uchun — to'liq ma'lumot (read-only)."""
    category_name = serializers.CharField(source='category.name', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)
    technics_name = serializers.CharField(source='technics.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Structure
        fields = [
            'id', 'category', 'category_name', 'organization', 'organization_name',
            'region', 'region_name', 'technics', 'technics_name',
            'status', 'status_display', 'name', 'parametr', 'inventory',
            'serial', 'price', 'year', 'is_active', 'date_creat', 'date_edit',
        ]


class StructureCreateUpdateSerializer(serializers.ModelSerializer):
    """Qo'shish va tahrirlash uchun."""

    class Meta:
        model = Structure
        fields = [
            'category', 'organization', 'region', 'name',
            'parametr', 'inventory', 'serial', 'price', 'year',
        ]


class StructureAssignSerializer(serializers.ModelSerializer):
    """Biriktirish uchun — faqat texnika maydoni."""

    class Meta:
        model = Structure
        fields = ['technics']


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ['id', 'name']


class MaterialCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialCategory
        fields = ['id', 'name']


class MaterialSerializer(serializers.ModelSerializer):
    """Ko'rish uchun — to'liq ma'lumot (read-only)."""
    category_name = serializers.CharField(source='category.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)

    class Meta:
        model = Material
        fields = [
            'id', 'category', 'category_name',
            'employee', 'employee_name', 'unit', 'unit_name',
            'name', 'number', 'code', 'price', 'year',
            'image', 'date_creat', 'date_edit',
        ]


class MaterialCreateUpdateSerializer(serializers.ModelSerializer):
    """Qo'shish va tahrirlash uchun. organization va employee foydalanuvchidan
    olinmaydi — view ichida (perform_create) avtomatik belgilanadi."""

    class Meta:
        model = Material
        fields = [
            'category', 'unit', 'name', 'number',
            'code', 'price', 'year', 'image',
        ]


class MaterialGiveItemSerializer(serializers.Serializer):
    material_id = serializers.IntegerField()
    number = serializers.IntegerField(min_value=1)


class MaterialGiveSerializer(serializers.Serializer):
    """Materialni(larni) boshqa xodimga berish uchun — bitta yoki bir nechta material."""
    employee_id = serializers.IntegerField()
    items = MaterialGiveItemSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("Kamida bitta material tanlanishi kerak.")
        ids = [item['material_id'] for item in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Bir xil material savatda takrorlangan.")
        return value


class MaterialEmployeeSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = MaterialEmployee
        fields = ['id', 'employee', 'employee_name', 'category', 'category_name']


class GoalSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)

    class Meta:
        model = Goal
        fields = ['id', 'organization', 'organization_name', 'name']


# Arizalar
class OrderMaterialSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source='material.name', read_only=True)
    unit_name = serializers.CharField(source='material.unit.name', read_only=True)
    given_summa = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = OrderMaterial
        fields = ['id', 'material', 'material_name', 'unit_name', 'number', 'given', 'given_summa']


class OrderMaterialGivenSerializer(serializers.Serializer):
    """OrderMaterial given sonini tahrirlash uchun."""
    given = serializers.IntegerField(min_value=1)


class OrderMaterialUpdateSerializer(serializers.Serializer):
    """OrderMaterial given sonini tahrirlash uchun."""
    number = serializers.IntegerField(min_value=1)


class OrderSerializer(serializers.ModelSerializer):
    goal_name = serializers.CharField(source='goal.name', read_only=True)
    goal_organization_id = serializers.IntegerField(source='goal.organization_id', read_only=True)
    goal_organization_name = serializers.CharField(source='goal.organization.name', read_only=True)
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    receiver_name = serializers.CharField(source='receiver.full_name', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    technics_name = serializers.CharField(source='technics.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    materials = OrderMaterialSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'goal_organization_id', 'goal_organization_name', 'goal', 'goal_name',
            'sender', 'sender_name', 'message_sender',
            'technics', 'technics_name', 'rating',
            'receiver', 'receiver_name', 'message_receiver',
            'user', 'user_name', 'message_user',
            'status', 'status_display',
            'receiver_seen', 'sender_seen', 'user_seen',
            'date_creat', 'date_edit',
            'date_process', 'date_finished', 'date_approved',
            'date_accepted', 'date_canceled', 'date_rejected',
            'materials',
        ]


class OrderCreateItemSerializer(serializers.Serializer):
    material_id = serializers.IntegerField()
    number = serializers.IntegerField(min_value=1)


class OrderCreateSerializer(serializers.ModelSerializer):
    """Ariza yuborish uchun. sender avtomatik so'rov yuborgan xodimdan olinadi.
    materials — ixtiyoriy, so'ralayotgan materiallar ro'yxati (ombordan hali
    ayirilmaydi, faqat so'rov sifatida saqlanadi)."""

    materials = OrderCreateItemSerializer(many=True, required=False, default=list)

    class Meta:
        model = Order
        fields = ['goal', 'message_sender', 'materials']


class OrderFinishSerializer(serializers.Serializer):
    """Arizani yakunlash uchun — faqat texnika (ixtiyoriy).
    Materiallar alohida /materials/ endpoint orqali qo'shiladi."""
    technics_id = serializers.IntegerField(required=False, allow_null=True, default=None)


class OrderMaterialAddSerializer(serializers.Serializer):
    """Arizaga material qo'shish/berish uchun.
    Agar material arizada mavjud bo'lsa — given yoziladi.
    Mavjud bo'lmasa — yangi OrderMaterial yaratiladi (given bilan)."""
    material_id = serializers.IntegerField()
    number = serializers.IntegerField(min_value=1)


class OrderDecideSerializer(serializers.Serializer):
    """
    Arizani hal qilish uchun.
    approved  — material o'zgarishsiz qoladi.
    rejected/canceled — arizadagi materiallar omborga qaytariladi.
    """
    action = serializers.ChoiceField(choices=["approved", "canceled", "rejected"])


class OrderAcceptedSerializer(serializers.Serializer):
    """Ishni yakuniy qabul qilish — reyting shu yerda majburiy kiritiladi.
    Material o'zgarishsiz qoladi (haqiqatda berilgan hisoblanadi)."""
    rating = serializers.IntegerField(min_value=1, max_value=5)


class OrderGoalSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    goal_name = serializers.CharField(source='goal.name', read_only=True)

    class Meta:
        model = OrderGoal
        fields = ['id', 'employee', 'employee_name', 'goal', 'goal_name']


class MaterialUserSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    receiver_name = serializers.CharField(source='receiver.full_name', read_only=True)

    class Meta:
        model = MaterialUser
        fields = ['id', 'sender', 'sender_name', 'receiver', 'receiver_name']


class DeedConsentSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = DeedConsent
        fields = [
            'id', 'deed', 'employee', 'employee_name', 'message',
            'status', 'status_display', 'date_creat', 'date_edit',
        ]


class DeedSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    receiver_name = serializers.CharField(source='receiver.full_name', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    status_sender_display = serializers.CharField(source='get_status_sender_display', read_only=True)
    status_receiver_display = serializers.CharField(source='get_status_receiver_display', read_only=True)
    consents = DeedConsentSerializer(source='deedconsent_set', many=True, read_only=True)

    class Meta:
        model = Deed
        fields = [
            'id', 'organization', 'organization_name',
            'sender', 'sender_name', 'message_sender', 'status_sender', 'status_sender_display', 'date_sender',
            'receiver', 'receiver_name', 'message_receiver', 'status_receiver', 'status_receiver_display', 'date_receiver',
            'user', 'user_name', 'user_edit', 'message_user',
            'body', 'status', 'status_display', 'file', 'code', 'order',
            'date_creat', 'date_edit', 'consents',
        ]
        read_only_fields = ['code']


class LiableSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    contract_name = serializers.CharField(source='contract.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Liable
        fields = ['id', 'employee', 'employee_name', 'contract', 'contract_name', 'category', 'category_name']


class MaterialMovementSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    material_name = serializers.CharField(source='material.name', read_only=True)
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = MaterialMovement
        fields = [
            'id', 'user', 'user_name', 'material', 'material_name',
            'employee', 'employee_name', 'income', 'outcome',
            'status', 'status_display', 'body', 'date_creat',
        ]