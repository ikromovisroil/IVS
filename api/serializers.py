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


class RankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rank
        fields = ['id', 'code', 'name']


class EmployeeSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)
    rank_name = serializers.CharField(source='rank.name', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Employee
        fields = [
            'id', 'username', 'last_name', 'first_name', 'father_name', 'full_name',
            'organization', 'organization_name',
            'department', 'department_name',
            'directorate', 'division',
            'region', 'region_name',
            'rank', 'rank_name',
            'phone', 'pinfl',
            'date_creat', 'date_edit',
        ]
        read_only_fields = ['pinfl']


def _resolve_structure(organization, department, directorate, division):
    """
    Bo'lim/boshqarma/bo'linma zanjiri mosligini tekshiradi va yuqoriga to'ldiradi
    (Employee.save() ham shunday qiladi). Natijada bo'lim tashkilotga tegishli bo'lishi shart —
    aks holda Employee.save() xodimni boshqa tashkilotga o'tkazib yuborardi.
    """
    if division and directorate and division.directorate_id != directorate.id:
        raise serializers.ValidationError({"division": "Bo'linma tanlangan boshqarmaga tegishli emas"})
    if directorate and department and directorate.department_id != department.id:
        raise serializers.ValidationError({"directorate": "Boshqarma tanlangan bo'limga tegishli emas"})
    if division and not directorate:
        directorate = division.directorate
    if directorate and not department:
        department = directorate.department
    if department and organization and department.organization_id and department.organization_id != organization.id:
        raise serializers.ValidationError({"department": "Bo'lim bu tashkilotga tegishli emas"})
    return department, directorate, division


class EmployeeCreateSerializer(serializers.ModelSerializer):
    """Qo'shish — saytdagi employee_create bilan bir xil maydonlar (User view ichida yaratiladi)."""

    class Meta:
        model = Employee
        fields = [
            'pinfl', 'first_name', 'last_name', 'father_name', 'organization',
            'department', 'directorate', 'division', 'rank', 'phone',
        ]
        extra_kwargs = {
            'first_name': {'required': True, 'allow_blank': False, 'allow_null': False},
            'last_name': {'required': True, 'allow_blank': False, 'allow_null': False},
            'organization': {'required': True, 'allow_null': False},
        }

    def validate_pinfl(self, value):
        value = (value or "").strip()
        if value and Employee.objects.filter(pinfl=value).exists():
            raise serializers.ValidationError("Bu PINFL bilan xodim allaqachon mavjud")
        return value or None

    def validate(self, attrs):
        _resolve_structure(
            attrs.get('organization'), attrs.get('department'),
            attrs.get('directorate'), attrs.get('division'),
        )
        return attrs

    def to_representation(self, instance):
        return EmployeeSerializer(instance, context=self.context).data


class EmployeeUpdateSerializer(serializers.ModelSerializer):
    """Tahrirlash — saytdagi employee_update bilan bir xil (tashkilot o'zgarmaydi)."""
    technics_action = serializers.ChoiceField(
        choices=['with', 'stay', 'release'], required=False, write_only=True,
        help_text="Joylashuv o'zgarsa xodimdagi texnikalar: with — birga ko'chadi, "
                  "stay — eski joyda qoladi, release — bo'shatiladi (standart)",
    )

    class Meta:
        model = Employee
        fields = [
            'pinfl', 'first_name', 'last_name', 'father_name',
            'department', 'directorate', 'division', 'rank', 'phone', 'technics_action',
        ]
        extra_kwargs = {
            'first_name': {'allow_blank': False, 'allow_null': False},
            'last_name': {'allow_blank': False, 'allow_null': False},
            'pinfl': {'allow_blank': False, 'allow_null': False},
        }

    def validate_pinfl(self, value):
        value = (value or "").strip()
        if not value.isdigit() or len(value) != 14:
            raise serializers.ValidationError("PINFL 14 xonali raqamdan iborat bo'lishi kerak")
        if Employee.objects.filter(pinfl=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("Bu PINFL boshqa xodimga tegishli")
        return value

    def validate(self, attrs):
        inst = self.instance
        dep = attrs.get('department', inst.department)
        drt = attrs.get('directorate', inst.directorate)
        div = attrs.get('division', inst.division)

        # Yuqori daraja o'zgargan, past daraja berilmagan bo'lsa — eskisi mos kelmaydi, tozalanadi
        if 'department' in attrs and 'directorate' not in attrs and drt and (not dep or drt.department_id != dep.id):
            drt = attrs['directorate'] = None
        if 'directorate' in attrs and 'division' not in attrs and div and (not drt or div.directorate_id != drt.id):
            div = attrs['division'] = None
        if drt is None and 'directorate' in attrs and div and 'division' not in attrs:
            div = attrs['division'] = None

        _resolve_structure(inst.organization, dep, drt, div)
        return attrs

    def to_representation(self, instance):
        return EmployeeSerializer(instance, context=self.context).data


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
    contract_names = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'group', 'group_name', 'contracts', 'contract_names', 'name']

    def get_contract_names(self, obj):
        return [c.name for c in obj.contracts.all()]


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
    extra_devices = serializers.SerializerMethodField()

    class Meta:
        model = Technics
        fields = [
            'id', 'group', 'group_name', 'category', 'category_name',
            'region', 'region_name', 'organization', 'organization_name',
            'department', 'department_name', 'directorate', 'directorate_name',
            'division', 'division_name', 'employee', 'employee_name',
            'status', 'status_display', 'name', 'parametr', 'inventory',
            'serial', 'mac', 'ip', 'price', 'year', 'address',
            'is_active', 'is_online', 'qr_code', 'date_creat', 'date_edit', 'extra_devices',
        ]

    def get_extra_devices(self, obj):
        items = getattr(obj, 'active_structures', None)
        if items is None:
            items = obj.structure_set.filter(is_active=True)
        return [
            {'id': x.id, 'name': x.name, 'serial': x.serial, 'inventory': x.inventory, 'status': x.status}
            for x in items
        ]


class TechnicsCreateSerializer(serializers.ModelSerializer):
    """Qo'shish — saytdagi TechnicsForm bilan bir xil maydonlar (hudud xodimdan olinadi)."""

    class Meta:
        model = Technics
        fields = [
            'group', 'category', 'organization', 'name',
            'parametr', 'inventory', 'serial', 'mac', 'ip',
            'year', 'price', 'address', 'is_online',
        ]
        extra_kwargs = {
            'group': {'required': True, 'allow_null': False},
            'category': {'required': True, 'allow_null': False},
            'organization': {'required': True, 'allow_null': False},
        }

    def to_representation(self, instance):
        # Javobda id va barcha ko'rsatish maydonlari qaytsin (ilova yaratilgan obyektni darhol ko'rsatadi)
        return TechnicsSerializer(instance, context=self.context).data


class TechnicsUpdateSerializer(serializers.ModelSerializer):
    """Tahrirlash — saytdagi technics_update bilan bir xil maydonlar (guruh va hudud o'zgarmaydi)."""

    class Meta:
        model = Technics
        fields = [
            'category', 'organization', 'name',
            'parametr', 'inventory', 'serial', 'mac', 'ip',
            'year', 'price', 'address', 'status', 'is_online',
        ]

    def to_representation(self, instance):
        # Javobda id va barcha ko'rsatish maydonlari qaytsin (ilova yaratilgan obyektni darhol ko'rsatadi)
        return TechnicsSerializer(instance, context=self.context).data


class TechnicsAssignSerializer(serializers.Serializer):
    """Biriktirish: xodimga YOKI strukturaga. Hech narsa berilmasa — bo'shatiladi (saytdagidek)."""
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all(), required=False, allow_null=True)
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), required=False, allow_null=True)
    directorate = serializers.PrimaryKeyRelatedField(queryset=Directorate.objects.all(), required=False, allow_null=True)
    division = serializers.PrimaryKeyRelatedField(queryset=Division.objects.all(), required=False, allow_null=True)


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


class StructureCreateSerializer(serializers.ModelSerializer):
    """Qo'shish — saytdagi ExtraTechnicsForm bilan bir xil (hudud xodimdan olinadi)."""

    class Meta:
        model = Structure
        fields = ['category', 'organization', 'name', 'parametr', 'inventory', 'serial', 'price', 'year']
        extra_kwargs = {
            'category': {'required': True, 'allow_null': False},
            'organization': {'required': True, 'allow_null': False},
        }

    def validate_price(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Narx manfiy bo'lishi mumkin emas")
        return value

    def to_representation(self, instance):
        return StructureSerializer(instance, context=self.context).data


class StructureUpdateSerializer(serializers.ModelSerializer):
    """Tahrirlash — saytdagi extra_tex_update bilan bir xil (hudud o'zgarmaydi)."""

    class Meta:
        model = Structure
        fields = ['category', 'organization', 'name', 'parametr', 'inventory', 'serial', 'price', 'year', 'status']

    def validate_price(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Narx manfiy bo'lishi mumkin emas")
        return value

    def to_representation(self, instance):
        return StructureSerializer(instance, context=self.context).data


class StructureAssignSerializer(serializers.Serializer):
    """Texnikaga biriktirish uchun."""
    technics = serializers.PrimaryKeyRelatedField(queryset=Technics.objects.all())


class StructureUnassignSerializer(serializers.Serializer):
    """Ajratish: texnika berilsa, qurilma aynan shu texnikaga tegishliligi tekshiriladi (saytdagidek)."""
    technics = serializers.PrimaryKeyRelatedField(queryset=Technics.objects.all(), required=False)


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
    olinmaydi — view ichida (perform_create) avtomatik belgilanadi.
    Qoidalar saytdagi (material_create / material_update) bilan bir xil."""

    class Meta:
        model = Material
        fields = [
            'category', 'unit', 'name', 'number',
            'code', 'price', 'year', 'image',
        ]

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Nomi kiritilishi shart")
        return value

    def validate_code(self, value):
        return (value or "").strip() or None

    def validate_year(self, value):
        return (value or "").strip() or None

    def validate_price(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Narx manfiy bo'lishi mumkin emas")
        return value

    def validate_category(self, value):
        """Kategoriya o'z tashkilotiniki (yoki umumiy) bo'lishi kerak."""
        if value is None:
            return value
        request = self.context.get('request')
        employee = getattr(getattr(request, 'user', None), 'employee', None)
        if value.organization_id and employee and value.organization_id != employee.organization_id:
            raise serializers.ValidationError("Bu kategoriya sizning tashkilotingizga tegishli emas")
        return value

    def validate_image(self, value):
        """Faqat JPG/PNG, 5 MB gacha va haqiqatan rasm (saytdagi bilan bir xil)."""
        if value is None:
            return value
        from django.core.exceptions import ValidationError as DjangoValidationError
        from main.validators import validate_material_image
        try:
            validate_material_image(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def to_representation(self, instance):
        return MaterialSerializer(instance, context=self.context).data


class MaterialServiceSerializer(serializers.Serializer):
    """Materialni sarflash (xizmat ko'rsatish) uchun."""
    material_id = serializers.IntegerField()
    give_number = serializers.IntegerField(min_value=1)
    body = serializers.CharField(required=False, allow_blank=True, default="")


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
    category_names = serializers.SerializerMethodField()

    class Meta:
        model = MaterialEmployee
        fields = ['id', 'employee', 'employee_name', 'category', 'category_names']

    def get_category_names(self, obj):
        return [c.name for c in obj.category.all()]


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
    deeds = serializers.SerializerMethodField()

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
            'materials', 'deeds',
        ]

    def get_deeds(self, obj):
        request = self.context.get('request')
        out = []
        for d in obj.deeds.all():
            url = None
            if d.file:
                url = request.build_absolute_uri(d.file.url) if request else d.file.url
            out.append({'id': d.id, 'code': d.code, 'file': url})
        return out


class OrderCreateItemSerializer(serializers.Serializer):
    material_id = serializers.IntegerField()
    number = serializers.IntegerField(min_value=1)


class OrderCreateSerializer(serializers.ModelSerializer):
    """Ariza yuborish uchun. sender avtomatik so'rov yuborgan xodimdan olinadi.
    materials — ixtiyoriy, so'ralayotgan materiallar ro'yxati (ombordan hali
    ayirilmaydi, faqat so'rov sifatida saqlanadi)."""

    materials = OrderCreateItemSerializer(many=True, required=False)
    sender = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), required=False,
        help_text="Boshqa xodim nomidan ariza yuborish ('add_order' huquqi kerak); ATM arizasi uchun",
    )

    class Meta:
        model = Order
        fields = ['goal', 'message_sender', 'materials', 'sender']


class OrderMaterialAddSerializer(serializers.Serializer):
    """Arizaga material qo'shish/berish uchun.
    Agar material arizada mavjud bo'lsa — given yoziladi.
    Mavjud bo'lmasa — yangi OrderMaterial yaratiladi (given bilan)."""
    material_id = serializers.IntegerField()
    number = serializers.IntegerField(min_value=1)


class OrderGivenItemSerializer(serializers.Serializer):
    """Material arizasi: arizadagi material (ordermaterial_id) bo'yicha beriladigan miqdor."""
    ordermaterial_id = serializers.IntegerField()
    given = serializers.IntegerField(min_value=0)


class OrderConfirmSerializer(serializers.Serializer):
    """Tasdiqlovchi (confirm_order): approved — beriladigan sonlar bilan; rejected — materiallar omborga qaytariladi."""
    action = serializers.ChoiceField(choices=["approved", "rejected"])
    items = OrderGivenItemSerializer(many=True, required=False)


class OrderFinishSerializer(serializers.Serializer):
    """Arizani yakunlash: texnika (ixtiyoriy) va (ATM arizasi uchun) berilgan materiallar ro'yxati."""
    technics_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    materials = OrderMaterialAddSerializer(many=True, required=False)
    # Material arizasi (omborxona) uchun: arizadagi har bir material bo'yicha beriladigan son
    items = OrderGivenItemSerializer(many=True, required=False)
    date = serializers.CharField(
        required=False, allow_blank=True,
        help_text="Material arizasi: olib ketish vaqti, format YYYY-MM-DDTHH:MM (ixtiyoriy)",
    )


class OrderAcceptSerializer(serializers.Serializer):
    """ATM arizasini qabul qilish: ijrochini faqat superuser tanlay oladi."""
    receiver = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all(), required=False)


class OrderDecideSerializer(serializers.Serializer):
    """
    Arizani hal qilish uchun.
    ATM arizasi (worker): faqat 'accepted' (rating 1-5 majburiy) yoki 'canceled' — yuboruvchi/user.
    Material arizasi (client): approved — material o'zgarishsiz; rejected/canceled — omborga qaytariladi.
    """
    action = serializers.ChoiceField(choices=["approved", "canceled", "rejected", "accepted"])
    rating = serializers.IntegerField(min_value=1, max_value=5, required=False)


class OrderAcceptedSerializer(serializers.Serializer):
    """Ishni yakuniy qabul qilish — reyting shu yerda majburiy kiritiladi.
    Material o'zgarishsiz qoladi (haqiqatda berilgan hisoblanadi)."""
    rating = serializers.IntegerField(min_value=1, max_value=5)


class OrderGoalSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    goal_names = serializers.SerializerMethodField()

    class Meta:
        model = OrderGoal
        fields = ['id', 'employee', 'employee_name', 'goal', 'goal_names']

    def get_goal_names(self, obj):
        return [g.name for g in obj.goal.all()]


class MaterialUserSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    receiver_names = serializers.SerializerMethodField()

    class Meta:
        model = MaterialUser
        fields = ['id', 'sender', 'sender_name', 'receiver', 'receiver_names']

    def get_receiver_names(self, obj):
        return [e.full_name for e in obj.receiver.all()]


class DeedConsentSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_organization = serializers.CharField(source='employee.organization.name', read_only=True)
    employee_rank = serializers.CharField(source='employee.rank.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = DeedConsent
        fields = [
            'id', 'deed', 'employee', 'employee_name', 'employee_organization', 'employee_rank',
            'message', 'status', 'status_display', 'date_creat', 'date_edit',
        ]
        read_only_fields = fields


class DeedConsentActionSerializer(serializers.Serializer):
    """Kelishuvni tasdiqlash/rad etish uchun — main/views.py:deedconsent_action
    bilan bir xil qoida: message ixtiyoriy, faqat rad etishda majburiy
    (buni view action ichida tekshiramiz, chunki action turiga bog'liq)."""
    message = serializers.CharField(required=False, allow_blank=True, default="")


class DeedFilesSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeedFiles
        fields = ['id', 'deed', 'file', 'date_creat', 'date_edit']
        read_only_fields = fields


def _django_errors(exc):
    return serializers.ValidationError(list(exc.messages))


class DeedCreateSerializer(serializers.ModelSerializer):
    """
    Yaratish — saytdagi contact_post_deed bilan bir xil:
    * `file` (PDF) berilsa — tayyor hujjat yuklanadi; berilmasa `body` dan PDF yaratiladi;
    * `receiver` faqat status='document' uchun va faqat 'worker' tashkilot xodimi;
    * `attachments` — 10 tagacha PDF/Word/Excel; `agreements` — kelishuvchi xodimlar ID si.
    Yaratuvchi (`user`) har doim so'rov yuborgan xodim.
    """
    attachments = serializers.ListField(child=serializers.FileField(), required=False, write_only=True, max_length=10)
    agreements = serializers.ListField(child=serializers.IntegerField(), required=False, write_only=True)

    class Meta:
        model = Deed
        fields = ['status', 'organization', 'sender', 'receiver', 'body', 'file', 'attachments', 'agreements']
        extra_kwargs = {
            'organization': {'required': True, 'allow_null': False},
            'sender': {'required': True, 'allow_null': False},
            'file': {'required': False},
            'body': {'required': False, 'allow_blank': True},
        }

    def validate_file(self, value):
        from django.core.exceptions import ValidationError as DjangoValidationError
        from main.validators import validate_file_extension
        try:
            validate_file_extension(value)
        except DjangoValidationError as exc:
            raise _django_errors(exc)
        return value

    def validate_attachments(self, value):
        from django.core.exceptions import ValidationError as DjangoValidationError
        from main.validators import validate_attachment_extension
        for att in value:
            try:
                validate_attachment_extension(att)
            except DjangoValidationError as exc:
                raise serializers.ValidationError(f"{att.name}: {' '.join(exc.messages)}")
        return value

    def validate_body(self, value):
        from main.sanitizers import sanitize_deed_body
        value = (value or "").strip()
        return sanitize_deed_body(value) if value else ""

    def validate(self, attrs):
        if not attrs.get('file') and not attrs.get('body'):
            raise serializers.ValidationError("Fayl (PDF) yoki hujjat matni (body) berilishi shart")

        receiver = attrs.get('receiver')
        if attrs.get('status') != 'document':
            attrs['receiver'] = None
        elif receiver:
            if receiver.pk == attrs['sender'].pk:
                raise serializers.ValidationError(
                    {"receiver": "Imzolovchi va xizmat ko'rsatuvchi bir xil xodim bo'lishi mumkin emas"}
                )
            if not (receiver.organization_id and receiver.organization.type == "worker"):
                raise serializers.ValidationError({"receiver": "Xizmat ko'rsatuvchi xodim topilmadi"})
        return attrs

    def create(self, validated_data):
        attachments = validated_data.pop('attachments', [])
        agreements = validated_data.pop('agreements', [])
        deed = Deed.objects.create(**validated_data)

        ids = set(Employee.objects.filter(id__in=agreements).values_list('id', flat=True))
        ids.discard(deed.receiver_id)
        ids.discard(None)
        if ids:
            DeedConsent.objects.bulk_create([DeedConsent(deed=deed, employee_id=i) for i in ids])
        for att in attachments:
            DeedFiles.objects.create(deed=deed, file=att)
        return deed

    def to_representation(self, instance):
        return DeedSerializer(instance, context=self.context).data


class DeedUpdateSerializer(serializers.Serializer):
    """
    Tahrirlash — saytdagi deed_edit bilan bir xil: imzolovchi, qabul qiluvchi, matn va kelishuvchilar.
    Faqat yaratuvchi, `user_edit` yoqilgan va hali hech kim javob bermagan paytda.
    """
    sender = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all(), required=False)
    receiver = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all(), required=False)
    body = serializers.CharField(required=False, allow_blank=False)
    agreements = serializers.ListField(child=serializers.IntegerField(), required=False)

    def validate_body(self, value):
        from main.sanitizers import sanitize_deed_body
        value = sanitize_deed_body((value or "").strip())
        if not value:
            raise serializers.ValidationError("Hujjat matni bo'sh bo'lmasin")
        return value


class DeedConsentAddSerializer(serializers.Serializer):
    employees = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)


class DeedSignerConsentSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()


class DeedRejectSerializer(serializers.Serializer):
    message = serializers.CharField(required=False, allow_blank=True, default="")


class DeedConsentCandidateSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    rank_name = serializers.CharField(source='rank.name', read_only=True)

    class Meta:
        model = Employee
        fields = ['id', 'full_name', 'organization_name', 'rank_name']


class DeedSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    receiver_name = serializers.CharField(source='receiver.full_name', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    status_sender_display = serializers.CharField(source='get_status_sender_display', read_only=True)
    status_receiver_display = serializers.CharField(source='get_status_receiver_display', read_only=True)
    consents = DeedConsentSerializer(source='deedconsent_set', many=True, read_only=True)
    attachments = DeedFilesSerializer(source='deedfiles_set', many=True, read_only=True)

    # Ilova interfeysi uchun: joriy foydalanuvchi bu hujjatda nima qila oladi
    can_edit = serializers.SerializerMethodField()
    can_manage_consents = serializers.SerializerMethodField()
    can_add_consents = serializers.SerializerMethodField()
    can_reject = serializers.SerializerMethodField()
    my_consent_id = serializers.SerializerMethodField()

    class Meta:
        model = Deed
        fields = [
            'id', 'organization', 'organization_name',
            'sender', 'sender_name', 'message_sender', 'status_sender', 'status_sender_display', 'date_sender',
            'receiver', 'receiver_name', 'message_receiver', 'status_receiver', 'status_receiver_display', 'date_receiver',
            'user', 'user_name', 'user_edit', 'message_user',
            'sender_can_add_consent', 'receiver_can_add_consent',
            'body', 'status', 'status_display', 'file', 'code', 'orders',
            'date_creat', 'date_edit', 'consents', 'attachments',
            'can_edit', 'can_manage_consents', 'can_add_consents', 'can_reject', 'my_consent_id',
        ]
        read_only_fields = fields

    def _me(self):
        request = self.context.get('request')
        return getattr(getattr(request, 'user', None), 'employee', None)

    def get_can_edit(self, deed):
        me = self._me()
        if not me or deed.user_id != me.id or not deed.user_edit or not deed.body:
            return False
        if deed.status_sender != 'viewed':
            return False
        return not deed.receiver_id or deed.status_receiver == 'viewed'

    def get_can_manage_consents(self, deed):
        from main.views import _deed_consents_open
        me = self._me()
        return bool(me and deed.user_id == me.id and _deed_consents_open(deed))

    def get_can_add_consents(self, deed):
        from main.views import _deed_consents_open, _can_add_consents
        me = self._me()
        return bool(me and _deed_consents_open(deed) and _can_add_consents(deed, me))

    def get_can_reject(self, deed):
        me = self._me()
        if not me:
            return False
        if deed.receiver_id == me.id:
            return deed.status_receiver == 'viewed'
        if deed.sender_id == me.id:
            return deed.status_sender == 'viewed'
        return False

    def get_my_consent_id(self, deed):
        me = self._me()
        if not me:
            return None
        for dc in deed.deedconsent_set.all():
            if dc.employee_id == me.id and dc.status == 'viewed':
                return dc.id
        return None


class DeedRegistrySerializer(DeedSerializer):
    """Hujjatlar reyestri (saytdagi files sahifasi): hujjat ma'lumoti matnsiz (body yo'q) va ilova bayroqlarisiz."""

    class Meta(DeedSerializer.Meta):
        fields = [
            f for f in DeedSerializer.Meta.fields
            if f not in ('body', 'can_edit', 'can_manage_consents', 'can_add_consents', 'can_reject', 'my_consent_id')
        ]
        read_only_fields = fields


class LiableSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    contract_names = serializers.SerializerMethodField()
    category_names = serializers.SerializerMethodField()

    class Meta:
        model = Liable
        fields = ['id', 'employee', 'employee_name', 'categorys', 'category_names', 'contracts', 'contract_names']

    def get_contract_names(self, obj):
        return [c.name for c in obj.contracts.all()]

    def get_category_names(self, obj):
        return [c.name for c in obj.categorys.all()]


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