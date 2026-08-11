from django.db import DatabaseError
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.core.files.base import ContentFile
import secrets
from django.http import Http404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from django.http import FileResponse
from bot.notify import send_telegram_message, rating_markup, barn_approved_markup
from main.html_pdf import _create_deed_for_order, deed_to_pdf_bytes, add_text_watermark_pdf_bytes, HtmlPdfError
from rest_framework import viewsets, mixins
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser


from .serializers import *
from .permissions import *
from .pagination import *


class OrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["type"]
    search_fields = ["name", "inn"]

    def get_queryset(self):
        qs = Organization.objects.all()
        user = self.request.user

        if user.is_superuser or user.has_perm("main.all_organization"):
            return qs

        employee = getattr(user, "employee", None)
        if not employee or not employee.organization_id:
            return qs.none()

        return qs.filter(id=employee.organization_id)


class RegionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Region.objects.all()
    serializer_class = RegionSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ["name"]

    def get_queryset(self):
        qs = Region.objects.all()
        user = self.request.user

        if user.is_superuser or user.has_perm("main.all_region"):
            return qs

        employee = getattr(user, "employee", None)
        if not employee or not employee.region_id:
            return qs.none()

        return qs.filter(id=employee.region_id)


class DepartmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Department.objects.select_related('organization', 'region').all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["organization", "region"]
    search_fields = ["name", "code", "inn"]

    def get_queryset(self):
        qs = Department.objects.select_related('organization', 'region').all()
        user = self.request.user

        if user.is_superuser:
            return qs

        employee = getattr(user, "employee", None)
        if not employee:
            return qs.none()

        has_all_org = user.has_perm("main.all_organization")
        has_all_region = user.has_perm("main.all_region")

        if not has_all_org:
            if not employee.organization_id:
                return qs.none()
            qs = qs.filter(organization_id=employee.organization_id)

        if not has_all_region:
            if not employee.region_id:
                return qs.none()
            qs = qs.filter(region_id=employee.region_id)

        return qs


class DirectorateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Directorate.objects.select_related(
        'department', 'department__organization', 'department__region'
    ).all()
    serializer_class = DirectorateSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["department"]
    search_fields = ["name", "code"]

    def get_queryset(self):
        qs = Directorate.objects.select_related(
            'department', 'department__organization', 'department__region'
        ).all()
        user = self.request.user

        if user.is_superuser:
            return qs

        employee = getattr(user, "employee", None)
        if not employee:
            return qs.none()

        has_all_org = user.has_perm("main.all_organization")
        has_all_region = user.has_perm("main.all_region")

        if not has_all_org:
            if not employee.organization_id:
                return qs.none()
            qs = qs.filter(department__organization_id=employee.organization_id)

        if not has_all_region:
            if not employee.region_id:
                return qs.none()
            qs = qs.filter(department__region_id=employee.region_id)

        return qs


class DivisionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Division.objects.select_related(
        'directorate',
        'directorate__department',
        'directorate__department__organization',
        'directorate__department__region',
    ).all()
    serializer_class = DivisionSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["directorate"]
    search_fields = ["name", "code"]

    def get_queryset(self):
        qs = Division.objects.select_related(
            'directorate',
            'directorate__department',
            'directorate__department__organization',
            'directorate__department__region',
        ).all()
        user = self.request.user

        if user.is_superuser:
            return qs

        employee = getattr(user, "employee", None)
        if not employee:
            return qs.none()

        has_all_org = user.has_perm("main.all_organization")
        has_all_region = user.has_perm("main.all_region")

        if not has_all_org:
            if not employee.organization_id:
                return qs.none()
            qs = qs.filter(directorate__department__organization_id=employee.organization_id)

        if not has_all_region:
            if not employee.region_id:
                return qs.none()
            qs = qs.filter(directorate__department__region_id=employee.region_id)

        return qs


class GroupViewSet(viewsets.ReadOnlyModelViewSet):
    """Faqat KO'RISH — barcha autentifikatsiyadan o'tgan foydalanuvchilar ko'radi."""
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [SearchFilter]
    search_fields = ["name"]


class ContractViewSet(viewsets.ReadOnlyModelViewSet):
    """Faqat KO'RISH — barcha autentifikatsiyadan o'tgan foydalanuvchilar ko'radi."""
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [SearchFilter]
    search_fields = ["name"]


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Faqat KO'RISH — barcha autentifikatsiyadan o'tgan foydalanuvchilar ko'radi."""
    queryset = Category.objects.select_related('group', 'contract').all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["group", "contract"]
    search_fields = ["name"]


class TechnicsViewSet(viewsets.ModelViewSet):
    """
    Ko'rish — hammaga (o'z tashkiloti/xududi bo'yicha cheklab), faqat is_active=True.
    Qo'shish/tahrirlash — tegishli permission bo'lganlarga (faqat texnika maydonlari).
    Biriktirish — alohida action orqali (employee/department/directorate/division).
    O'chirish — bazadan o'chirmaydi, is_active=False qilib qo'yadi (soft delete).
    O'chirilgan texnikalar hech qanday action orqali (list/retrieve/update) qayta
    ko'rinmaydi — faqat admin panel orqali qayta faollashtiriladi.
    """

    queryset = Technics.objects.select_related(
        'group', 'category', 'region', 'organization',
        'department', 'directorate', 'division', 'employee',
    ).filter(is_active=True)
    permission_classes = [TechnicsPermission]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = [
        "group", "category", "region", "organization",
        "department", "directorate", "division",
        "employee", "status",
    ]
    search_fields = ["name", "inventory", "serial", "mac", "ip"]

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return TechnicsCreateUpdateSerializer
        if self.action == 'assign':
            return TechnicsAssignSerializer
        return TechnicsSerializer

    def get_queryset(self):
        qs = Technics.objects.select_related(
            'group', 'category', 'region', 'organization',
            'department', 'directorate', 'division', 'employee',
        ).filter(is_active=True)
        user = self.request.user

        if user.is_superuser:
            return qs

        employee = getattr(user, "employee", None)
        if not employee:
            return qs.none()

        has_all_org = user.has_perm("main.all_organization")
        has_all_region = user.has_perm("main.all_region")

        if not has_all_org:
            if not employee.organization_id:
                return qs.none()
            qs = qs.filter(organization_id=employee.organization_id)

        if not has_all_region:
            if not employee.region_id:
                return qs.none()
            qs = qs.filter(region_id=employee.region_id)

        return qs

    def perform_destroy(self, instance):
        """Haqiqiy o'chirish o'rniga is_active=False qilib qo'yish."""
        instance.is_active = False
        instance.save(update_fields=['is_active'])

    @action(detail=True, methods=['post'], url_path='assign')
    def assign(self, request, pk=None):
        """Texnikani xodimga biriktirish: POST /api/technics/{id}/assign/"""
        technics = self.get_object()
        serializer = self.get_serializer(technics, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(TechnicsSerializer(technics).data)

    @action(detail=True, methods=['get'], url_path='qr')
    def qr(self, request, pk=None):
        """QR kodni to'g'ridan-to'g'ri fayl sifatida qaytaradi: GET /api/technics/{id}/qr/"""
        technics = self.get_object()

        if not technics.qr_code:
            raise Http404("QR kod topilmadi")

        return FileResponse(
            technics.qr_code.open('rb'),
            content_type='image/png',
            filename=f"technics_{technics.pk}_qr.png",
        )


class StructureCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Faqat KO'RISH — barcha autentifikatsiyadan o'tgan foydalanuvchilar ko'radi."""
    queryset = StructureCategory.objects.all()
    serializer_class = StructureCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [SearchFilter]
    search_fields = ["name"]


class StructureViewSet(viewsets.ModelViewSet):
    """
    Ko'rish — hammaga (o'z tashkiloti/xududi bo'yicha cheklab), faqat is_active=True.
    Qo'shish/tahrirlash — tegishli permission bo'lganlarga.
    Biriktirish/bekor qilish — alohida action orqali (technics).
    O'chirish — bazadan o'chirmaydi, is_active=False qilib qo'yadi (soft delete).
    """

    queryset = Structure.objects.select_related(
        'category', 'organization', 'region', 'technics',
    ).filter(is_active=True)
    permission_classes = [StructurePermission]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["category", "organization", "region", "technics", "status"]
    search_fields = ["name", "inventory", "serial"]

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return StructureCreateUpdateSerializer
        if self.action in ('assign', 'unassign'):
            return StructureAssignSerializer
        return StructureSerializer

    def get_queryset(self):
        qs = Structure.objects.select_related(
            'category', 'organization', 'region', 'technics',
        ).filter(is_active=True)
        user = self.request.user

        if user.is_superuser:
            return qs

        employee = getattr(user, "employee", None)
        if not employee:
            return qs.none()

        has_all_org = user.has_perm("main.all_organization")
        has_all_region = user.has_perm("main.all_region")

        if not has_all_org:
            if not employee.organization_id:
                return qs.none()
            qs = qs.filter(organization_id=employee.organization_id)

        if not has_all_region:
            if not employee.region_id:
                return qs.none()
            qs = qs.filter(region_id=employee.region_id)

        return qs

    def perform_destroy(self, instance):
        """Haqiqiy o'chirish o'rniga is_active=False qilib qo'yish."""
        instance.is_active = False
        instance.save(update_fields=['is_active'])

    @action(detail=True, methods=['post'], url_path='assign')
    def assign(self, request, pk=None):
        """Qurulmani texnikaga biriktirish: POST /api/structures/{id}/assign/"""
        structure = self.get_object()
        serializer = self.get_serializer(structure, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(StructureSerializer(structure).data)

    @action(detail=True, methods=['post'], url_path='unassign')
    def unassign(self, request, pk=None):
        """Qurulmani texnikadan bo'shatish: POST /api/structures/{id}/unassign/"""
        structure = self.get_object()
        structure.technics = None
        structure.save()

        return Response(StructureSerializer(structure).data)


class UnitViewSet(viewsets.ReadOnlyModelViewSet):
    """Faqat KO'RISH — barcha autentifikatsiyadan o'tgan foydalanuvchilar ko'radi."""
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [SearchFilter]
    search_fields = ["name"]


class MaterialCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Faqat KO'RISH — barcha autentifikatsiyadan o'tgan foydalanuvchilar ko'radi."""
    queryset = MaterialCategory.objects.all()
    serializer_class = MaterialCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [SearchFilter]
    search_fields = ["name"]


class MaterialViewSet(viewsets.ModelViewSet):
    """
    Ko'rish — 'shop_employee': faqat o'z tashkilotidagi va o'zining materiallari.
              'all_material_employee': o'z tashkilotidagi BARCHA materiallar.
    Qo'shish — 'shop_employee' yoki 'add_material' ruxsati kerak; organization va
    employee avtomatik so'rov yuborgan xodimning o'zidan olinadi.
    Tahrirlash — 'shop_employee' yoki 'change_material' ruxsati kerak.
    O'chirish — bazadan o'chirmaydi, is_active=False qilib qo'yadi (soft delete).
    Berish (give) — 'all_material_employee' ruxsati bo'lganlar o'z tashkilotidagi
    xodimga material bera oladi: POST /api/materials/give/
    """

    queryset = Material.objects.select_related(
        'category', 'organization', 'unit', 'employee',
    ).filter(is_active=True)
    permission_classes = [MaterialPermission]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["category", "unit", "employee"]
    search_fields = ["name", "code"]

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return MaterialCreateUpdateSerializer
        if self.action == 'give':
            return MaterialGiveSerializer
        return MaterialSerializer

    def get_queryset(self):
        user = self.request.user

        employee = getattr(user, "employee", None)
        if not employee or not employee.organization_id:
            return Material.objects.none()

        base_qs = Material.objects.select_related(
            'category', 'organization', 'unit', 'employee',
        ).filter(organization_id=employee.organization_id, is_active=True)

        if user.is_superuser or user.has_perm('main.all_material_employee'):
            return base_qs

        if user.has_perm('main.shop_employee'):
            return base_qs.filter(employee_id=employee.id)

        return Material.objects.none()

    def perform_create(self, serializer):
        employee = self.request.user.employee
        serializer.save(organization_id=employee.organization_id, employee=employee)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active'])

    @action(detail=False, methods=['post'], url_path='give')
    def give(self, request):
        """
        Bir nechta materialni bitta xodimga berish: POST /api/materials/give/
        Faqat 'all_material_employee' ruxsati bo'lganlar chaqira oladi.
        Butun savat bitta transaction ichida ishlaydi — biror material xato bersa,
        hech biri saqlanmaydi.
        """
        if not (request.user.is_superuser or request.user.has_perm('main.all_material_employee')):
            return Response({"detail": "Ruxsat yo'q."}, status=403)

        employee = getattr(request.user, "employee", None)
        if not employee:
            return Response({"detail": "Sizda xodim profili topilmadi."}, status=400)

        serializer = MaterialGiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee_id = serializer.validated_data['employee_id']
        items = serializer.validated_data['items']

        emp = get_object_or_404(Employee, id=employee_id)
        if emp.organization_id != employee.organization_id:
            return Response({"detail": "Xodim boshqa tashkilotga tegishli."}, status=400)

        results = []

        with transaction.atomic():
            for item in items:
                material_id = item['material_id']
                give_number_int = item['number']

                src = get_object_or_404(
                    Material.objects.select_for_update(),
                    id=material_id
                )

                if src.organization_id != employee.organization_id:
                    return Response(
                        {"detail": f"Material #{material_id}: sizga ruxsat yo'q."}, status=403
                    )

                if src.employee_id and src.employee_id == employee_id:
                    return Response(
                        {"detail": f"Material #{material_id}: allaqachon shu xodimga tegishli."},
                        status=400
                    )

                src_qty = int(src.number or 0)
                if src_qty < give_number_int:
                    return Response(
                        {"detail": f"Material #{material_id}: omborda yetarli emas (bor: {src_qty})"},
                        status=400
                    )

                dst_filter = {"employee_id": emp.id}
                if (src.code or "").strip():
                    dst_filter["code"] = src.code
                else:
                    dst_filter["name"] = src.name

                dst = (
                    Material.objects
                    .select_for_update()
                    .filter(**dst_filter)
                    .first()
                )

                if dst:
                    dst_qty_before = int(dst.number or 0)
                    dst.number = dst_qty_before + give_number_int

                    if (dst.price in [None, 0, "0"]) and src.price not in [None, 0, "0"]:
                        dst.price = src.price
                    if not dst.unit_id and src.unit_id:
                        dst.unit = src.unit

                    dst.save(update_fields=["number", "price", "unit"])
                    dst_material = dst
                else:
                    dst_qty_before = 0
                    dst_material = Material.objects.create(
                        organization=emp.organization,
                        employee=emp,
                        name=src.name,
                        code=src.code,
                        number=give_number_int,
                        unit=src.unit,
                        price=src.price,
                        year=src.year,
                    )

                src.number = src_qty - give_number_int
                src.save(update_fields=["number"])

                MaterialMovement.objects.create(
                    material=src,
                    user=employee,
                    employee=src.employee,
                    status='assigned',
                    income=None,
                    outcome=give_number_int,
                    body=(
                        f"Berildi: {employee}\n"
                        f"Qabul qildi: {emp}\n"
                        f"Ombordan oldin: {src_qty}\n"
                        f"Soni: {give_number_int}\n"
                        f"Omborda qoldi: {src.number}"
                    )
                )

                MaterialMovement.objects.create(
                    material=dst_material,
                    user=employee,
                    employee=emp,
                    status='assigned',
                    income=give_number_int,
                    outcome=None,
                    body=(
                        f"Qabul qildi: {emp}\n"
                        f"Berdi: {employee}\n"
                        f"Oldin: {dst_qty_before}\n"
                        f"Soni: {give_number_int}\n"
                        f"Jami: {dst_qty_before + give_number_int}"
                    )
                )

                results.append(MaterialSerializer(src).data)

        return Response({"given": results})


class MaterialEmployeeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Faqat KO'RISH — o'z tashkilotidagi xodim-kategoriya bog'lanishlari.
    """

    serializer_class = MaterialEmployeeSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["employee", "category"]
    search_fields = ["employee__last_name", "employee__first_name", "category__name"]

    def get_queryset(self):
        qs = MaterialEmployee.objects.select_related('employee', 'category').all()
        user = self.request.user

        if user.is_superuser or user.has_perm("main.all_organization"):
            return qs

        employee = getattr(user, "employee", None)
        if not employee or not employee.organization_id:
            return qs.none()

        return qs.filter(employee__organization_id=employee.organization_id)


class GoalViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Faqat KO'RISH — 'all_organization' bo'lsa hammasi, aks holda faqat
    o'z tashkilotiga tegishli ariza kategoriyalari.
    """

    serializer_class = GoalSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["organization"]
    search_fields = ["name"]

    def get_queryset(self):
        qs = Goal.objects.select_related('organization').all()
        user = self.request.user

        if user.is_superuser or user.has_perm("main.all_organization"):
            return qs

        employee = getattr(user, "employee", None)
        if not employee or not employee.organization_id:
            return qs.none()

        return qs.filter(organization_id=employee.organization_id)


class OrderViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Ko'rish — 'view_order' ruxsati bo'lsa o'z tashkilotidagi (goal__organization
    orqali) barcha arizalar, bo'lmasa faqat o'ziga aloqador (sender/receiver/user).
    Yaratish — har qanday employee profiliga ega xodim; sender avtomatik
    o'zidan olinadi, status='viewed' bo'lib boshlanadi, materiallar ixtiyoriy
    (so'rov sifatida saqlanadi, ombordan hali ayirilmaydi).
    Qabul qilish (accept) — 'change_order' ruxsati, viewed→process.
    Material biriktirish (materials) — faqat receiver, ombordan ayiradi,
    MaterialMovement yozadi, mavjud bo'lsa given yangilanadi, bo'lmasa yaratiladi.
    Yakunlash (finish) — faqat receiver, texnika biriktiradi, process/finished→finished.
    Hal qilish (decide) — sender/order.user/confirm_order:
        approved  — material o'zgarishsiz qoladi
        rejected/canceled — arizadagi materiallar omborga qaytariladi
    Yakuniy qabul (accepted) — faqat sender, approved→accepted, reyting
    majburiy, material o'zgarishsiz qoladi.
    """

    permission_classes = [OrderPermission]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["status", "goal", "goal__organization", "sender", "receiver", "user", "technics"]
    search_fields = ["message_sender", "message_receiver", "message_user"]

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        if self.action == 'add_material':
            return OrderMaterialAddSerializer
        if self.action == 'finish':
            return OrderFinishSerializer
        if self.action == 'decide':
            return OrderDecideSerializer
        if self.action == 'accepted':
            return OrderAcceptedSerializer
        return OrderSerializer

    def get_queryset(self):
        qs = Order.objects.select_related(
            'goal', 'goal__organization', 'sender', 'receiver', 'user', 'technics',
        ).prefetch_related('materials__material').all()

        user = self.request.user
        employee = getattr(user, "employee", None)
        if not employee:
            return qs.none()

        if user.is_superuser:
            return qs

        if user.has_perm('main.view_order'):
            return qs.filter(goal__organization_id=employee.organization_id)

        return qs.filter(
            models.Q(sender_id=employee.id) |
            models.Q(receiver_id=employee.id) |
            models.Q(user_id=employee.id)
        ).distinct()

    # ---------- YARATISH ----------

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = request.user.employee
        materials_data = serializer.validated_data.pop('materials', [])

        with transaction.atomic():
            order = Order.objects.create(
                goal=serializer.validated_data['goal'],
                message_sender=serializer.validated_data.get('message_sender'),
                sender=employee,
                status='viewed',
            )

            if materials_data:
                material_ids = [item['material_id'] for item in materials_data]
                if len(material_ids) != len(set(material_ids)):
                    return Response({"detail": "Bir xil material bir necha marta kiritildi."}, status=400)

                materials = Material.objects.filter(id__in=material_ids, is_active=True)
                materials_map = {m.id: m for m in materials}

                order_materials = []
                for item in materials_data:
                    mat = materials_map.get(item['material_id'])
                    if not mat:
                        return Response(
                            {"detail": f"Material #{item['material_id']} topilmadi yoki faol emas."},
                            status=400
                        )
                    order_materials.append(OrderMaterial(order=order, material=mat, number=item['number']))

                OrderMaterial.objects.bulk_create(order_materials)

        return Response(OrderSerializer(order).data, status=201)

    # ---------- QABUL QILISH ----------

    @action(detail=True, methods=['post'], url_path='accept')
    def accept(self, request, pk=None):
        """Arizani qabul qilish: POST /api/orders/{id}/accept/"""
        employee = request.user.employee

        order = get_object_or_404(Order, pk=pk)
        if order.status != "viewed" or order.receiver_id is not None:
            return Response(
                {"detail": "Bu ariza allaqachon boshqa xodim tomonidan qabul qilingan."},
                status=400
            )

        try:
            with transaction.atomic():
                order = Order.objects.select_for_update().get(pk=pk)

                if order.status != "viewed" or order.receiver_id is not None:
                    return Response(
                        {"detail": "Bu ariza allaqachon boshqa xodim tomonidan qabul qilingan."},
                        status=400
                    )

                order.status = "process"
                order.receiver = employee
                order.save(update_fields=["status", "receiver"])
        except DatabaseError:
            return Response({"detail": "Xatolik yuz berdi. Qayta urinib ko'ring."}, status=500)

        return Response(OrderSerializer(order).data)

    # ---------- MATERIAL BIRIKTIRISH ----------

    @action(detail=True, methods=['post'], url_path='materials')
    def add_material(self, request, pk=None):
        """
        Arizaga material biriktirish: POST /api/orders/{id}/materials/
        Faqat receiver (qabul qilgan xodim) chaqira oladi, status process/finished bo'lsa.
        Material arizada mavjud bo'lsa — given yoziladi (yangilanadi).
        Mavjud bo'lmasa — yangi OrderMaterial yaratiladi (given bilan).
        Ombordan ayiriladi, MaterialMovement yoziladi.
        """
        employee = request.user.employee
        serializer = OrderMaterialAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        material_id = serializer.validated_data['material_id']
        n = serializer.validated_data['number']

        try:
            with transaction.atomic():
                order = get_object_or_404(Order.objects.select_for_update(), pk=pk)

                if order.receiver_id != employee.id:
                    return Response(
                        {"detail": "Bu arizaga faqat uni qabul qilgan xodim material qo'sha oladi."},
                        status=403
                    )

                if order.status not in ["process", "finished"]:
                    return Response({"detail": "Bu arizaga material qo'shib bo'lmaydi."}, status=400)

                mat = get_object_or_404(
                    Material.objects.select_for_update(), id=material_id, is_active=True
                )

                if (mat.number or 0) < n:
                    return Response(
                        {"detail": f'"{mat.name}" yetarli emas. Omborda {mat.number} dona bor.'},
                        status=400
                    )

                existing_om = OrderMaterial.objects.select_for_update().filter(
                    order=order, material_id=material_id
                ).first()

                Material.objects.filter(pk=mat.pk).update(number=F("number") - n)

                if existing_om:
                    existing_om.given = n
                    existing_om.save(update_fields=["given"])
                    om_result = existing_om
                else:
                    om_result = OrderMaterial.objects.create(
                        order=order, material=mat, number=n, given=n
                    )

                MaterialMovement.objects.create(
                    material=mat,
                    user=employee,
                    employee=order.sender,
                    status='assigned',
                    income=None,
                    outcome=n,
                    body=(
                        f"Ariza #{order.id} bo'yicha berildi\n"
                        f"Berdi: {employee}\n"
                        f"Kimga: {order.sender}\n"
                        f"Soni: {n}\n"
                        f"Omborda qoldi: {mat.number - n}"
                    )
                )
        except DatabaseError:
            return Response({"detail": "Xatolik yuz berdi. Qayta urinib ko'ring."}, status=500)

        return Response(OrderMaterialSerializer(om_result).data, status=201)

    # ---------- YAKUNLASH ----------

    @action(detail=True, methods=['post'], url_path='finish')
    def finish(self, request, pk=None):
        """
        Arizani yakunlash: POST /api/orders/{id}/finish/
        Faqat texnika biriktiradi va statusni 'finished' qiladi.
        Materiallar alohida /materials/ endpoint orqali qo'shiladi.
        """
        employee = request.user.employee
        serializer = OrderFinishSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        technics_id = serializer.validated_data.get('technics_id')

        try:
            with transaction.atomic():
                order = get_object_or_404(Order.objects.select_for_update(), pk=pk)

                if not order.receiver_id:
                    return Response({"detail": "Ariza hali hech kimga biriktirilmagan."}, status=400)

                if order.receiver_id != employee.id:
                    return Response(
                        {"detail": "Bu arizani faqat uni qabul qilgan xodim yakunlay oladi."},
                        status=403
                    )

                if order.status not in ["process", "finished"]:
                    return Response({"detail": "Bu ariza yakunlanishi mumkin emas."}, status=400)

                if technics_id:
                    order.technics_id = technics_id

                order.status = "finished"
                order.save(update_fields=["status", "technics_id"])
        except DatabaseError:
            return Response({"detail": "Xatolik yuz berdi. Qayta urinib ko'ring."}, status=500)

        return Response(OrderSerializer(order).data)

    # ---------- HAL QILISH ----------

    @action(detail=True, methods=['post'], url_path='decide')
    def decide(self, request, pk=None):
        """
        Arizani hal qilish: POST /api/orders/{id}/decide/
        Sender, order.user, YOKI 'confirm_order' ruxsatiga ega xodim bajara oladi.
        action='approved' — material o'zgarishsiz qoladi.
        action='rejected' yoki 'canceled' — berilgan materiallar omborga qaytariladi.
        """
        employee = request.user.employee
        user = request.user

        order = get_object_or_404(Order, pk=pk)

        is_related = order.sender_id == employee.id or order.user_id == employee.id
        has_confirm_perm = user.is_superuser or user.has_perm('main.confirm_order')

        if not is_related and not has_confirm_perm:
            return Response({"detail": "Sizda bu arizani o'zgartirish huquqi yo'q."}, status=403)

        serializer = OrderDecideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        act = serializer.validated_data['action']

        try:
            with transaction.atomic():
                order = Order.objects.select_for_update().get(pk=pk)

                if act in ("rejected", "canceled"):
                    order_materials = list(
                        OrderMaterial.objects.select_for_update()
                        .filter(order=order)
                        .select_related("material")
                    )
                    material_ids = [om.material_id for om in order_materials if om.material_id]
                    materials = list(Material.objects.select_for_update().filter(id__in=material_ids))
                    material_map = {m.id: m for m in materials}

                    movements = []
                    for om in order_materials:
                        mat = material_map.get(om.material_id)
                        if not mat:
                            continue

                        mat.number = (mat.number or 0) + om.number
                        movements.append(MaterialMovement(
                            material=mat,
                            user=employee,
                            employee=order.sender,
                            status='assigned',
                            income=om.number,
                            outcome=None,
                            body=(
                                f"Ariza #{order.id} {act} — material omborga qaytarildi\n"
                                f"Qaytardi: {order.sender}\n"
                                f"Qabul qildi: {employee}\n"
                                f"Soni: {om.number}\n"
                                f"Omborda: {mat.number}"
                            )
                        ))

                    if material_map:
                        Material.objects.bulk_update(list(material_map.values()), ["number"])
                    if movements:
                        MaterialMovement.objects.bulk_create(movements)

                # act == "approved" bo'lsa — material o'zgarishsiz qoladi

                order.status = act
                if has_confirm_perm and not is_related:
                    order.user = employee
                    order.save(update_fields=["status", "user"])
                else:
                    order.save(update_fields=["status"])
        except DatabaseError:
            return Response({"detail": "Xatolik yuz berdi. Qayta urinib ko'ring."}, status=500)

        return Response(OrderSerializer(order).data)

    # ---------- YAKUNIY QABUL ----------

    @action(detail=True, methods=['post'], url_path='accepted')
    def accepted(self, request, pk=None):
        """
        Arizani yakuniy qabul qilish: POST /api/orders/{id}/accepted/
        Faqat sender bajara oladi. Faqat status='approved' bo'lganda ishlaydi.
        Reyting (1-5) shu bosqichda majburiy kiritiladi. Material o'zgarishsiz qoladi.
        """
        employee = request.user.employee

        order = get_object_or_404(Order, pk=pk)
        if order.sender_id != employee.id:
            return Response({"detail": "Ariza sizga tegishli emas."}, status=403)

        if order.status != "approved":
            return Response({"detail": "Bu ariza hozir qabul qilinmaydi."}, status=400)

        serializer = OrderAcceptedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rating = serializer.validated_data['rating']

        try:
            with transaction.atomic():
                order = Order.objects.select_for_update().get(pk=pk)

                if order.status != "approved":
                    return Response({"detail": "Bu ariza hozir qabul qilinmaydi."}, status=400)

                order.status = "accepted"
                order.rating = rating
                order.save(update_fields=["status", "rating"])
        except DatabaseError:
            return Response({"detail": "Xatolik yuz berdi. Qayta urinib ko'ring."}, status=500)

        return Response(OrderSerializer(order).data)


class OrderMaterialViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Ko'rish — arizadagi materiallar ('view_order' bo'lsa tashkilot bo'yicha,
    bo'lmasa o'ziga aloqador sender/receiver/user).
    Tahrirlash (PATCH) — faqat receiver, 'number' (so'ralgan miqdor) o'zgaradi,
    ombor bilan bog'liq emas.
    Given (POST .../given/) — faqat receiver, 'given' (berilgan miqdor) o'zgaradi,
    ombordagi Material.number bilan delta hisoblab kamaytiradi/ko'paytiradi.
    O'chirish (DELETE) — faqat receiver, given miqdorini to'liq omborga qaytaradi.
    """

    serializer_class = OrderMaterialSerializer
    permission_classes = [OrderMaterialPermission]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["order", "material"]

    def get_serializer_class(self):
        if self.action in ('update', 'partial_update'):
            return OrderMaterialUpdateSerializer
        if self.action == 'given':
            return OrderMaterialGivenSerializer
        return OrderMaterialSerializer

    def get_queryset(self):
        qs = OrderMaterial.objects.select_related(
            'order', 'material', 'material__unit',
        ).all()

        user = self.request.user
        employee = getattr(user, "employee", None)
        if not employee:
            return qs.none()

        if user.is_superuser:
            return qs

        if user.has_perm('main.view_order'):
            return qs.filter(order__goal__organization_id=employee.organization_id)

        return qs.filter(
            models.Q(order__sender_id=employee.id) |
            models.Q(order__receiver_id=employee.id) |
            models.Q(order__user_id=employee.id)
        ).distinct()

    # ---------- NUMBER TAHRIRLASH (ombor bilan bog'liq emas) ----------

    def update(self, request, *args, **kwargs):
        """PATCH/PUT /api/order-materials/{id}/ — number (so'ralgan miqdor) tahrirlash."""
        employee = request.user.employee
        serializer = OrderMaterialUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_number = serializer.validated_data['number']

        om = get_object_or_404(
            OrderMaterial.objects.select_related('order', 'material'),
            pk=kwargs['pk']
        )
        order = om.order

        if not order or order.receiver_id != employee.id:
            return Response(
                {"detail": "Bu materialni faqat arizani qabul qilgan xodim tahrirlay oladi."},
                status=403
            )

        om.number = new_number
        om.save(update_fields=["number"])

        return Response(OrderMaterialSerializer(om).data)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    # ---------- GIVEN TAHRIRLASH (ombor bilan bog'liq) ----------

    @action(detail=True, methods=['post'], url_path='given')
    def given(self, request, pk=None):
        """
        POST /api/order-materials/{id}/given/ — given (berilgan miqdor) tahrirlash.
        Ombordagi Material.number bilan farqni (delta) hisoblab kamaytiradi/ko'paytiradi.
        Faqat receiver bajara oladi.
        """
        employee = request.user.employee
        serializer = OrderMaterialGivenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_given = serializer.validated_data['given']

        try:
            with transaction.atomic():
                om = get_object_or_404(
                    OrderMaterial.objects.select_for_update().select_related('order', 'material'),
                    pk=pk
                )
                order = om.order

                if not order or order.receiver_id != employee.id:
                    return Response(
                        {"detail": "Bu materialni faqat arizani qabul qilgan xodim tahrirlay oladi."},
                        status=403
                    )

                mat = Material.objects.select_for_update().get(pk=om.material_id)
                old_given = om.given or 0
                delta = new_given - old_given

                if delta > 0 and (mat.number or 0) < delta:
                    return Response(
                        {"detail": f'"{mat.name}" yetarli emas. Omborda {mat.number} dona bor.'},
                        status=400
                    )

                mat.number = (mat.number or 0) - delta
                mat.save(update_fields=["number"])

                om.given = new_given
                om.save(update_fields=["given"])

                MaterialMovement.objects.create(
                    material=mat,
                    user=employee,
                    employee=order.sender,
                    status='assigned',
                    income=-delta if delta < 0 else None,
                    outcome=delta if delta > 0 else None,
                    body=(
                        f"Ariza #{order.id} bo'yicha material tahrirlandi\n"
                        f"Eski given: {old_given}, Yangi given: {new_given}\n"
                        f"Omborda qoldi: {mat.number}"
                    )
                )
        except DatabaseError:
            return Response({"detail": "Xatolik yuz berdi. Qayta urinib ko'ring."}, status=500)

        return Response(OrderMaterialSerializer(om).data)

    # ---------- O'CHIRISH ----------

    def destroy(self, request, *args, **kwargs):
        """DELETE /api/order-materials/{id}/ — o'chirish, given omborga to'liq qaytariladi."""
        employee = request.user.employee

        try:
            with transaction.atomic():
                om = get_object_or_404(
                    OrderMaterial.objects.select_for_update().select_related('order', 'material'),
                    pk=kwargs['pk']
                )
                order = om.order

                if not order or order.receiver_id != employee.id:
                    return Response(
                        {"detail": "Bu materialni faqat arizani qabul qilgan xodim o'chira oladi."},
                        status=403
                    )

                given = om.given or 0
                if given > 0 and om.material_id:
                    mat = Material.objects.select_for_update().get(pk=om.material_id)
                    mat.number = (mat.number or 0) + given
                    mat.save(update_fields=["number"])

                    MaterialMovement.objects.create(
                        material=mat,
                        user=employee,
                        employee=order.sender,
                        status='deleted',
                        income=given,
                        outcome=None,
                        body=(
                            f"Ariza #{order.id} bo'yicha material o'chirildi\n"
                            f"Qaytarildi: {given}\n"
                            f"Omborda: {mat.number}"
                        )
                    )

                om.delete()
        except DatabaseError:
            return Response({"detail": "Xatolik yuz berdi. Qayta urinib ko'ring."}, status=500)

        return Response(status=204)


class OrderGoalViewSet(viewsets.ModelViewSet):
    """
    Ko'rish — 'all_organization' bo'lsa hammasi, bo'lmasa o'z tashkiloti.
    Yaratish/Tahrirlash/O'chirish — tegishli permission (add/change/delete_ordergoal).
    """

    serializer_class = OrderGoalSerializer
    permission_classes = [OrderGoalPermission]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["employee", "goal"]

    def get_queryset(self):
        qs = OrderGoal.objects.select_related('employee', 'goal').all()
        user = self.request.user

        if user.is_superuser or user.has_perm('main.permission_employee'):
            return qs

        employee = getattr(user, "employee", None)
        if not employee or not employee.organization_id:
            return qs.none()

        return qs.filter(employee__organization_id=employee.organization_id)


class MaterialUserViewSet(viewsets.ModelViewSet):
    """
    Ko'rish — 'all_organization' bo'lsa hammasi, bo'lmasa o'z tashkiloti
    (sender yoki receiver orqali).
    Yaratish/Tahrirlash/O'chirish — tegishli permission (add/change/delete_materialuser).
    """

    serializer_class = MaterialUserSerializer
    permission_classes = [MaterialUserPermission]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["sender", "receiver"]

    def get_queryset(self):
        qs = MaterialUser.objects.select_related('sender', 'receiver').all()
        user = self.request.user

        if user.is_superuser or user.has_perm('main.permission_employee'):
            return qs

        employee = getattr(user, "employee", None)
        if not employee or not employee.organization_id:
            return qs.none()

        return qs.filter(
            models.Q(sender__organization_id=employee.organization_id) |
            models.Q(receiver__organization_id=employee.organization_id)
        ).distinct()


class DeedViewSet(viewsets.ModelViewSet):
    """
    To'liq CRUD — har qanday employee profiliga ega xodim ko'radi, qo'shadi,
    tahrirlaydi, o'chiradi. Cheklov yo'q.
    """

    queryset = Deed.objects.select_related(
        'organization', 'sender', 'receiver', 'user', 'order',
    ).prefetch_related('deedconsent_set').all().order_by('-id')
    serializer_class = DeedSerializer
    permission_classes = [DeedPermission]
    pagination_class = StandardResultsPagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]  # fayl yuklash uchun
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["organization", "sender", "receiver", "user", "status", "order"]
    search_fields = ["code", "body", "message_sender", "message_receiver", "message_user"]


class DeedConsentViewSet(viewsets.ModelViewSet):
    """
    To'liq CRUD — har qanday employee profiliga ega xodim ko'radi, qo'shadi,
    tahrirlaydi, o'chiradi. Cheklov yo'q.
    """

    queryset = DeedConsent.objects.select_related('deed', 'employee').all()
    serializer_class = DeedConsentSerializer
    permission_classes = [DeedConsentPermission]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["deed", "employee", "status"]


class LiableViewSet(viewsets.ModelViewSet):
    """
    Ko'rish — o'z tashkilotidagi xodimlarning shartnoma-kategoriya bog'lanishlari.
    Yaratish/Tahrirlash/O'chirish — tegishli permission (add/change/delete_liable).
    """

    serializer_class = LiableSerializer
    permission_classes = [LiablePermission]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["employee", "contract", "category"]

    def get_queryset(self):
        qs = Liable.objects.select_related('employee', 'contract', 'category').all()
        user = self.request.user

        if user.is_superuser:
            return qs

        employee = getattr(user, "employee", None)
        if not employee or not employee.organization_id:
            return qs.none()

        return qs.filter(employee__organization_id=employee.organization_id)


class MaterialMovementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Faqat KO'RISH — material harakati jurnali.
    'all_organization' bo'lsa hammasi, bo'lmasa faqat o'z tashkilotidagi
    (material.organization orqali) harakatlar.
    """

    serializer_class = MaterialMovementSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["material", "employee", "user", "status"]
    search_fields = ["body"]

    def get_queryset(self):
        qs = MaterialMovement.objects.select_related('user', 'material', 'employee').all()
        user = self.request.user

        if not getattr(user, 'employee', None):
            return qs.none()

        if user.is_superuser:
            return qs

        employee = user.employee
        if not employee.organization_id:
            return qs.none()

        return qs.filter(material__organization_id=employee.organization_id)