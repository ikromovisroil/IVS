import logging
from datetime import datetime
from decimal import Decimal
from django.utils.dateparse import parse_date
from django.utils.decorators import method_decorator
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema, no_body
from django.utils import timezone
from django.contrib.auth.models import Permission
from django.db.models import Exists, OuterRef, Prefetch, Q
from django.db import DatabaseError, transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.core.files.base import ContentFile
import secrets
from django.http import Http404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from django.http import FileResponse
from bot.notify import send_telegram_message, rating_markup, barn_approved_markup
from main.html_pdf import _create_deed_for_order, deed_to_pdf_bytes, add_text_watermark_pdf_bytes, HtmlPdfError
from main.push_views import (
    notify_deed_sender, notify_deed_watchers, notify_order_status_change, notify_eligible_employees_new_order,
    send_push_notification,
)
from main.order_views import _assignee_candidates, _restore_given_materials
from main.views import _save_deed_pdf, _deed_consents_open, _can_add_consents, _deed_consent_org_ids
from rest_framework import viewsets, mixins
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser


from .serializers import *
from .permissions import *
from .material_report import allowed_report_employees, build_report, parse_period
from .pagination import *

# `import *` lar (main.models) Django'ning ValidationError/PermissionDenied nomlarini almashtirib yuborgani uchun
# DRF variantlari ENG OXIRIDA import qilinadi (aks holda 400 o'rniga 500 xato chiqadi).
from rest_framework.exceptions import PermissionDenied, ValidationError  # noqa: E402


class OrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["type"]
    search_fields = ["name", "inn"]

    def get_queryset(self):
        qs = Organization.objects.all().order_by('name', 'id')
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
        qs = Region.objects.all().order_by('name', 'id')
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
        qs = Department.objects.select_related('organization', 'region').all().order_by('name', 'id')
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
        ).all().order_by('name', 'id')
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
        ).all().order_by('name', 'id')
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


class RankViewSet(viewsets.ReadOnlyModelViewSet):
    """Faqat KO'RISH — barcha autentifikatsiyadan o'tgan foydalanuvchilar ko'radi."""
    queryset = Rank.objects.all()
    serializer_class = RankSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [SearchFilter]
    search_fields = ["name"]


class EmployeeViewSet(viewsets.ModelViewSet):
    """
    Saytdagi (main/views.py: employee, employee_create/update/delete) bilan bir xil:
    Ko'rish — 'view_employee'; 'all_organization' bo'lsa hammasi, aks holda faqat o'z tashkiloti.
    Qo'shish — 'add_employee' (User avtomatik yaratiladi, kirish SSO orqali).
    Tahrirlash — 'change_employee' (tashkilot o'zgarmaydi; joylashuv o'zgarsa texnikalar bilan nima qilish
    `technics_action` orqali). O'chirish — 'delete_employee' (o'zini o'chirib bo'lmaydi, User faolsizlanadi).
    """

    serializer_class = EmployeeSerializer
    permission_classes = [EmployeePermission]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["organization", "department", "directorate", "division", "region", "rank"]
    search_fields = ["last_name", "first_name", "father_name", "pinfl"]

    def get_serializer_class(self):
        if self.action == 'create':
            return EmployeeCreateSerializer
        if self.action in ('update', 'partial_update'):
            return EmployeeUpdateSerializer
        return EmployeeSerializer

    def get_queryset(self):
        qs = Employee.objects.select_related(
            'organization', 'department', 'region', 'rank', 'user',
        ).all()
        user = self.request.user

        if user.is_superuser or user.has_perm('main.all_organization'):
            return qs

        employee = getattr(user, "employee", None)
        if not employee or not employee.organization_id:
            return qs.none()

        return qs.filter(organization_id=employee.organization_id)

    def _current_employee(self):
        employee = getattr(self.request.user, "employee", None)
        if not employee:
            raise PermissionDenied("Employee yo'q")
        return employee

    def perform_create(self, serializer):
        current = self._current_employee()
        data = serializer.validated_data
        organization = data['organization']

        if not self.request.user.has_perm("main.all_organization"):
            if organization.id != current.organization_id:
                raise PermissionDenied("Boshqa tashkilotga xodim qo'sha olmaysiz")

        from django.contrib.auth import get_user_model
        from django.utils.crypto import get_random_string
        from main.views import _generate_username

        User = get_user_model()
        with transaction.atomic():
            username = _generate_username(data.get('pinfl') or "", data['first_name'], data['last_name'])
            user = User.objects.create_user(
                username=username,
                password=get_random_string(
                    length=12, allowed_chars="abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
                ),
            )
            user.is_active = True
            user.save(update_fields=["is_active"])

            emp, _ = Employee.objects.get_or_create(user=user)
            for field in ('pinfl', 'first_name', 'last_name', 'organization',
                          'department', 'directorate', 'division', 'rank'):
                setattr(emp, field, data.get(field))
            emp.father_name = (data.get('father_name') or "").strip() or None
            emp.phone = (data.get('phone') or "").strip() or None
            emp.save()
            serializer.instance = emp

    def perform_update(self, serializer):
        data = serializer.validated_data
        technics_action = data.pop('technics_action', None) or 'release'
        emp = serializer.instance
        old = (emp.department_id, emp.directorate_id, emp.division_id)

        with transaction.atomic():
            for key in ('father_name', 'phone'):
                if key in data:
                    data[key] = (data[key] or "").strip() or None
            emp = serializer.save()
            new = (emp.department_id, emp.directorate_id, emp.division_id)
            if new == old:
                return

            technics = Technics.objects.filter(employee_id=emp.id, is_active=True)
            if not technics.exists():
                return
            if technics_action == 'with':
                technics.update(
                    employee=emp, department_id=new[0], directorate_id=new[1],
                    division_id=new[2], status='active',
                )
            elif technics_action == 'stay':
                technics.update(
                    employee=None, department_id=old[0], directorate_id=old[1],
                    division_id=old[2], status='active',
                )
            else:
                technics.update(
                    employee=None, department=None, directorate=None, division=None, status='free',
                )

    @action(detail=True, methods=['get', 'put'], url_path='permissions')
    def manage_permissions(self, request, pk=None):
        """
        Xodim ruxsatlari (saytdagi "ruxsatlar" oynasi): GET — joriy holat va tanlash variantlari;
        PUT {"permissions": {"add_order": true, ...}, "goals": [id], "categories": [id], "contracts": [id],
        "material_categories": [id]} — faqat yuborilgan kalitlar o'zgaradi. 'permission_employee' (PUT uchun
        qo'shimcha 'change_employee') kerak.
        """
        from . import roles

        target = self.get_object()
        current = self._current_employee()
        roles.check_access(request, target.organization_id, current, writing=request.method == "PUT")
        if request.method == "PUT":
            result = roles.apply(request, current, target, request.data)
            data = roles.state(request.user, current, target)
            data.update(result)
            return Response(data)
        return Response(roles.state(request.user, current, target))

    def perform_destroy(self, instance):
        current = self._current_employee()
        if instance.id == current.id:
            raise ValidationError({"detail": "O'zingizni o'chira olmaysiz"})
        with transaction.atomic():
            user = instance.user
            instance.delete()
            if user:
                user.is_active = False
                user.save(update_fields=["is_active"])


class GroupViewSet(viewsets.ReadOnlyModelViewSet):
    """Faqat KO'RISH — barcha autentifikatsiyadan o'tgan foydalanuvchilar ko'radi."""
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [SearchFilter]
    search_fields = ["name"]


class ContractViewSet(viewsets.ReadOnlyModelViewSet):
    """Faqat KO'RISH: shartnomalar ro'yxati (saytda faqat ruxsatlar oynasida ko'rinadi). 'permission_employee' kerak."""
    queryset = Contract.objects.order_by('id')
    serializer_class = ContractSerializer
    permission_classes = [PermissionManagerPermission]
    pagination_class = StandardResultsPagination
    filter_backends = [SearchFilter]
    search_fields = ["name"]


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Faqat KO'RISH — barcha autentifikatsiyadan o'tgan foydalanuvchilar ko'radi."""
    queryset = Category.objects.select_related('group').prefetch_related('contracts').all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["group", "contracts"]
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

    OPTIONAL_TEXT_FIELDS = ('parametr', 'inventory', 'serial', 'mac', 'ip', 'year', 'address')

    def get_serializer_class(self):
        if self.action == 'create':
            return TechnicsCreateSerializer
        if self.action in ('update', 'partial_update'):
            return TechnicsUpdateSerializer
        if self.action == 'assign':
            return TechnicsAssignSerializer
        return TechnicsSerializer

    def get_queryset(self):
        qs = Technics.objects.select_related(
            'group', 'category', 'region', 'organization',
            'department', 'directorate', 'division', 'employee',
        ).prefetch_related(
            Prefetch('structure_set', queryset=Structure.objects.filter(is_active=True), to_attr='active_structures'),
        ).filter(is_active=True)
        user = self.request.user

        # Saytdagi ro'yxat (barn_tex) kabi: texnikalarni faqat xodimga biriktirilgan kategoriyalar (Liable) bo'yicha
        # ko'radi. Tahrirlash/o'chirish/biriktirish/QR saytda faqat tashkilot va hudud bilan cheklanadi.
        if self.action in ('list', 'retrieve') and not user.is_superuser:
            emp = getattr(user, "employee", None)
            if emp:
                liable_ids = Liable.categorys.through.objects.filter(
                    liable__employee=emp
                ).values_list("category_id", flat=True)
                qs = qs.filter(category_id__in=liable_ids)

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

    # ---- yordamchilar (saytdagi main/views.py qoidalari bilan bir xil) ----

    def _current_employee(self):
        employee = getattr(self.request.user, "employee", None)
        if not employee:
            raise PermissionDenied("Employee yo'q")
        return employee

    def _check_organization(self, organization):
        """Umumiy tashkilot huquqi bo'lmasa — faqat o'z tashkilotiga texnika qo'sha/ko'chira oladi."""
        if organization is None or self.request.user.has_perm("main.all_organization"):
            return
        if organization.id != self._current_employee().organization_id:
            raise PermissionDenied("Bu tashkilot uchun ruxsat yo'q")

    def _check_duplicate_serial(self, serial, organization, exclude_pk=None):
        serial = (serial or "").strip()
        if not serial or serial.upper() == "B/N" or organization is None:
            return
        qs = Technics.objects.filter(serial__iexact=serial, organization=organization, is_active=True)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if qs.exists():
            raise ValidationError({"serial": f"Bu serial raqamli uskuna allaqachon mavjud: {serial}"})

    def _cleaned(self, validated):
        """Bo'sh matnlar -> None, bo'sh narx -> 0 (saytdagidek)."""
        out = {}
        for key in self.OPTIONAL_TEXT_FIELDS:
            if key in validated:
                out[key] = (validated[key] or "").strip() or None
        if 'price' in validated:
            out['price'] = validated['price'] or Decimal("0")
        return out

    # ---- amallar ----

    def perform_create(self, serializer):
        employee = self._current_employee()
        data = serializer.validated_data
        organization = data.get('organization')
        self._check_organization(organization)
        with transaction.atomic():
            self._check_duplicate_serial(data.get('serial'), organization)
            extra = self._cleaned(data)
            if employee.region_id:
                extra['region_id'] = employee.region_id
            serializer.save(**extra)

    def perform_update(self, serializer):
        data = serializer.validated_data
        instance = serializer.instance
        organization = data.get('organization', instance.organization)
        if 'organization' in data:
            self._check_organization(organization)
        with transaction.atomic():
            self._check_duplicate_serial(
                data.get('serial', instance.serial), organization, exclude_pk=instance.pk
            )
            serializer.save(**self._cleaned(data))

    def perform_destroy(self, instance):
        """Haqiqiy o'chirish o'rniga is_active=False; xodimga biriktirilgan bo'lsa - bo'shatiladi."""
        instance.is_active = False
        fields = ['is_active']
        if instance.employee_id:
            instance.employee = None
            instance.status = 'free'
            fields += ['employee', 'status']
        instance.save(update_fields=fields)

    @action(detail=True, methods=['post'], url_path='assign')
    def assign(self, request, pk=None):
        """
        Biriktirish: POST /api/technics/{id}/assign/
        - employee berilsa - xodimga (u texnika tashkilotidan bo'lishi shart);
        - department/directorate/division berilsa - strukturaga;
        - hech narsa berilmasa - bo'shatiladi.
        """
        obj = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        emp = data.get('employee')
        dep = data.get('department')
        drt = data.get('directorate')
        div = data.get('division')

        with transaction.atomic():
            tex = Technics.objects.select_for_update(of=("self",)).get(pk=obj.pk)

            if emp:
                if emp.organization_id != tex.organization_id:
                    raise PermissionDenied("Xodim bu tashkilotga tegishli emas")
                tex.employee, tex.department, tex.directorate, tex.division = emp, None, None, None
                tex.status = 'active'
            elif dep or drt or div:
                if dep and dep.organization_id != tex.organization_id:
                    raise ValidationError({"department": "Bo'lim bu tashkilotga tegishli emas"})
                if drt:
                    if dep and drt.department_id != dep.id:
                        raise ValidationError({"directorate": "Boshqarma tanlangan bo'limga tegishli emas"})
                    if not dep and (not drt.department_id or drt.department.organization_id != tex.organization_id):
                        raise ValidationError({"directorate": "Boshqarma bu tashkilotga tegishli emas"})
                if div:
                    if drt and div.directorate_id != drt.id:
                        raise ValidationError({"division": "Bo'linma tanlangan boshqarmaga tegishli emas"})
                    if not drt:
                        parent = div.directorate
                        if not parent or not parent.department_id or parent.department.organization_id != tex.organization_id:
                            raise ValidationError({"division": "Bo'linma bu tashkilotga tegishli emas"})
                tex.employee, tex.department, tex.directorate, tex.division = None, dep, drt, div
                tex.status = 'active'
            else:
                tex.employee, tex.department, tex.directorate, tex.division = None, None, None, None
                tex.status = 'free'

            tex.save(update_fields=['employee', 'department', 'directorate', 'division', 'status'])

        return Response(TechnicsSerializer(tex).data)

    @action(detail=True, methods=['post'], url_path='unassign')
    def unassign(self, request, pk=None):
        """Bo'shatish: POST /api/technics/{id}/unassign/ - xodim va struktura olib tashlanadi, holat 'free'."""
        obj = self.get_object()
        with transaction.atomic():
            tex = Technics.objects.select_for_update(of=("self",)).get(pk=obj.pk)
            tex.employee = tex.department = tex.directorate = tex.division = None
            tex.status = 'free'
            tex.save(update_fields=['employee', 'department', 'directorate', 'division', 'status'])
        return Response(TechnicsSerializer(tex).data)

    @action(detail=True, methods=['get'], url_path='qr')
    def qr(self, request, pk=None):
        """QR kodni to'g'ridan-to'g'ri fayl sifatida qaytaradi: GET /api/technics/{id}/qr/"""
        technics = self.get_object()

        if not technics.qr_code:
            raise Http404("QR kod topilmadi")
        try:
            handle = technics.qr_code.open('rb')
        except (FileNotFoundError, ValueError):
            raise Http404("QR kod topilmadi")

        return FileResponse(
            handle,
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
    Saytdagi (main/views.py: extra_tex*) bilan bir xil. Huquqlar TEXNIKA huquqlari:
    ko'rish/tahrirlash/biriktirish — 'change_technics', qo'shish — 'add_technics', o'chirish — 'delete_technics'.
    Ko'rish — o'z tashkiloti/hududi bo'yicha cheklab, faqat is_active=True.
    O'chirish — soft delete (is_active=False), texnikaga biriktirilgan bo'lsa ajratiladi.
    Biriktirish — POST /api/structures/{id}/assign/ {"technics": id}; ajratish — .../unassign/.
    """

    permission_classes = [StructurePermission]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["category", "organization", "region", "technics", "status"]
    search_fields = ["name", "inventory", "serial", "year"]

    def get_serializer_class(self):
        if self.action == 'create':
            return StructureCreateSerializer
        if self.action in ('update', 'partial_update'):
            return StructureUpdateSerializer
        if self.action == 'assign':
            return StructureAssignSerializer
        if self.action == 'unassign':
            return StructureUnassignSerializer
        return StructureSerializer

    def get_queryset(self):
        qs = Structure.objects.select_related(
            'category', 'organization', 'region', 'technics',
        ).filter(is_active=True).order_by('-id')
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

    # ---- yordamchilar ----

    def _current_employee(self):
        employee = getattr(self.request.user, "employee", None)
        if not employee:
            raise PermissionDenied("Employee yo'q")
        return employee

    def _check_organization(self, organization):
        if organization is None or self.request.user.has_perm("main.all_organization"):
            return
        if organization.id != self._current_employee().organization_id:
            raise PermissionDenied("Bu tashkilot uchun ruxsat yo'q")

    def _check_duplicate_serial(self, serial, organization, exclude_pk=None):
        serial = (serial or "").strip()
        if not serial or organization is None:
            return
        qs = Structure.objects.filter(serial__iexact=serial, organization=organization, is_active=True)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if qs.exists():
            raise ValidationError({"serial": f"Bu serial raqamli qurilma allaqachon mavjud: {serial}"})

    @staticmethod
    def _cleaned(validated):
        out = {}
        for key in ('parametr', 'inventory', 'serial', 'year'):
            if key in validated:
                out[key] = (validated[key] or "").strip() or None
        return out

    # ---- amallar ----

    def perform_create(self, serializer):
        employee = self._current_employee()
        data = serializer.validated_data
        organization = data.get('organization')
        self._check_organization(organization)
        with transaction.atomic():
            extra = self._cleaned(data)
            self._check_duplicate_serial(extra.get('serial'), organization)
            if employee.region_id:
                extra['region_id'] = employee.region_id
            serializer.save(**extra)

    def perform_update(self, serializer):
        data = serializer.validated_data
        instance = serializer.instance
        organization = data.get('organization', instance.organization)
        if 'organization' in data:
            self._check_organization(organization)
        with transaction.atomic():
            extra = self._cleaned(data)
            self._check_duplicate_serial(
                extra.get('serial', instance.serial), organization, exclude_pk=instance.pk
            )
            if 'price' in data and data['price'] is None:
                extra['price'] = Decimal("0")
            serializer.save(**extra)

    def perform_destroy(self, instance):
        """Soft delete; texnikaga biriktirilgan bo'lsa ajratiladi (saytdagidek)."""
        instance.is_active = False
        fields = ['is_active']
        if instance.technics_id:
            instance.technics = None
            fields.append('technics')
        instance.save(update_fields=fields)

    @action(detail=True, methods=['post'], url_path='assign')
    def assign(self, request, pk=None):
        """Qurilmani texnikaga biriktirish: POST /api/structures/{id}/assign/ {"technics": id}"""
        from main.views import _check_technics_scope

        obj = self.get_object()
        employee = self._current_employee()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tex = serializer.validated_data['technics']

        with transaction.atomic():
            tex = get_object_or_404(Technics.objects.select_for_update(of=("self",)), pk=tex.pk, is_active=True)
            extra = Structure.objects.select_for_update(of=("self",)).get(pk=obj.pk)

            # Ikkalasi ham so'rovchining doirasida bo'lishi kerak
            _check_technics_scope(request, employee, tex)

            if extra.organization_id != tex.organization_id:
                raise ValidationError({"detail": "Qurilma boshqa tashkilotga tegishli"})
            if extra.technics_id:
                raise ValidationError({"detail": "Bu qo'shimcha texnika allaqachon biriktirilgan"})

            extra.technics = tex
            extra.status = "active"
            extra.save(update_fields=["technics", "status"])

        return Response(StructureSerializer(extra, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='unassign')
    def unassign(self, request, pk=None):
        """Qurilmani texnikadan ajratish: POST /api/structures/{id}/unassign/ ({"technics": id} ixtiyoriy)"""
        obj = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tex = serializer.validated_data.get('technics')

        with transaction.atomic():
            extra = Structure.objects.select_for_update(of=("self",)).get(pk=obj.pk)
            if not extra.technics_id:
                raise ValidationError({"detail": "Bu qo'shimcha texnika allaqachon bo'sh"})
            if tex and extra.technics_id != tex.id:
                raise ValidationError({"detail": "Bu qo'shimcha texnika ushbu uskunaga tegishli emas"})
            extra.technics = None
            extra.status = "free"
            extra.save(update_fields=["technics", "status"])

        return Response(StructureSerializer(extra, context={'request': request}).data)


class UnitViewSet(viewsets.ReadOnlyModelViewSet):
    """Faqat KO'RISH — barcha autentifikatsiyadan o'tgan foydalanuvchilar ko'radi."""
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [SearchFilter]
    search_fields = ["name"]


class MaterialCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Faqat KO'RISH: material kategoriyalari — o'z tashkilotiniki (yoki umumiy); 'all_organization' bo'lsa hammasi."""
    serializer_class = MaterialCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [SearchFilter]
    search_fields = ["name"]

    def get_queryset(self):
        qs = MaterialCategory.objects.order_by('name', 'id')
        user = self.request.user
        if user.is_superuser or user.has_perm("main.all_organization"):
            return qs
        employee = getattr(user, "employee", None)
        if not employee or not employee.organization_id:
            return qs.none()
        return qs.filter(models.Q(organization_id=employee.organization_id) | models.Q(organization__isnull=True))


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
        if self.action == 'service':
            return MaterialServiceSerializer
        return MaterialSerializer

    # ---- ko'rish doirasi: saytdagi barn_mat bilan bir xil ----

    def _current_employee(self):
        employee = getattr(self.request.user, "employee", None)
        if not employee:
            raise PermissionDenied("Employee yo'q")
        return employee

    def _visible_employee_ids(self, user, employee):
        """
        all_material_employee — tashkilotdagi 'shop_employee' huquqli xodimlar;
        aks holda — o'ziga MaterialUser orqali biriktirilgan xodimlar (+ o'zi, agar o'zi javobgar bo'lsa).
        """
        if user.has_perm("main.all_material_employee"):
            perm = Permission.objects.filter(codename="shop_employee", content_type__app_label="main").first()
            if not perm:
                return []
            return list(
                Employee.objects.filter(
                    Q(user__groups__permissions=perm) | Q(user__user_permissions=perm),
                    organization_id=employee.organization_id,
                ).values_list("id", flat=True).distinct()
            )

        ids = set(MaterialUser.objects.filter(receiver=employee).values_list("sender_id", flat=True))
        if Material.objects.filter(employee=employee, organization_id=employee.organization_id).exists():
            ids.add(employee.id)
        ids.discard(None)
        return list(ids)

    def get_queryset(self):
        user = self.request.user
        employee = getattr(user, "employee", None)
        if not employee or not employee.organization_id:
            return Material.objects.none()

        org_qs = Material.objects.select_related(
            'category', 'organization', 'unit', 'employee',
        ).filter(organization_id=employee.organization_id, is_active=True)

        # Saytda tahrirlash/o'chirishda faqat tashkilot tekshiriladi
        if self.action in ('update', 'partial_update', 'destroy'):
            return org_qs

        # Ro'yxat/ko'rish: saytdagidek faqat soni > 0 va ko'rishga ruxsat berilgan xodimlarniki
        return org_qs.filter(
            number__gt=0,
            employee_id__in=self._visible_employee_ids(user, employee),
        )


    @action(detail=False, methods=['get'], url_path='report/employees')
    def report_employees(self, request):
        """Hisobotda tanlash mumkin bo'lgan xodimlar (saytdagi mat_info dropdown'i)."""
        employee = self._current_employee()
        rows = allowed_report_employees(request.user, employee).order_by("last_name", "first_name")
        return Response([{"id": e.id, "full_name": e.full_name} for e in rows])

    @action(detail=False, methods=['get'], url_path='report')
    def report(self, request):
        """
        Material kirim-chiqim hisoboti (saytdagi mat_info): GET /api/materials/report/?employee=<id>&date1=&date2=&name=
        employee majburiy; sana berilmasa joriy oy. Har bir material uchun boshlang'ich qoldiq, kirim, chiqim,
        joriy qoldiq (soni va summasi) va harakatlar tarixi. 20 tadan sahifalanadi.
        """
        employee = self._current_employee()
        emp_raw = (request.query_params.get("employee") or "").strip()
        if not emp_raw.isdigit():
            raise ValidationError({"employee": "Xodim tanlanmagan"})
        date1, date2 = parse_period(request.query_params)
        rows = build_report(
            request.user, employee, int(emp_raw), date1, date2,
            (request.query_params.get("name") or "").strip(),
        )
        page = self.paginate_queryset(rows)
        response = self.get_paginated_response(page)
        response.data["period"] = {"date1": date1.isoformat(), "date2": date2.isoformat()}
        return response

    # ---- amallar ----

    def perform_create(self, serializer):
        employee = self._current_employee()
        serializer.save(organization_id=employee.organization_id, employee=employee)

    @staticmethod
    def _snapshot(mat):
        return {
            "name": mat.name,
            "unit": mat.unit.name if mat.unit else "—",
            "category": mat.category.name if mat.category else "—",
            "number": mat.number,
            "code": mat.code or "—",
            "price": mat.price or "—",
            "year": mat.year or "—",
        }

    def perform_update(self, serializer):
        with transaction.atomic():
            old = self._snapshot(serializer.instance)
            mat = serializer.save()
            if mat.price is None:
                mat.price = Decimal("0")
                mat.save(update_fields=['price'])
            mat = Material.objects.select_related('unit', 'category', 'employee').get(pk=mat.pk)
            new = self._snapshot(mat)

            labels = {
                "name": "Nomi", "unit": "Birligi", "category": "Kategoriya", "number": "Soni",
                "code": "Kodi", "price": "Narxi", "year": "Yili",
            }
            changes = [f"{label}: {old[k]} → {new[k]}" for k, label in labels.items() if old[k] != new[k]]
            if not changes:
                return

            diff = new["number"] - old["number"]
            if diff > 0:
                user_, emp_, income, outcome = None, mat.employee, diff, None
            elif diff < 0:
                user_, emp_, income, outcome = mat.employee, None, None, -diff
            else:
                user_, emp_, income, outcome = None, None, None, None

            MaterialMovement.objects.create(
                material=mat, user=user_, employee=emp_, status='edited',
                income=income, outcome=outcome, body="\n".join(changes),
            )

    def perform_destroy(self, instance):
        """Soft delete + harakat jurnaliga 'deleted' yozuvi (saytdagidek)."""
        with transaction.atomic():
            instance.is_active = False
            instance.save(update_fields=['is_active'])
            MaterialMovement.objects.create(
                material=instance, user=instance.employee, employee=None, status='deleted',
                outcome=instance.number, body=f"Material o'chirildi: {instance.id}",
            )

    @action(detail=False, methods=['post'], url_path='service')
    def service(self, request):
        """
        Materialni sarflash: POST /api/materials/service/ {material_id, give_number, body}
        Saytdagi material_service bilan bir xil: faqat o'z tashkiloti, egasi / unga biriktirilgan /
        all_material_employee; soni kamayadi va jurnalga 'service' yoziladi.
        """
        employee = self._current_employee()
        serializer = MaterialServiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            mat = get_object_or_404(
                Material.objects.select_for_update(of=("self",)), pk=data['material_id']
            )
            if mat.organization_id != employee.organization_id:
                raise PermissionDenied("Sizga ruxsat yo'q")

            is_owner = mat.employee_id == employee.id
            is_delegated = mat.employee_id is not None and MaterialUser.objects.filter(
                sender_id=mat.employee_id, receiver=employee
            ).exists()
            if not (is_owner or is_delegated or request.user.has_perm("main.all_material_employee")):
                raise PermissionDenied("Sizga ruxsat yo'q")

            if not mat.is_active:
                raise ValidationError({"detail": "Material allaqachon o'chirilgan"})
            if data['give_number'] > mat.number:
                raise ValidationError({"give_number": "Mavjud sonidan ko'p miqdor kiritildi"})

            MaterialMovement.objects.create(
                material=mat, user=mat.employee, status='service',
                outcome=data['give_number'], body=(data.get('body') or '').strip(),
            )
            mat.number -= data['give_number']
            mat.save(update_fields=["number"])

        return Response(MaterialSerializer(mat, context={'request': request}).data)

    @action(detail=False, methods=['post'], url_path='give')
    def give(self, request):
        """
        Bir nechta materialni bitta xodimga berish: POST /api/materials/give/
        'change_material' ruxsati kerak (saytdagi material_attach kabi).
        Butun savat bitta transaction ichida ishlaydi — biror material xato bersa,
        hech biri saqlanmaydi.
        """
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
                    dst.is_active = True

                    dst.save(update_fields=["number", "price", "unit", "is_active"])
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

                giver = src.employee

                MaterialMovement.objects.create(
                    material=src,
                    user=giver,
                    employee=emp,
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
                    user=giver,
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
    Faqat KO'RISH: xodimga ruxsat etilgan material kategoriyalari (saytda faqat ruxsatlar oynasida ko'rinadi).
    'permission_employee' kerak; faqat o'z tashkiloti.
    """

    serializer_class = MaterialEmployeeSerializer
    permission_classes = [PermissionManagerPermission]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["employee", "category"]
    search_fields = ["employee__last_name", "employee__first_name", "category__name"]

    def get_queryset(self):
        qs = MaterialEmployee.objects.select_related('employee').prefetch_related('category').order_by('id')
        return _org_scoped(qs, self.request.user, "employee__organization_id")


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


ORDER_ROLE_PARAM = openapi.Parameter(
    'role', openapi.IN_QUERY, type=openapi.TYPE_STRING,
    enum=['sender', 'sender_archive', 'sender_user', 'receiver_new', 'receiver_active', 'receiver_archive',
          'barn_sender', 'barn_sender_archive', 'barn_receiver_new', 'barn_receiver_active', 'barn_receiver_archive',
          'barn_agrement', 'barn_agrement_archive'],
    description="ATM arizalari: sender — yuborganlarim (yangi/jarayonda/bajarilgan), sender_archive — arxivim, "
                "sender_user — nomidan yuborganlarim (add_order), receiver_new — bajaruvchi uchun yangi arizalar (change_order), "
                "receiver_active — qabul qilganlarim, receiver_archive — bajarilganlar arxivi. "
                "Material arizasi (omborxona): barn_sender / barn_sender_archive — yuboruvchi, "
                "barn_receiver_new / barn_receiver_active / barn_receiver_archive — omborxonachi (change_order), "
                "barn_agrement / barn_agrement_archive — tasdiqlovchi (confirm_order). "
                "Berilmasa — o'ziga aloqador arizalar.",
)
DEED_ROLE_PARAM = openapi.Parameter(
    'role', openapi.IN_QUERY, type=openapi.TYPE_STRING,
    enum=['created', 'created_archive', 'to_sign', 'signed', 'to_agree', 'agreed'],
    description="Hujjat ro'yxati (saytdagi sahifalar): created — yuborganlarim (faol), created_archive — yuborganlarim arxivi, "
                "to_sign — menga kelgan imzo, signed — imzolaganlarim/rad etganlarim, "
                "to_agree — kelishuvim kutilayotganlar, agreed — kelishganlarim. Berilmasa — o'zim ishtirok etgan hujjatlar.",
)


@method_decorator(name='list', decorator=swagger_auto_schema(manual_parameters=[ORDER_ROLE_PARAM]))
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
        if self.action == 'finish':
            return OrderFinishSerializer
        if self.action == 'decide':
            return OrderDecideSerializer
        if self.action == 'confirm':
            return OrderConfirmSerializer
        if self.action == 'accept':
            return OrderAcceptSerializer
        return OrderSerializer

    def _base_queryset(self):
        qs = Order.objects.select_related(
            'goal', 'goal__organization', 'sender', 'receiver', 'user', 'technics',
        ).prefetch_related('materials__material', 'deeds').all()

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


    # =====================================================================
    # ATM (texnik xizmat) arizasi — saytdagi order_views.py bilan bir xil.
    # Material arizasi (goal.organization.type == 'client') hozircha avvalgi (legacy) mantiqda.
    # =====================================================================

    TERMINAL = ["approved", "accepted", "canceled", "rejected"]

    def _employee(self):
        employee = getattr(self.request.user, "employee", None)
        if not employee:
            raise PermissionDenied("Employee yo'q")
        return employee

    @staticmethod
    def _goal_type(pk):
        return Order.objects.filter(pk=pk).values_list('goal__organization__type', flat=True).first()

    @staticmethod
    def _best_effort(func, *args, **kwargs):
        """Push/Telegram yuborilmasa ham asosiy amal bekor bo'lmasin."""
        try:
            func(*args, **kwargs)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Ariza bildirishnomasi yuborilmadi")

    def _receiver_guard(self, employee):
        if getattr(employee.organization, "type", None) == "client":
            raise PermissionDenied("Sizga ruxsat yo'q")

    def _role_queryset(self, role, employee):
        """Saytdagi ro'yxatlar: ?role=sender | sender_archive | sender_user | receiver_new | receiver_active | receiver_archive"""
        user = self.request.user
        # Ro'yxatlar saytdagidek alohida mantiqda (aloqadorlik cheklovidan mustaqil)
        qs = Order.objects.select_related(
            'goal', 'goal__organization', 'sender', 'receiver', 'user', 'technics',
        ).prefetch_related('materials__material', 'deeds').filter(goal__organization__type="worker")

        if role == "sender":
            return qs.filter(sender=employee, status__in=["viewed", "process", "finished"]).order_by("-id")
        if role == "sender_archive":
            return qs.filter(sender=employee, status__in=self.TERMINAL).order_by("-id")
        if role == "sender_user":
            if not user.has_perm("main.add_order"):
                raise PermissionDenied("Sizga ruxsat yo'q")
            return qs.filter(user=employee).order_by("-id")

        if role in ("receiver_new", "receiver_active", "receiver_archive"):
            if not user.has_perm("main.change_order"):
                raise PermissionDenied("Sizga ruxsat yo'q")
            self._receiver_guard(employee)
            if role == "receiver_new":
                goal_ids = OrderGoal.goal.through.objects.filter(
                    ordergoal__employee=employee
                ).values_list("goal_id", flat=True)
                return qs.filter(
                    sender__region=employee.region, goal_id__in=goal_ids, status="viewed",
                ).order_by("-id")
            if role == "receiver_active":
                return qs.filter(
                    receiver=employee, goal__organization=employee.organization,
                    status__in=["process", "finished"],
                ).order_by("-id")
            return qs.filter(receiver=employee, status__in=self.TERMINAL).order_by("-date_edit")

        if role.startswith("barn_"):
            return self._barn_role_queryset(role, employee)

        raise ValidationError({"role": "Noto'g'ri qiymat. Mumkin: sender, sender_archive, sender_user, "
                                       "receiver_new, receiver_active, receiver_archive, barn_sender, barn_sender_archive, "
                                       "barn_receiver_new, barn_receiver_active, barn_receiver_archive, barn_agrement, "
                                       "barn_agrement_archive"})

    def get_queryset(self):
        employee = getattr(self.request.user, "employee", None)
        role = (self.request.query_params.get('role') or '').strip()
        if role and employee and self.action == 'list':
            return self._role_queryset(role, employee)
        base = self._base_queryset()
        if self.action == 'retrieve' and employee:
            # Bajaruvchi hali qabul qilmagan (o'ziga ruxsat etilgan) yangi arizani ham ko'ra olsin
            cond = models.Q(pk__in=base.values('pk'))
            for r in ("receiver_new", "barn_receiver_new", "barn_agrement"):
                try:
                    cond |= models.Q(pk__in=self._role_queryset(r, employee).values('pk'))
                except PermissionDenied:
                    pass
            return Order.objects.select_related(
                'goal', 'goal__organization', 'sender', 'receiver', 'user', 'technics',
            ).prefetch_related('materials__material', 'deeds').filter(cond)
        return base

    # ---------- YARATISH ----------

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        goal = serializer.validated_data['goal']

        if not goal.organization_id or goal.organization.type not in ("worker", "client"):
            raise ValidationError({"goal": "Ariza turi noto'g'ri"})
        if goal.organization.type == "client":
            return self._create_material_order(request, serializer)

        employee = self._employee()
        if serializer.validated_data.get('materials'):
            raise ValidationError({"materials": "ATM arizasida materiallarni bajaruvchi yakunlashda kiritadi."})

        on_behalf = serializer.validated_data.get('sender')
        if on_behalf and on_behalf.pk != employee.pk:
            if not request.user.has_perm("main.add_order"):
                raise PermissionDenied("Boshqa xodim nomidan ariza yuborish huquqingiz yo'q")
            order = Order.objects.create(
                sender=on_behalf, user=employee, goal=goal,
                message_sender=(serializer.validated_data.get('message_sender') or '').strip() or None,
                status="viewed",
            )
        else:
            order = Order.objects.create(
                sender=employee, goal=goal,
                message_sender=(serializer.validated_data.get('message_sender') or '').strip() or None,
                status="viewed",
            )
            self._best_effort(notify_eligible_employees_new_order, order)

        order = self._base_queryset().get(pk=order.pk)
        return Response(OrderSerializer(order, context=self.get_serializer_context()).data, status=201)

    # ---------- QABUL QILISH (bajaruvchi) ----------

    @swagger_auto_schema(responses={200: OrderSerializer()})
    @action(detail=True, methods=['post'], url_path='accept')
    def accept(self, request, pk=None):
        """ATM arizasini qabul qilish: POST /api/orders/{id}/accept/ ({"receiver": id} — faqat superuser)"""
        if self._goal_type(pk) != 'worker':
            return self._barn_accept(request, pk)

        employee = self._employee()
        self._receiver_guard(employee)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        assignee = employee
        chosen = serializer.validated_data.get('receiver')
        if chosen:
            if not request.user.is_superuser:
                raise PermissionDenied("Ijrochini tanlash huquqingiz yo'q")
            assignee = chosen

        goal_ids = set(
            OrderGoal.goal.through.objects.filter(ordergoal__employee=assignee).values_list("goal_id", flat=True)
        )

        def eligible(o):
            return (
                o.status == "viewed" and o.receiver_id is None and o.goal_id in goal_ids
                and o.goal.organization.type == "worker" and o.sender_id is not None
                and o.sender.region_id == assignee.region_id
            )

        msg = "Bu arizani qabul qilish huquqingiz yo'q yoki u allaqachon qabul qilingan"
        order = get_object_or_404(Order.objects.select_related("goal__organization", "sender"), pk=pk)
        if not eligible(order):
            raise ValidationError({"detail": msg})
        if assignee.pk != employee.pk and not _assignee_candidates(order).filter(pk=assignee.pk).exists():
            raise ValidationError(
                {"detail": "Tanlangan xodim bu arizani bajara olmaydi (kategoriya, hudud yoki huquq mos emas)"}
            )

        with transaction.atomic():
            order = (
                Order.objects.select_for_update(of=("self",))
                .select_related("goal__organization", "sender").get(pk=pk)
            )
            if not eligible(order):
                raise ValidationError({"detail": msg})
            order.status = "process"
            order.receiver = assignee
            order.save(update_fields=["status", "receiver"])

        self._best_effort(notify_order_status_change, order)
        time_str = timezone.localtime(timezone.now()).strftime('%Y.%m.%d %H:%M:%S')
        if order.sender_id and order.sender.telegram_chat:
            self._best_effort(
                send_telegram_message, order.sender.telegram_chat,
                f"<b>🔔 Yangi bildirishnoma</b>\n\n"
                f"✅ ATMga yuborgan #{order.id} - arizangiz qabul qilindi.\n"
                f"👤 <b>Bajaruvchi:</b> {assignee.full_name}\n\n"
                f"📅 <b>Vaqt:</b> {time_str}",
            )
        if assignee.pk != employee.pk:
            self._best_effort(
                send_push_notification, assignee,
                title="Sizga ariza biriktirildi",
                body=f"#{order.id} {order.sender.full_name if order.sender else ''}",
                url="/order/receiver/activ/", tag=f"order-assign-{order.id}",
            )
            if assignee.telegram_chat:
                self._best_effort(
                    send_telegram_message, assignee.telegram_chat,
                    f"<b>🔔 Yangi bildirishnoma</b>\n\n"
                    f"📌 Sizga ATM arizasi #{order.id} biriktirildi.\n"
                    f"👤 <b>Ariza muallifi:</b> {order.sender.full_name if order.sender else '-'}\n"
                    f"👨‍💼 <b>Biriktirdi:</b> {employee.full_name}\n\n"
                    f"📅 <b>Vaqt:</b> {time_str}",
                )

        order = self._base_queryset().get(pk=order.pk)
        return Response(OrderSerializer(order, context=self.get_serializer_context()).data)

    @action(detail=True, methods=['get'], url_path='assignees')
    def assignees(self, request, pk=None):
        """Superuser arizani biriktira oladigan xodimlar: GET /api/orders/{id}/assignees/"""
        if not request.user.is_superuser:
            raise PermissionDenied("Sizga ruxsat yo'q")
        order = get_object_or_404(Order.objects.select_related("goal__organization", "sender"), pk=pk)
        if self._goal_type(pk) != 'worker':
            raise ValidationError({"detail": "Faqat ATM arizasi uchun"})
        rows = _assignee_candidates(order)[:100]
        return Response([{"id": e.id, "full_name": e.full_name} for e in rows])

    @action(detail=False, methods=['get'], url_path='available-materials')
    def available_materials(self, request):
        """Bajaruvchi arizaga bera oladigan materiallar (unga MaterialUser orqali biriktirilgan xodimlarniki)."""
        employee = self._employee()
        self._receiver_guard(employee)
        qs = Material.objects.filter(
            employee__in=MaterialUser.objects.filter(receiver=employee).values("sender"),
            is_active=True, number__gt=0,
        ).select_related("unit", "employee", "category").order_by("name", "id")
        term = (request.query_params.get('search') or '').strip()
        if term:
            qs = qs.filter(models.Q(name__icontains=term) | models.Q(code__icontains=term))
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(
            MaterialSerializer(page, many=True, context=self.get_serializer_context()).data
        )

    # ---------- YAKUNLASH (bajaruvchi: texnika + materiallar) ----------

    @swagger_auto_schema(responses={200: OrderSerializer()})
    @action(detail=True, methods=['post'], url_path='finish')
    def finish(self, request, pk=None):
        """
        ATM arizasini yakunlash: POST /api/orders/{id}/finish/
        {"technics_id": id?, "materials": [{"material_id": id, "number": n}, ...]}
        Faqat arizani qabul qilgan xodim; process/finished holatida; materiallar ombordan ayriladi.
        """
        if self._goal_type(pk) != 'worker':
            return self._barn_finish(request, pk)

        employee = self._employee()
        self._receiver_guard(employee)
        serializer = OrderFinishSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        technics_id = serializer.validated_data.get('technics_id')
        items = serializer.validated_data.get('materials') or []

        if technics_id and not Technics.objects.filter(pk=technics_id).exists():
            raise ValidationError({"technics_id": "Texnika topilmadi"})

        pairs, seen = [], set()
        for it in items:
            if it['material_id'] in seen:
                raise ValidationError({"materials": "Bir xil materialni bir necha marta kiritmang"})
            seen.add(it['material_id'])
            pairs.append((it['material_id'], it['number']))

        allowed_owner_ids = set(
            MaterialUser.objects.filter(receiver=employee).values_list("sender_id", flat=True)
        )

        with transaction.atomic():
            order = get_object_or_404(Order.objects.select_for_update(of=("self",)).select_related("sender"), pk=pk)
            if not order.receiver_id:
                raise ValidationError({"detail": "Ariza hali hech kimga biriktirilmagan"})
            if order.receiver_id != employee.id:
                raise PermissionDenied("Bu arizani faqat uni qabul qilgan xodim yakunlay oladi")
            if order.status not in ["process", "finished"]:
                raise ValidationError({"detail": "Bu ariza yakunlanishi mumkin emas"})

            if technics_id:
                order.technics_id = technics_id

            if pairs:
                materials = {
                    m.id: m for m in Material.objects.select_for_update(of=("self",))
                    .filter(id__in=[m for m, _ in pairs], is_active=True).order_by("id")
                }
                for m_id, n in pairs:
                    mat = materials.get(m_id)
                    if not mat:
                        raise ValidationError({"detail": "Material topilmadi yoki faol emas"})
                    if mat.employee_id not in allowed_owner_ids:
                        raise PermissionDenied(f'"{mat.name}" materialini berishga ruxsatingiz yo\'q')
                    if (mat.number or 0) < n:
                        raise ValidationError(
                            {"detail": f'"{mat.name}" yetarli emas. Omborda {mat.number} dona bor'}
                        )

                OrderMaterial.objects.bulk_create(
                    [OrderMaterial(order=order, material=materials[m], number=n) for m, n in pairs]
                )
                for m_id, n in pairs:
                    Material.objects.filter(pk=m_id).update(number=F("number") - n)
                MaterialMovement.objects.bulk_create([
                    MaterialMovement(
                        material=materials[m], user=employee, employee=order.sender,
                        status="order", outcome=n, body=f"Ariza #{order.id} orqali berildi",
                    ) for m, n in pairs
                ])

            order.status = "finished"
            order.save(update_fields=["status", "technics_id"])

        self._best_effort(notify_order_status_change, order)
        if order.sender_id and order.sender.telegram_chat:
            self._best_effort(
                send_telegram_message, order.sender.telegram_chat,
                f"<b>🔔 Yangi bildirishnoma</b>\n\n"
                f"✅ ATMga yuborgan #{order.id} - arizangiz bajarildi.\n"
                f"👤 <b>Bajaruvchi:</b> {employee.full_name}\n\n"
                f"📅 <b>Vaqt:</b> {timezone.localtime(timezone.now()).strftime('%Y.%m.%d %H:%M:%S')}\n\n"
                f"⭐ <b>Iltimos, xizmat sifatini baholang:</b>",
                reply_markup=rating_markup(order.id),
            )

        order = self._base_queryset().get(pk=order.pk)
        return Response(OrderSerializer(order, context=self.get_serializer_context()).data)

    # ---------- HAL QILISH (yuboruvchi: baho bilan qabul / bekor) ----------

    @swagger_auto_schema(responses={200: OrderSerializer()})
    @action(detail=True, methods=['post'], url_path='decide')
    def decide(self, request, pk=None):
        """
        ATM arizasi: POST /api/orders/{id}/decide/ {"action": "accepted", "rating": 1-5} yoki {"action": "canceled"}
        Faqat yuboruvchi (yoki ariza nomidan yuborgan 'user').
        Material arizasi (client) uchun avvalgi qoidalar.
        """
        if self._goal_type(pk) != 'worker':
            return self._barn_decide(request, pk)

        employee = self._employee()
        serializer = OrderDecideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        act = serializer.validated_data['action']
        rating = serializer.validated_data.get('rating')

        if act not in ("accepted", "canceled"):
            raise ValidationError({"action": "ATM arizasi uchun faqat 'accepted' yoki 'canceled'"})
        if act == "accepted" and rating is None:
            raise ValidationError({"rating": "Baho (1 dan 5 gacha) majburiy"})

        with transaction.atomic():
            order = get_object_or_404(Order.objects.select_for_update(of=("self",)), pk=pk)
            if order.sender_id != employee.id and order.user_id != employee.id:
                raise PermissionDenied("Sizda bu arizani o'zgartirish huquqi yo'q")
            if act == "accepted" and order.status != "finished":
                raise ValidationError({"detail": "Faqat bajarilgan ariza qabul qilinishi mumkin"})
            if act == "canceled" and order.status not in ("viewed", "process", "finished"):
                raise ValidationError({"detail": "Bu ariza bekor qilinishi mumkin emas"})

            fields = ["status"]
            order.status = act
            if rating is not None and act == "accepted":
                order.rating = rating
                fields.append("rating")
            order.save(update_fields=fields)

        self._best_effort(notify_order_status_change, order)
        order = self._base_queryset().get(pk=order.pk)
        return Response(OrderSerializer(order, context=self.get_serializer_context()).data)

    # ---------- O'QILGANLIK VA BELGILAR ----------

    @action(detail=False, methods=['post'], url_path='mark-seen')
    def mark_seen(self, request):
        """Yangi ariza belgilarini o'chirish (saytdagi order_mark_seen)."""
        employee = self._employee()
        Order.objects.filter(
            receiver=employee, goal__organization__type="worker",
            status__in=["approved", "canceled"], receiver_seen=False,
        ).update(receiver_seen=True)
        Order.objects.filter(
            receiver=employee, goal__organization__type="client",
            status__in=["accepted", "canceled", "rejected"], receiver_seen=False,
        ).update(receiver_seen=True)
        Order.objects.filter(
            sender=employee, goal__organization__type="worker",
            status__in=["finished", "rejected"], sender_seen=False,
        ).update(sender_seen=True)
        Order.objects.filter(
            sender=employee, goal__organization__type="client",
            status__in=["approved", "rejected"], sender_seen=False,
        ).update(sender_seen=True)
        Order.objects.filter(
            user=employee, goal__organization__type="client",
            status="accepted", user_seen=False,
        ).update(user_seen=True)
        return Response({"status": "ok"})

    @action(detail=False, methods=['get'], url_path='badges')
    def badges(self, request):
        """Belgilar soni (saytdagi qizil raqamlar): yangi bildirishnomalar va bajarish uchun kutayotganlar."""
        from main.context_processors import order_notifications, order_receiver_count
        return Response({
            "notifications": order_notifications(request)["order_notification_count"],
            "receiver_pending": order_receiver_count(request)["order_receiver_badge_count"],
        })

    # ---------- (legacy) YARATISH ----------

    def _create_material_order(self, request, serializer):
        """
        Material arizasi (client tashkilot maqsadi) — saytdagi create_order_sender_from:
        savat Android'da saqlanadi va shu so'rovda yuboriladi. Faqat o'z tashkilotining, ruxsat etilgan
        kategoriyadagi faol materiallari; worker (ATM) xodimi yubora olmaydi; savat bo'sh bo'lmasligi shart.
        """
        employee = self._employee()
        if getattr(employee.organization, "type", None) == "worker":
            raise PermissionDenied("Sizga ruxsat yo'q")

        data = serializer.validated_data
        if data['goal'].organization_id != employee.organization_id:
            raise ValidationError({"goal": "Material arizasi faqat o'z tashkilotingiz omborxonasiga yuboriladi"})
        if data.get('sender') and data['sender'].pk != employee.pk:
            raise ValidationError({"sender": "Material arizasi faqat o'z nomingizdan yuboriladi"})

        items = data.get('materials') or []
        if not items:
            raise ValidationError({"materials": "Savat bo'sh — ariza yaratib bo'lmaydi"})

        ids = [it['material_id'] for it in items]
        if len(ids) != len(set(ids)):
            raise ValidationError({"materials": "Bir xil material bir necha marta kiritildi"})

        category_ids = MaterialEmployee.category.through.objects.filter(
            materialemployee__employee=employee
        ).values_list("materialcategory_id", flat=True)
        allowed = {
            m.id: m for m in Material.objects.filter(
                id__in=ids, organization=employee.organization, is_active=True, category_id__in=category_ids,
            )
        }
        for mid in ids:
            if mid not in allowed:
                raise ValidationError({"materials": f"Material #{mid} topilmadi yoki sizga ruxsat etilmagan"})

        with transaction.atomic():
            order = Order.objects.create(
                goal=data['goal'],
                message_sender=(data.get('message_sender') or '').strip() or None,
                sender=employee, status='viewed',
            )
            OrderMaterial.objects.bulk_create([
                OrderMaterial(order=order, user=employee, material=allowed[it['material_id']], number=it['number'])
                for it in items
            ])

        self._best_effort(notify_eligible_employees_new_order, order)
        order = self._base_queryset().get(pk=order.pk)
        return Response(OrderSerializer(order, context=self.get_serializer_context()).data, status=201)

    @action(detail=False, methods=['get'], url_path='selectable-materials')
    def selectable_materials(self, request):
        """
        Mijoz material arizasiga tanlay oladigan materiallar (saytdagi order_sender_material_barn):
        o'z tashkilotining faol materiallari, faqat unga ruxsat etilgan kategoriyalar bo'yicha. ?search= (nomi).
        """
        employee = self._employee()
        if getattr(employee.organization, "type", None) == "worker":
            raise PermissionDenied("Sizga ruxsat yo'q")
        category_ids = MaterialEmployee.category.through.objects.filter(
            materialemployee__employee=employee
        ).values_list("materialcategory_id", flat=True)
        qs = (
            Material.objects.filter(organization=employee.organization, is_active=True, category_id__in=category_ids)
            .select_related("organization", "unit", "category").order_by("-id")
        )
        term = (request.query_params.get('search') or '').strip()
        if term:
            qs = qs.filter(name__icontains=term)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(
            MaterialSerializer(page, many=True, context=self.get_serializer_context()).data
        )

    # =====================================================================
    # MATERIAL ARIZASI (omborxona, client tashkilot) — saytdagi order_*_barn / order_agrement bilan bir xil.
    # Holatlar: viewed -> process (omborxonachi qabul qildi) | rejected;
    #           process -> finished (omborxonachi materiallarni berdi);
    #           finished -> approved (tasdiqlovchi) | rejected (materiallar omborga qaytadi);
    #           approved -> accepted (yuboruvchi, akt yaratiladi); viewed/process/finished -> canceled (yuboruvchi).
    # =====================================================================

    def _barn_guard(self, employee):
        if getattr(employee.organization, "type", None) == "worker":
            raise PermissionDenied("Sizga ruxsat yo'q")

    def _barn_role_queryset(self, role, employee):
        user = self.request.user
        self._barn_guard(employee)
        qs = Order.objects.select_related(
            'goal', 'goal__organization', 'sender', 'receiver', 'user', 'technics',
        ).prefetch_related('materials__material', 'deeds').filter(goal__organization__type="client")

        if role == "barn_sender":
            return qs.filter(sender=employee, status__in=["viewed", "process", "finished", "approved"]).order_by("-id")
        if role == "barn_sender_archive":
            return qs.filter(sender=employee, status__in=["accepted", "canceled", "rejected"]).order_by("-id")

        if role in ("barn_receiver_new", "barn_receiver_active", "barn_receiver_archive"):
            if not user.has_perm("main.change_order"):
                raise PermissionDenied("Sizga ruxsat yo'q")
            if role == "barn_receiver_new":
                if not employee.region_id:
                    return qs.none()
                goal_ids = OrderGoal.goal.through.objects.filter(
                    ordergoal__employee=employee
                ).values_list("goal_id", flat=True)
                return qs.filter(
                    goal__organization=employee.organization, goal_id__in=goal_ids,
                    sender__region_id=employee.region_id, status="viewed",
                ).order_by("-id")
            if role == "barn_receiver_active":
                return qs.filter(receiver=employee, status__in=["process", "finished"]).order_by("-id")
            return qs.filter(
                receiver=employee, status__in=["approved", "accepted", "canceled", "rejected"]
            ).order_by("-id")

        if role in ("barn_agrement", "barn_agrement_archive"):
            if not user.has_perm("main.confirm_order"):
                raise PermissionDenied("Sizga ruxsat yo'q")
            if role == "barn_agrement":
                if not employee.region_id:
                    return qs.none()
                return qs.filter(
                    goal__organization=employee.organization,
                    receiver__region_id=employee.region_id, status="finished",
                ).order_by("-id")
            return qs.filter(
                user=employee, status__in=["approved", "accepted", "canceled", "rejected"]
            ).order_by("-id")

        raise ValidationError({"role": "Noto'g'ri qiymat"})

    def _barn_response(self, order, **extra):
        order = self._base_queryset().filter(pk=order.pk).first() or Order.objects.get(pk=order.pk)
        data = OrderSerializer(order, context=self.get_serializer_context()).data
        data = dict(data)
        data.update(extra)
        return Response(data)

    def _barn_review(self, request, pk, action_name):
        """Omborxonachi: arizani qabul qiladi (process) yoki rad etadi (rejected) — order_accepted_barn."""
        employee = self._employee()
        self._barn_guard(employee)

        goal_ids = set(
            OrderGoal.goal.through.objects.filter(ordergoal__employee=employee).values_list("goal_id", flat=True)
        )

        def eligible(o):
            return (
                o.status == "viewed" and o.goal_id in goal_ids
                and o.goal.organization_id == employee.organization_id
                and o.goal.organization.type == "client"
                and o.sender_id is not None and o.sender.region_id == employee.region_id
            )

        order = get_object_or_404(Order.objects.select_related("goal__organization", "sender"), pk=pk)
        if not eligible(order):
            raise ValidationError({"detail": "Ariza topilmadi yoki allaqachon ko'rib chiqilgan"})

        with transaction.atomic():
            order = (
                Order.objects.select_for_update(of=("self",)).select_related("goal__organization", "sender").get(pk=pk)
            )
            if not eligible(order):
                raise ValidationError({"detail": "Ariza allaqachon ko'rib chiqilgan"})
            order.receiver = employee
            order.status = action_name
            order.save(update_fields=["status", "receiver"])

        self._best_effort(notify_order_status_change, order)
        if order.sender_id and order.sender.telegram_chat:
            when = timezone.localtime(timezone.now()).strftime('%Y.%m.%d %H:%M:%S')
            if action_name == "process":
                text = (f"<b>🔔 Yangi bildirishnoma</b>\n\n✅ Omborxonaga yuborilgan #{order.id} - arizangiz qabul qilindi.\n"
                        f"👤 <b>Bajaruvchi:</b> {employee.full_name}\n\n📅 <b>Vaqt:</b> {when}")
            else:
                text = (f"<b>🔔 Yangi bildirishnoma</b>\n\n❌ Omborxonaga yuborilgan #{order.id} - arizangiz rad etildi.\n"
                        f"👤 <b>Ko'rib chiqdi:</b> {employee.full_name}\n\n📅 <b>Vaqt:</b> {when}")
            self._best_effort(send_telegram_message, order.sender.telegram_chat, text)
        return self._barn_response(order)

    def _barn_accept(self, request, pk):
        return self._barn_review(request, pk, "process")

    @swagger_auto_schema(request_body=no_body, responses={200: OrderSerializer()})
    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        """Material arizasini rad etish (omborxonachi, change_order): POST /api/orders/{id}/reject/"""
        if self._goal_type(pk) != 'client':
            raise ValidationError({"detail": "Faqat material arizasi uchun"})
        return self._barn_review(request, pk, "rejected")

    @staticmethod
    def _give_changes(items, order_materials, order, giver, sender, allow_zero, tag):
        """given qiymatlarini qo'llaydi: ombor qoldig'i va harakat jurnalini (delta bo'yicha) hisoblaydi."""
        om_map = {str(om.id): om for om in order_materials}
        materials = {m.id: m for m in Material.objects.select_for_update().filter(
            id__in=[om.material_id for om in order_materials if om.material_id])}
        to_update, changed, movements = [], set(), []
        for it in items:
            om = om_map.get(str(it['ordermaterial_id']))
            if om is None:
                raise ValidationError({"items": f"Arizadagi material topilmadi: {it['ordermaterial_id']}"})
            mat = materials.get(om.material_id)
            if mat is None:
                raise ValidationError({"items": "Material topilmadi"})
            given = it['given']
            if given == 0 and not allow_zero:
                raise ValidationError({"items": f"{mat.name} uchun beriladigan son 0 bo'lishi mumkin emas"})
            delta = given - (om.given or 0)
            if delta > 0 and (mat.number or 0) < delta:
                raise ValidationError(
                    {"detail": f"{mat.name} omborda yetarli emas. Omborda: {mat.number}, kerak: {delta}"}
                )
            mat.number = (mat.number or 0) - delta
            changed.add(mat.id)
            om.given = given
            to_update.append(om)
            if delta > 0:
                movements.append(MaterialMovement(
                    material=mat, user=giver, employee=sender, status="order", outcome=delta,
                    body=f"Ariza #{order.id} {tag}",
                ))
            elif delta < 0:
                movements.append(MaterialMovement(
                    material=mat, user=sender, employee=mat.employee, status="order", income=-delta,
                    body=f"Ariza #{order.id} - ortiqcha qaytarildi",
                ))
        for mid in changed:
            if materials[mid].number < 0:
                raise ValidationError({"detail": f"{materials[mid].name} uchun qoldiq manfiy bo'lib qoldi"})
        if to_update:
            OrderMaterial.objects.bulk_update(to_update, ["given"])
        if changed:
            Material.objects.bulk_update([materials[m] for m in changed], ["number"])
        if movements:
            MaterialMovement.objects.bulk_create(movements)

    def _barn_finish(self, request, pk):
        """
        Omborxonachi materiallarni beradi: POST /api/orders/{id}/finish/
        {"items": [{"ordermaterial_id": id, "given": n}, ...], "date": "YYYY-MM-DDTHH:MM"?}
        Faqat arizani qabul qilgan xodim, o'z tashkiloti omborxonasi, process/finished holatida.
        """
        employee = self._employee()
        self._barn_guard(employee)
        serializer = OrderFinishSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        items = serializer.validated_data.get('items') or []
        date = (serializer.validated_data.get('date') or '').strip()

        if not items:
            raise ValidationError({"items": "Materiallar ro'yxati bo'sh"})
        ids = [it['ordermaterial_id'] for it in items]
        if len(ids) != len(set(ids)):
            raise ValidationError({"items": "Takroriy materiallar yuborildi"})

        date_display = ""
        if date:
            try:
                date_display = datetime.strptime(date, "%Y-%m-%dT%H:%M").strftime("%d.%m.%Y %H:%M")
            except ValueError:
                raise ValidationError({"date": "Sana formati noto'g'ri (YYYY-MM-DDTHH:MM)"})
        body = (f"Materiallarni ombordan {date_display} da qabul qilib olishingiz mumkin" if date_display
                else "Materiallarni ombordan qabul qilib olishingiz mumkin")

        with transaction.atomic():
            order = get_object_or_404(
                Order.objects.select_for_update(of=("self",)).select_related("goal__organization", "sender"), pk=pk
            )
            if order.receiver_id != employee.id:
                raise PermissionDenied("Bu arizani faqat uni qabul qilgan xodim yakunlay oladi")
            if not order.goal or order.goal.organization_id != employee.organization_id:
                raise PermissionDenied("Bu ariza sizning tashkilotingizga tegishli emas")
            if order.status not in ["process", "finished"]:
                raise ValidationError({"detail": "Bu ariza yakunlanishi mumkin emas"})

            oms = list(OrderMaterial.objects.select_for_update(of=("self",)).filter(order=order, id__in=ids))
            if len(oms) != len(ids):
                raise ValidationError({"items": "Ba'zi materiallar topilmadi"})
            if any(om.material_id is None for om in oms):
                raise ValidationError({"items": "Ba'zi materiallarga bog'lanish topilmadi"})

            self._give_changes(items, oms, order, employee, order.sender, allow_zero=False, tag="orqali berildi")
            order.status = "finished"
            order.message_receiver = body
            order.save(update_fields=["status", "message_receiver"])

        self._best_effort(notify_order_status_change, order)
        if order.sender_id and order.sender.telegram_chat:
            self._best_effort(
                send_telegram_message, order.sender.telegram_chat,
                f"<b>🔔 Yangi bildirishnoma</b>\n\n✅ Omborxonaga yuborilgan #{order.id} - arizangiz bajarildi.\n"
                f"👤 <b>Bajaruvchi:</b> {employee.full_name}\n\n"
                f"📅 <b>Vaqt:</b> {timezone.localtime(timezone.now()).strftime('%Y.%m.%d %H:%M:%S')}",
            )
        return self._barn_response(order)

    @action(detail=True, methods=['post'], url_path='confirm')
    def confirm(self, request, pk=None):
        """
        Tasdiqlovchi ('confirm_order'): POST /api/orders/{id}/confirm/
        {"action": "approved", "items": [{"ordermaterial_id", "given"}]} yoki {"action": "rejected"} (materiallar omborga qaytadi).
        Faqat 'finished' holatdagi, o'z tashkiloti va hududidagi arizalar.
        """
        employee = self._employee()
        self._barn_guard(employee)
        serializer = OrderConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        act = serializer.validated_data['action']
        items = serializer.validated_data.get('items') or []

        if act == "approved":
            ids = [it['ordermaterial_id'] for it in items]
            if len(ids) != len(set(ids)):
                raise ValidationError({"items": "Takroriy materiallar yuborildi"})

        with transaction.atomic():
            order = get_object_or_404(
                Order.objects.select_for_update(of=("self",)).select_related("goal__organization", "receiver", "sender"),
                pk=pk,
            )
            if not order.goal or order.goal.organization_id != employee.organization_id:
                raise PermissionDenied("Bu ariza sizning tashkilotingizga tegishli emas")
            if not order.receiver or order.receiver.region_id != employee.region_id:
                raise PermissionDenied("Bu ariza sizning hududingizga tegishli emas")
            if order.status != "finished":
                raise ValidationError({"detail": "Bu arizani tasdiqlash yoki rad etish mumkin emas"})

            if act == "rejected":
                oms = list(OrderMaterial.objects.select_for_update(of=("self",)).filter(order=order).select_related("material"))
                mats = {m.id: m for m in Material.objects.select_for_update().filter(
                    id__in=[om.material_id for om in oms if om.material_id and (om.given or 0) > 0])}
                changed_m, changed_om, movements = [], [], []
                for om in oms:
                    old = om.given or 0
                    if old > 0:
                        mat = mats.get(om.material_id)
                        if mat:
                            mat.number = (mat.number or 0) + old
                            changed_m.append(mat)
                            movements.append(MaterialMovement(
                                material=mat, user=order.sender, employee=mat.employee, status="order",
                                income=old, body=f"Ariza #{order.id} rad etildi - qaytarildi",
                            ))
                        om.given = 0
                        changed_om.append(om)
                if changed_m:
                    Material.objects.bulk_update(changed_m, ["number"])
                if changed_om:
                    OrderMaterial.objects.bulk_update(changed_om, ["given"])
                if movements:
                    MaterialMovement.objects.bulk_create(movements)
                order.status = "rejected"
                order.user = employee
                order.save(update_fields=["status", "user"])
            else:
                if not items:
                    raise ValidationError({"items": "Materiallar ro'yxati bo'sh"})
                oms = list(OrderMaterial.objects.select_for_update(of=("self",)).filter(order=order, id__in=ids).select_related("material"))
                if len(oms) != len(ids):
                    raise ValidationError({"items": "Ba'zi materiallar topilmadi"})
                if any(om.material_id is None for om in oms):
                    raise ValidationError({"items": "Ba'zi materiallarga bog'lanish topilmadi"})
                self._give_changes(items, oms, order, order.receiver, order.sender, allow_zero=True, tag="tasdiqlandi")
                order.status = "approved"
                order.user = employee
                order.save(update_fields=["status", "user"])

        self._best_effort(notify_order_status_change, order)
        if order.sender_id and order.sender.telegram_chat:
            when = timezone.localtime(timezone.now()).strftime('%Y.%m.%d %H:%M:%S')
            if act == "approved":
                self._best_effort(
                    send_telegram_message, order.sender.telegram_chat,
                    f"<b>🔔 Yangi bildirishnoma</b>\n\n✅ Omborxonaga yuborilgan #{order.id} - arizangiz tasdiqlandi.\n"
                    f"⚠️ <b>{order.message_receiver}</b>\n👤 <b>Bajaruvchi:</b> {order.receiver.full_name}\n"
                    f"✔️ <b>Tasdiqlovchi:</b> {employee.full_name}\n\n📅 <b>Vaqt:</b> {when}",
                    reply_markup=barn_approved_markup(order.id),
                )
            else:
                self._best_effort(
                    send_telegram_message, order.sender.telegram_chat,
                    f"<b>🔔 Yangi bildirishnoma</b>\n\n❌ Omborxonaga yuborilgan #{order.id} - arizangiz rad etildi.\n"
                    f"👤 <b>Ko'rib chiqdi:</b> {employee.full_name}\n\n📅 <b>Vaqt:</b> {when}",
                )
        return self._barn_response(order)

    def _barn_decide(self, request, pk):
        """Yuboruvchi: accepted (faqat tasdiqlangan; akt yaratiladi) yoki canceled — order_decide_barn."""
        employee = self._employee()
        self._barn_guard(employee)
        serializer = OrderDecideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        act = serializer.validated_data['action']
        if act not in ("accepted", "canceled"):
            raise ValidationError({"action": "Material arizasi uchun faqat 'accepted' yoki 'canceled'"})

        with transaction.atomic():
            order = get_object_or_404(Order.objects.select_for_update(of=("self",)), pk=pk)
            if order.sender_id != employee.id:
                raise PermissionDenied("Ariza sizga tegishli emas")
            if act == "canceled" and order.status in {"accepted", "approved", "canceled", "rejected"}:
                raise ValidationError({"detail": "Bu ariza bo'yicha amal bajarilgan"})
            if act == "accepted" and order.status != "approved":
                raise ValidationError({"detail": "Bu ariza hozir qabul qilinmaydi"})
            # Omborxonachi materiallarni allaqachon bergan bo'lsa (finished) — bekor qilinganda omborga qaytadi
            if act == "canceled" and order.status == "finished":
                _restore_given_materials(order, "bekor qilindi")
            order.status = act
            order.save(update_fields=["status"])

        extra = {}
        if act == "accepted" and order.materials.exists():
            try:
                _create_deed_for_order(order, request)
            except HtmlPdfError:
                extra["warning"] = ("Ariza qabul qilindi, lekin hujjat yaratilmadi. "
                                    "Hujjatni keyinroq qayta yaratishga urinib ko'ring.")
            except Exception:
                extra["warning"] = ("Ariza qabul qilindi, lekin hujjatga imzo/QR urishda xatolik yuz berdi. "
                                    "Hujjatni keyinroq tekshiring.")
        self._best_effort(notify_order_status_change, order)
        return self._barn_response(order, **extra)



class OrderMaterialViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Faqat KO'RISH — arizadagi materiallar ('view_order' bo'lsa tashkilot bo'yicha, bo'lmasa o'ziga aloqador
    sender/receiver/user). Materiallar arizada saytdagidek faqat yakunlash/tasdiqlashda o'zgaradi
    (POST /api/orders/{id}/finish/ va /confirm/), alohida tahrirlanmaydi.
    """

    serializer_class = OrderMaterialSerializer
    permission_classes = [OrderMaterialPermission]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["order", "material"]

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


def _org_scoped(qs, user, lookup):
    """Rol ma'lumotlari: 'all_organization' (yoki superuser) hammasi, aks holda faqat o'z tashkiloti (lookup — tashkilot yo'li)."""
    if user.is_superuser or user.has_perm("main.all_organization"):
        return qs
    employee = getattr(user, "employee", None)
    if not employee or not employee.organization_id:
        return qs.none()
    return qs.filter(**{lookup: employee.organization_id})


class OrderGoalViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Faqat KO'RISH: xodimlarning ruxsat etilgan ariza turlari. Saytda ular faqat ruxsatlar oynasida
    (PUT /api/employees/{id}/permissions/) o'zgaradi. 'permission_employee' kerak; faqat o'z tashkiloti.
    """

    serializer_class = OrderGoalSerializer
    permission_classes = [PermissionManagerPermission]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["employee", "goal"]

    def get_queryset(self):
        qs = OrderGoal.objects.select_related('employee').prefetch_related('goal').order_by('id')
        return _org_scoped(qs, self.request.user, "employee__organization_id")


class MaterialUserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Faqat KO'RISH: material delegatsiyasi (kim kimning materialini sarflay oladi). Saytda u faqat admin panelda
    boshqariladi. 'permission_employee' kerak; faqat o'z tashkiloti.
    """

    serializer_class = MaterialUserSerializer
    permission_classes = [PermissionManagerPermission]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["sender", "receiver"]

    def get_queryset(self):
        qs = MaterialUser.objects.select_related('sender').prefetch_related('receiver').order_by('id')
        user = self.request.user
        if user.is_superuser or user.has_perm("main.all_organization"):
            return qs
        employee = getattr(user, "employee", None)
        if not employee or not employee.organization_id:
            return qs.none()
        return qs.filter(sender__organization_id=employee.organization_id).distinct()


def _deed_attachments_response(deed):
    import os
    import shutil
    import tempfile
    import zipfile

    items = []
    for item in deed.deedfiles_set.order_by("id"):
        try:
            if item.file and item.file.storage.exists(item.file.name):
                items.append(item)
        except Exception:
            pass
    if not items:
        raise Http404("Bu hujjatga ilova fayllar topilmadi")

    if len(items) == 1:
        item = items[0]
        return FileResponse(item.file.open("rb"), as_attachment=True, filename=os.path.basename(item.file.name))

    tmp = tempfile.SpooledTemporaryFile(max_size=20 * 1024 * 1024)
    used = set()
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in items:
            base = os.path.basename(item.file.name)
            name, i = base, 1
            while name in used:
                name = f"{i}_{base}"
                i += 1
            used.add(name)
            with item.file.open("rb") as src, zf.open(name, "w") as dst:
                shutil.copyfileobj(src, dst)
    tmp.seek(0)
    return FileResponse(tmp, as_attachment=True, filename=f"ilovalar_{deed.code or deed.pk}.zip")


def _visible_deeds(user):
    """
    Saytdagidek hujjatni ISHTIROKCHILAR ko'radi: yaratuvchi, imzolovchi, qabul qiluvchi, kelishuvchi.
    'all_organization' (va superuser) hammasini ko'radi.
    """
    employee = getattr(user, "employee", None)
    if not employee:
        return Deed.objects.none()
    if user.has_perm('main.all_organization'):
        return Deed.objects.all()
    return Deed.objects.filter(
        Q(user=employee) | Q(sender=employee) | Q(receiver=employee) | Q(deedconsent__employee=employee)
    )


@method_decorator(name='list', decorator=swagger_auto_schema(manual_parameters=[DEED_ROLE_PARAM]))
class DeedViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                  mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    Saytdagi (main/views.py) hujjat qoidalari bilan bir xil.

    Ko'rish — faqat ishtirokchilar (yaratuvchi, imzolovchi, qabul qiluvchi, kelishuvchi) yoki 'all_organization'.
      Ro'yxat filtri: ?role=created | created_archive | to_sign | signed | to_agree | agreed
    Yaratish — 'add_deed': PDF fayl yoki body, ilovalar (10 tagacha), kelishuvchilar; yaratuvchi = so'rov egasi.
    Tahrirlash (PATCH) — faqat yaratuvchi, 'user_edit' yoqilgan va hali hech kim javob bermagan paytda.
    Rad etish (POST .../reject/) — imzolovchi/qabul qiluvchi. Imzolash (E-imzo) — hali API'da yo'q.
    Kelishuvchilar: POST .../consents/, GET .../consent-candidates/, POST .../signer-consent/{sender|receiver}/.
    Hujjat O'CHIRILMAYDI (saytda ham yo'q).
    """

    permission_classes = [DeedPermission]
    pagination_class = StandardResultsPagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["organization", "sender", "receiver", "user", "status", "orders"]
    search_fields = ["code", "body", "message_sender", "message_receiver", "message_user"]

    ROLES = ("created", "created_archive", "to_sign", "signed", "to_agree", "agreed")

    def get_serializer_class(self):
        if self.action == 'create':
            return DeedCreateSerializer
        if self.action in ('update', 'partial_update'):
            return DeedUpdateSerializer
        return DeedSerializer

    def _employee(self):
        employee = getattr(self.request.user, "employee", None)
        if not employee:
            raise PermissionDenied("Employee yo'q")
        return employee

    def _apply_role(self, qs, role, me):
        done = ["approved", "rejected"]
        if role == "created":
            return qs.filter(user=me)
        if role == "created_active":
            pending = DeedConsent.objects.filter(deed_id=OuterRef("pk"), status="viewed")
            return qs.filter(user=me).annotate(has_pending_consent=Exists(pending)).filter(
                Q(receiver__isnull=True, status_sender="viewed") |
                Q(receiver__isnull=False) & (Q(status_sender="viewed") | Q(status_receiver="viewed")) |
                Q(has_pending_consent=True)
            )
        if role == "created_archive":
            pending = DeedConsent.objects.filter(deed_id=OuterRef("pk"), status="viewed")
            return qs.filter(user=me).annotate(has_pending_consent=Exists(pending)).filter(
                Q(receiver__isnull=True, status_sender__in=done) |
                Q(receiver__isnull=False, status_sender__in=done, status_receiver__in=done)
            ).filter(has_pending_consent=False)
        if role == "to_sign":
            return qs.filter(
                Q(sender_id=me.id, status_sender="viewed") | Q(receiver_id=me.id, status_receiver="viewed")
            )
        if role == "signed":
            return qs.filter(
                Q(sender_id=me.id, status_sender__in=done) | Q(receiver_id=me.id, status_receiver__in=done)
            )
        if role == "to_agree":
            return qs.filter(deedconsent__employee_id=me.id, deedconsent__status="viewed")
        if role == "agreed":
            return qs.filter(deedconsent__employee_id=me.id, deedconsent__status__in=done)
        raise ValidationError({"role": f"Noto'g'ri qiymat. Mumkin: {', '.join(self.ROLES)}"})

    def get_queryset(self):
        user = self.request.user
        me = getattr(user, "employee", None)
        qs = _visible_deeds(user).select_related(
            'organization', 'sender', 'receiver', 'user',
        ).prefetch_related(
            'orders', 'deedfiles_set',
            Prefetch('deedconsent_set', queryset=DeedConsent.objects.select_related(
                'employee', 'employee__organization', 'employee__rank')),
        )
        role = (self.request.query_params.get('role') or '').strip()
        if role and me:
            if role == 'created':
                qs = self._apply_role(qs, 'created_active', me)
            else:
                qs = self._apply_role(qs, role, me)
        return qs.distinct().order_by('-id')

    # ---- yaratish ----

    def create(self, request, *args, **kwargs):
        employee = self._employee()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            deed = serializer.save(user=employee)
            if not deed.file:
                try:
                    _save_deed_pdf(deed)
                except HtmlPdfError as e:
                    raise ValidationError({"detail": str(e)})
        deed = Deed.objects.get(pk=deed.pk)
        # Saytdagidek: imzolovchiga va kelishuvchilarga push (xato bo'lsa hujjat yaratilishiga halaqit bermaydi)
        try:
            notify_deed_sender(deed)
            watchers = Employee.objects.filter(deedconsent__deed=deed).distinct()
            if watchers:
                notify_deed_watchers(deed, watchers)
        except Exception:
            logging.getLogger(__name__).exception("Hujjat #%s uchun push yuborilmadi", deed.pk)
        return Response(DeedSerializer(deed, context=self.get_serializer_context()).data, status=201)

    # ---- tahrirlash (saytdagi deed_edit) ----

    @staticmethod
    def _assert_editable(deed, employee):
        if deed.user_id != employee.id:
            raise PermissionDenied("Sizga ruxsat yo'q")
        if not deed.user_edit or not deed.body:
            raise PermissionDenied("Bu hujjatni tahrirlash mumkin emas")
        if deed.status_sender != 'viewed' or (deed.receiver_id and deed.status_receiver != 'viewed'):
            raise PermissionDenied("Hujjat bo'yicha javob berilgan, tahrirlab bo'lmaydi")

    def update(self, request, *args, **kwargs):
        employee = self._employee()
        deed = self.get_object()
        self._assert_editable(deed, employee)

        serializer = DeedUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        sender_org_id = deed.sender.organization_id if deed.sender_id else None
        receiver_org_id = deed.receiver.organization_id if deed.receiver_id else None
        org_ids = [x for x in {sender_org_id, receiver_org_id, employee.organization_id} if x]

        new_sender = data.get('sender', deed.sender)
        if 'sender' in data and new_sender.organization_id != sender_org_id:
            raise ValidationError({"sender": "Imzolovchi topilmadi yoki ruxsat etilmagan"})
        new_receiver = deed.receiver
        if 'receiver' in data:
            if not deed.receiver_id:
                raise ValidationError({"receiver": "Bu hujjatda qabul qiluvchi yo'q"})
            new_receiver = data['receiver']
            if new_receiver.organization_id != receiver_org_id:
                raise ValidationError({"receiver": "Qabul qiluvchi topilmadi yoki ruxsat etilmagan"})

        agreement_ids = None
        if 'agreements' in data:
            agreement_ids = list(
                Employee.objects.filter(id__in=data['agreements'], organization_id__in=org_ids)
                .values_list('id', flat=True)
            )

        with transaction.atomic():
            deed = Deed.objects.select_for_update(of=("self",)).select_related('sender', 'receiver').get(pk=deed.pk)
            self._assert_editable(deed, employee)

            sender_changed = deed.sender_id != new_sender.id
            receiver_changed = bool(deed.receiver_id) and deed.receiver_id != new_receiver.id

            deed.sender = new_sender
            update_fields = ["sender", "body"]
            if sender_changed:
                deed.status_sender, deed.message_sender, deed.date_sender = "viewed", None, None
                update_fields += ["status_sender", "message_sender", "date_sender"]
            if deed.receiver_id:
                deed.receiver = new_receiver
                update_fields.append("receiver")
                if receiver_changed:
                    deed.status_receiver, deed.message_receiver, deed.date_receiver = "viewed", None, None
                    update_fields += ["status_receiver", "message_receiver", "date_receiver"]

            deed.body = data.get('body', deed.body)
            try:
                pdf_bytes = deed_to_pdf_bytes(deed)
                pdf_bytes = add_text_watermark_pdf_bytes(pdf_bytes, "TASDIQLANMAGAN")
            except HtmlPdfError as e:
                raise ValidationError({"detail": f"Hujjat yangilanmadi: {e}"})
            pdf_name = f"akt_{timezone.now().strftime('%Y%m%d')}_{secrets.token_urlsafe(8)}.pdf"
            old_file = deed.file
            deed.save(update_fields=update_fields)

            if agreement_ids is not None:
                exclude = {deed.sender_id}
                if deed.receiver_id:
                    exclude.add(deed.receiver_id)
                final_ids = [i for i in agreement_ids if i not in exclude]
                existing = set(DeedConsent.objects.filter(deed_id=deed.id).values_list("employee_id", flat=True))
                # Javob bergan kelishuvchilar tarixi saqlanadi; faqat kutilayotganlar olib tashlanadi
                DeedConsent.objects.filter(deed_id=deed.id, status="viewed").exclude(employee_id__in=final_ids).delete()
                new_ids = [i for i in final_ids if i not in existing]
                if new_ids:
                    DeedConsent.objects.bulk_create(
                        [DeedConsent(deed_id=deed.id, employee_id=i, status="viewed") for i in new_ids]
                    )

            if old_file:
                try:
                    old_file.delete(save=False)
                except Exception:
                    pass
            deed.file.save(pdf_name, ContentFile(pdf_bytes), save=True)

        return Response(DeedSerializer(
            self.get_queryset().get(pk=deed.pk), context=self.get_serializer_context()
        ).data)

    @action(detail=True, methods=['post'], url_path='generate-pdf')
    def generate_pdf(self, request, pk=None):
        """PDF qayta yaratish (faqat tahrirlash mumkin bo'lgan paytda, yaratuvchi): POST /api/deeds/{id}/generate-pdf/"""
        employee = self._employee()
        deed = self.get_object()
        self._assert_editable(deed, employee)
        try:
            with transaction.atomic():
                _save_deed_pdf(deed)
        except HtmlPdfError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(DeedSerializer(deed, context=self.get_serializer_context()).data)

    @action(detail=True, methods=['post'], url_path='toggle-user-edit')
    def toggle_user_edit(self, request, pk=None):
        """Yaratuvchiga tahrirlashga ruxsatni yoqish/o'chirish ('change_deed' kerak)."""
        employee = self._employee()
        deed = get_object_or_404(Deed, pk=pk)
        if not (request.user.has_perm('main.all_organization')
                or deed.organization_id == employee.organization_id
                or _visible_deeds(request.user).filter(pk=deed.pk).exists()):
            raise PermissionDenied("Sizga ruxsat yo'q")
        deed.user_edit = not deed.user_edit
        deed.save(update_fields=["user_edit"])
        return Response({"success": True, "user_edit": deed.user_edit})

    # ---- imzolovchi rad etishi (saytdagi deed_action: reject; tasdiqlash E-imzo talab qiladi) ----

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        employee = self._employee()
        serializer = DeedRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.validated_data.get('message', '')

        with transaction.atomic():
            deed = get_object_or_404(Deed.objects.select_for_update(of=("self",)), pk=pk)
            if deed.receiver_id == employee.id:
                role, current = "receiver", deed.status_receiver
            elif deed.sender_id == employee.id:
                role, current = "sender", deed.status_sender
            else:
                raise PermissionDenied("Sizga ruxsat yo'q")
            if current != "viewed":
                raise ValidationError({"detail": "Bu dalolatnoma holatida amal bajarib bo'lmaydi"})

            now = timezone.now()
            setattr(deed, f"status_{role}", "rejected")
            setattr(deed, f"message_{role}", message)
            setattr(deed, f"date_{role}", now)
            deed.date_edit = now
            deed.save(update_fields=["date_edit", f"status_{role}", f"message_{role}", f"date_{role}"])

        return Response(DeedSerializer(
            self.get_queryset().get(pk=deed.pk), context=self.get_serializer_context()
        ).data)

    # ---- kelishuvchilar ----

    def _taken_ids(self, deed):
        taken = set(DeedConsent.objects.filter(deed_id=deed.id).values_list("employee_id", flat=True))
        taken.update(i for i in (deed.sender_id, deed.receiver_id) if i)
        return taken

    @action(detail=True, methods=['get'], url_path='consent-candidates')
    def consent_candidates(self, request, pk=None):
        """Kelishuvchi qo'shish uchun xodimlar (qidiruv: ?search=, 20 tadan sahifalanadi)."""
        employee = self._employee()
        deed = get_object_or_404(Deed.objects.select_related('sender', 'receiver'), pk=pk)
        if not _can_add_consents(deed, employee):
            raise PermissionDenied("Sizga ruxsat yo'q")

        qs = (
            Employee.objects
            .filter(organization_id__in=_deed_consent_org_ids(deed, employee))
            .exclude(id__in=self._taken_ids(deed))
            .select_related('rank', 'organization')
        )
        for term in (request.query_params.get('search') or '').split():
            qs = qs.filter(
                Q(last_name__icontains=term) | Q(first_name__icontains=term) |
                Q(father_name__icontains=term) | Q(pinfl__icontains=term)
            )
        qs = qs.order_by('last_name', 'first_name', 'father_name', 'id')
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(DeedConsentCandidateSerializer(page, many=True).data)

    @action(detail=True, methods=['post'], url_path='consents')
    def consents(self, request, pk=None):
        """Kelishuvchi(lar) qo'shish: POST /api/deeds/{id}/consents/ {"employees": [id, ...]}"""
        employee = self._employee()
        serializer = DeedConsentAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            deed = get_object_or_404(
                Deed.objects.select_for_update(of=("self",)).select_related('sender', 'receiver'), pk=pk
            )
            if not _can_add_consents(deed, employee):
                raise PermissionDenied("Sizga ruxsat yo'q")
            if not _deed_consents_open(deed):
                raise ValidationError({"detail": "Bu hujjatda kelishuvchilarni o'zgartirib bo'lmaydi"})

            taken = self._taken_ids(deed)
            valid_ids = [
                i for i in Employee.objects.filter(
                    id__in=serializer.validated_data['employees'],
                    organization_id__in=_deed_consent_org_ids(deed, employee),
                ).values_list('id', flat=True)
                if i not in taken
            ]
            if not valid_ids:
                raise ValidationError(
                    {"detail": "Tanlangan xodimni qo'shib bo'lmaydi (allaqachon bor yoki ruxsat etilmagan)"}
                )
            DeedConsent.objects.bulk_create(
                [DeedConsent(deed_id=deed.id, employee_id=i, status="viewed") for i in valid_ids]
            )

        return Response(DeedSerializer(
            self.get_queryset().get(pk=deed.pk), context=self.get_serializer_context()
        ).data, status=201)

    @action(detail=True, methods=['post'], url_path=r'signer-consent/(?P<role>sender|receiver)')
    def signer_consent(self, request, pk=None, role=None):
        """Yaratuvchi: imzolovchi ham kelishuvchi qo'sha olsinmi — {"enabled": true|false}."""
        employee = self._employee()
        serializer = DeedSignerConsentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        deed = get_object_or_404(Deed, pk=pk)
        if deed.user_id != employee.id:
            raise PermissionDenied("Sizga ruxsat yo'q")
        if role == "receiver" and not deed.receiver_id:
            raise Http404("Qabul qiluvchi topilmadi")
        if not _deed_consents_open(deed):
            return Response({"ok": False, "error": "Bu hujjatda kelishuvchilarni o'zgartirib bo'lmaydi"}, status=409)

        field = f"{role}_can_add_consent"
        setattr(deed, field, serializer.validated_data['enabled'])
        deed.save(update_fields=[field])
        return Response({"ok": True, "enabled": getattr(deed, field)})

    @action(detail=True, methods=['get'], url_path='attachments/download')
    def attachments_download(self, request, pk=None):
        """Ilovalarni yuklab olish: bitta bo'lsa o'zi, bir nechta bo'lsa ZIP (saytdagi deed_attachments)."""
        return _deed_attachments_response(self.get_object())


class DeedRegistryViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Hujjatlar reyestri — saytdagi "files" sahifasi: filtr bilan HAMMA hujjat (kirgan har bir xodim ko'ra oladi).
    Ro'yxat uchun kamida bitta filtr kerak: name (kod, F.I.O yoki ariza raqami), organization, region (yaratuvchi hududi),
    status (hujjat turi), date1, date2 (YYYY-MM-DD, yaratilgan sana). Hujjat matni (body) berilmaydi.
    Ilovalar: GET /api/deed-registry/{id}/attachments/download/.
    """

    serializer_class = DeedRegistrySerializer
    permission_classes = [DeedConsentPermission]
    pagination_class = StandardResultsPagination

    FILTERS = ("name", "organization", "region", "status", "date1", "date2")

    def get_queryset(self):
        qs = Deed.objects.select_related("organization", "sender", "receiver", "user").prefetch_related(
            "orders", "deedfiles_set",
            Prefetch("deedconsent_set", queryset=DeedConsent.objects.select_related(
                "employee", "employee__organization", "employee__rank")),
        ).order_by("-id")
        if self.action != "list":
            return qs

        params = self.request.query_params
        if not any((params.get(k) or "").strip() for k in self.FILTERS):
            raise ValidationError({"detail": "Kamida bitta filtr kerak: " + ", ".join(self.FILTERS)})

        name = (params.get("name") or "").strip()[:120]
        if name:
            person = Q()
            for term in name.split():
                person &= (
                    Q(sender__last_name__icontains=term) | Q(sender__first_name__icontains=term) |
                    Q(sender__father_name__icontains=term) | Q(receiver__last_name__icontains=term) |
                    Q(receiver__first_name__icontains=term) | Q(receiver__father_name__icontains=term) |
                    Q(user__last_name__icontains=term) | Q(user__first_name__icontains=term) |
                    Q(user__father_name__icontains=term)
                )
            cond = Q(code__icontains=name) | person
            cond |= Q(orders__id=int(name)) if name.isdigit() else Q(orders__id__icontains=name)
            qs = qs.filter(cond)

        org = (params.get("organization") or "").strip()
        if org:
            if not org.isdigit():
                raise ValidationError({"organization": "Noto'g'ri qiymat"})
            qs = qs.filter(organization_id=int(org))
        region = (params.get("region") or "").strip()
        if region:
            if not region.isdigit():
                raise ValidationError({"region": "Noto'g'ri qiymat"})
            qs = qs.filter(user__region_id=int(region))
        status_ = (params.get("status") or "").strip()
        if status_:
            qs = qs.filter(status=status_)
        for key, lookup in (("date1", "date_creat__date__gte"), ("date2", "date_creat__date__lte")):
            raw = (params.get(key) or "").strip()
            if raw:
                d = parse_date(raw)
                if not d:
                    raise ValidationError({key: "Sana formati noto'g'ri (YYYY-MM-DD)"})
                qs = qs.filter(**{lookup: d})
        return qs.distinct()

    @action(detail=True, methods=['get'], url_path='attachments/download')
    def attachments_download(self, request, pk=None):
        return _deed_attachments_response(self.get_object())


class DeedFilesViewSet(viewsets.ReadOnlyModelViewSet):
    """Faqat KO'RISH (saytda ilovalar hujjat yaratilganda qo'shiladi, keyin o'zgarmaydi) — ko'rinadigan hujjatlar bo'yicha."""

    serializer_class = DeedFilesSerializer
    permission_classes = [DeedConsentPermission]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["deed"]

    def get_queryset(self):
        return DeedFiles.objects.filter(
            deed_id__in=_visible_deeds(self.request.user).values('id')
        ).select_related('deed').order_by('-id')


class DeedConsentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin,
                         viewsets.GenericViewSet):
    """
    Ko'rish — ko'rinadigan hujjatlarning kelishuvchilari.
    O'chirish — faqat hujjat yaratuvchisi, faqat hali javob bermagan kelishuvchini, hujjat yopilmagan bo'lsa.
    Tasdiqlash/Rad etish — main/views.py:deedconsent_action() bilan bir xil qoida (faqat belgilangan
    kelishuvchi, faqat 'viewed' holatida, rad etishda izoh majburiy):
      POST /api/deed-consents/{id}/approve/
      POST /api/deed-consents/{id}/reject/
    Qo'shish — POST /api/deeds/{id}/consents/.
    """

    serializer_class = DeedConsentSerializer
    permission_classes = [DeedConsentPermission]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["deed", "employee", "status"]

    def get_queryset(self):
        return DeedConsent.objects.filter(
            deed_id__in=_visible_deeds(self.request.user).values('id')
        ).select_related('deed', 'employee', 'employee__organization', 'employee__rank').order_by('-id')

    def perform_destroy(self, instance):
        employee = getattr(self.request.user, "employee", None)
        deed = instance.deed
        if not employee or deed.user_id != employee.id:
            raise PermissionDenied("Sizga ruxsat yo'q")
        with transaction.atomic():
            consent = DeedConsent.objects.select_for_update(of=("self",)).get(pk=instance.pk)
            if not _deed_consents_open(deed):
                raise ValidationError({"detail": "Bu hujjatda kelishuvchilarni o'zgartirib bo'lmaydi"})
            if consent.status != "viewed":
                raise ValidationError({"detail": "Kelishuvchi allaqachon javob bergan, uni olib tashlab bo'lmaydi"})
            consent.delete()

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        return self._resolve(request, pk, 'approved')

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        return self._resolve(request, pk, 'rejected')

    def _resolve(self, request, pk, new_status):
        employee = getattr(request.user, 'employee', None)
        if not employee:
            return Response({"detail": "Employee yo'q"}, status=400)

        serializer = DeedConsentActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.validated_data.get('message', '')

        if new_status == 'rejected' and not message:
            return Response({"detail": "Rad etish uchun izoh yozing"}, status=400)

        try:
            with transaction.atomic():
                consent = get_object_or_404(
                    DeedConsent.objects.select_for_update(of=("self",)), pk=pk
                )

                if consent.employee_id != employee.id:
                    return Response({"detail": "Sizga ruxsat yo'q"}, status=403)

                if consent.status != "viewed":
                    return Response({"detail": "Bu kelishuv allaqachon ko'rib chiqilgan"}, status=400)

                consent.status = new_status
                consent.message = message
                consent.save(update_fields=["status", "message", "date_edit"])
        except DatabaseError:
            return Response({"detail": "Xatolik yuz berdi. Qayta urinib ko'ring"}, status=500)

        return Response(DeedConsentSerializer(consent).data)


class LiableViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Faqat KO'RISH: xodimlarning texnika kategoriyasi va shartnoma bog'lanishlari. Saytda ular faqat ruxsatlar
    oynasida o'zgaradi. 'permission_employee' kerak; faqat o'z tashkiloti.
    """

    serializer_class = LiableSerializer
    permission_classes = [PermissionManagerPermission]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["employee", "contracts", "categorys"]

    def get_queryset(self):
        qs = Liable.objects.select_related('employee').prefetch_related('contracts', 'categorys').order_by('id')
        return _org_scoped(qs, self.request.user, "employee__organization_id")


class MaterialMovementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Faqat KO'RISH: material harakati jurnali ('view_material' kerak). Saytdagi hisobot kabi doira: o'z tashkiloti
    materiallari bo'yicha, faqat ko'rishga ruxsat etilgan xodimlarning (o'zi yoki 'all_material_employee' bo'lsa
    tashkilotdagi moddiy javobgarlar) materiallari yoki o'zi ishtirok etgan harakatlar. Superuser — hammasi.
    """

    serializer_class = MaterialMovementSerializer
    permission_classes = [MaterialMovementPermission]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["material", "employee", "user", "status"]
    search_fields = ["body"]

    def get_queryset(self):
        qs = MaterialMovement.objects.select_related('user', 'material', 'employee').order_by('-id')
        user = self.request.user
        employee = getattr(user, 'employee', None)
        if not employee or not employee.organization_id:
            return qs.none()
        if user.is_superuser:
            return qs
        allowed = allowed_report_employees(user, employee).values_list('id', flat=True)
        return qs.filter(material__organization_id=employee.organization_id).filter(
            models.Q(material__employee_id__in=list(allowed)) | models.Q(user=employee) | models.Q(employee=employee)
        )


class PermissionCatalogView(APIView):
    """GET /api/permissions/catalog/ — ruxsatlar ro'yxati guruhlari (nomi bilan), bog'liqliklar va SUPER ruxsatlar ('permission_employee' kerak)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .roles import catalog

        if not request.user.has_perm("main.permission_employee"):
            raise PermissionDenied("Ruxsatlarni boshqarish huquqi yo'q")
        return Response(catalog())


class MeView(APIView):
    """
    GET /api/me/ — joriy foydalanuvchining xodim profili va Django
    ruxsatlari ro'yxati ("app_label.codename"). Frontend navigatsiya/ruxsat
    tekshiruvi uchun ishlatadi — JWT o'zi Django permission'larni olib
    yurmaydi, shu sabab bu alohida endpoint kerak.
    """

    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(responses={200: openapi.Response(
        'Joriy foydalanuvchi: xodim, tashkilot turi (worker=ATM vakili, client=mijoz), ariza imkoniyatlari (orders) va ruxsatlar',
        openapi.Schema(type=openapi.TYPE_OBJECT, properties={
            'username': openapi.Schema(type=openapi.TYPE_STRING),
            'is_superuser': openapi.Schema(type=openapi.TYPE_BOOLEAN),
            'employee': openapi.Schema(type=openapi.TYPE_OBJECT),
            'organization_type': openapi.Schema(type=openapi.TYPE_STRING, enum=['worker', 'client']),
            'orders': openapi.Schema(type=openapi.TYPE_OBJECT, description='can_create, can_create_on_behalf, can_execute, can_confirm, can_assign, send_goals, can_create_material_order, material_goals, execute_goals'),
            'permissions': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING)),
        }),
    )})
    def get(self, request):
        user = request.user
        employee = getattr(user, "employee", None)
        org = getattr(employee, "organization", None) if employee else None
        org_type = org.type if org else None   # 'worker' — ATM vakili, 'client' — mijoz

        can_execute = bool(
            employee and org_type != "client" and (user.is_superuser or user.has_perm("main.change_order"))
        )

        # ATM arizasini yuborish mumkin bo'lgan turlar (saytdagi order_sender: worker tashkilot maqsadlari)
        send_goals = list(
            Goal.objects.filter(organization__type="worker").order_by("name", "id")
            .values("id", "name", "organization")
        ) if employee else []
        # Bajaruvchi ijro qila oladigan turlar (OrderGoal)
        exec_goals = []
        if can_execute:
            ids = OrderGoal.goal.through.objects.filter(ordergoal__employee=employee).values_list("goal_id", flat=True)
            exec_goals = list(Goal.objects.filter(id__in=ids).order_by("name", "id").values("id", "name", "organization"))

        # Material arizasi (omborxonaga): faqat o'z tashkilotining ariza turlari; ATM (worker) xodimi yubora olmaydi
        material_goals = []
        if employee and org and org_type != "worker":
            material_goals = list(
                Goal.objects.filter(organization=org, organization__type="client")
                .order_by("name", "id").values("id", "name", "organization")
            )

        return Response({
            "username": user.username,
            "is_superuser": user.is_superuser,
            "employee": EmployeeSerializer(employee).data if employee else None,
            "organization_type": org_type,
            "orders": {
                "can_create": bool(employee),                                   # ATM arizasi yuborish
                "can_create_on_behalf": bool(employee and user.has_perm("main.add_order")),
                "can_execute": can_execute,                                     # qabul qilish, yakunlash, material berish
                "can_confirm": bool(employee and user.has_perm("main.confirm_order")),
                "can_assign": bool(employee and user.is_superuser),             # ijrochini tanlash
                "send_goals": send_goals,
                "can_create_material_order": bool(material_goals),
                "material_goals": material_goals,
                "execute_goals": exec_goals,
            },
            "permissions": sorted(user.get_all_permissions()),
        })