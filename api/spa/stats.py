"""
Statistika bo'limi (React: frontend/src/pages/stats/) — /api/v1/spa/stats/.

Eski sahifalar main/views.py dagi tex_status, emp_status, org_status (HTML). Ular hisob-kitobni shablonga beradi,
shuning uchun bu yerda xuddi shu so'rovlar JSON ko'rinishida qaytariladi: bir xil filtrlar, standart qiymatlar va
ko'rish doirasi (`main.all_organization` / `main.all_region`). Tuzilma tekshiruvi, ariza turi va xodim modali
main/views.py dagi funksiyalardan olinadi (`_employee_structure_error`, `_status_goal_type`, `org_status_employee`).

  GET technics/       ?organization&region&department&directorate&division  — texnikalar (guruh/kategoriya)
  GET employees/      ?region&date1&date2                                    — bajaruvchi xodimlar samaradorligi
  GET organizations/  ?organization&region&department&directorate&division&date1&date2&page — ariza bergan xodimlar
  GET organizations/employee/<pk>/?date1&date2                               — xodimning kategoriyalar bo'yicha arizalari
"""
from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Avg, Count, F, Q, Value
from django.db.models.functions import Coalesce, Concat
from django.shortcuts import get_object_or_404
from django.urls import path
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from main.models import (Category, Department, Directorate, Division, Employee, Goal, Group, Order, Organization,
                         Region, Technics)
from main.views import (ORG_STATUS_PAGE_SIZE, _employee_structure_error, _status_goal_type, org_status_employee,
                        tex_group_icon)

STRUCTURE_KEYS = ("department", "directorate", "division")


def _month_bounds():
    """Joriy oy: birinchi va oxirgi kun (eski sahifalardagi standart davr)."""
    first = timezone.localdate().replace(day=1)
    nxt = first.replace(year=first.year + 1, month=1) if first.month == 12 else first.replace(month=first.month + 1)
    return first, nxt - timedelta(days=1)


def _date(params, key):
    raw = (params.get(key) or "").strip()
    if not raw:
        return raw, None
    try:
        value = parse_date(raw)
    except ValueError:
        value = None
    if value is None:
        raise ValidationError({key: "Sana formati noto'g'ri (YYYY-MM-DD)"})
    return raw, value


def _names(org_id, region_id, dep_id, dir_id, div_id):
    """Tanlangan qiymatlarning nomlari (sarlavha va Select uchun)."""
    def name(model, raw):
        return model.objects.filter(pk=int(raw)).values_list("name", flat=True).first() if raw.isdigit() else None
    return {
        "organization": name(Organization, org_id),
        "region": "Barcha hududlar" if region_id == "all" else name(Region, region_id),
        "department": name(Department, dep_id),
        "directorate": name(Directorate, dir_id),
        "division": name(Division, div_id),
    }


class _StatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.emp = getattr(request.user, "employee", None)
        if not self.emp:
            raise PermissionDenied("Employee yo'q")
        if not request.user.has_perm("main.status_employee"):
            raise PermissionDenied("Statistikani ko'rish huquqi yo'q")
        self.can_all = request.user.has_perm("main.all_organization")
        self.can_all_regions = request.user.has_perm("main.all_region")

    def scoped(self):
        organizations = Organization.objects.only("id", "name").order_by("id")
        regions = Region.objects.only("id", "name").order_by("id")
        if not self.can_all:
            organizations = organizations.filter(pk=self.emp.organization_id)
        if not self.can_all_regions:
            regions = regions.filter(pk=self.emp.region_id)
        return organizations, regions

    def check_region(self, region_id):
        # Ko'rish doirasi serverda tekshiriladi: o'z hududidan boshqasini so'rab bo'lmaydi
        if region_id and not self.can_all_regions and region_id != str(self.emp.region_id):
            raise PermissionDenied("Bu hudud bo'yicha ruxsat yo'q")


class TechnicsStats(_StatsView):
    """main.views.tex_status bilan bir xil: birinchi ochilishda (organization/region berilmasa) xodimning o'z
    tashkiloti, hududi va departmenti tanlanadi; tashkilot va hudud tanlanmaguncha ma'lumot bo'sh."""

    def get(self, request):
        params = request.query_params
        emp = self.emp
        organizations, regions = self.scoped()

        submitted = "organization" in params or "region" in params
        if submitted:
            org_id = (params.get("organization") or "").strip()
            region_id = (params.get("region") or "").strip()
            dep_id = (params.get("department") or "").strip()
        else:
            org_id = str(emp.organization_id or "")
            region_id = str(emp.region_id) if emp.region_id else ("all" if self.can_all_regions else "")
            dep_id = str(emp.department_id or "")
        dir_id = (params.get("directorate") or "").strip()
        div_id = (params.get("division") or "").strip()

        self.check_region(region_id)
        organization = get_object_or_404(organizations, pk=int(org_id)) if org_id.isdigit() else None
        if region_id.isdigit():
            get_object_or_404(regions, pk=int(region_id))
        all_regions_selected = self.can_all_regions and region_id == "all"

        message = None
        ready = organization is not None and (region_id.isdigit() or all_regions_selected)
        if not ready:
            if submitted:
                message = "Tashkilot va hududni tanlang"
            dep_id = dir_id = div_id = ""
        else:
            message = _employee_structure_error(organization, dep_id, dir_id, div_id)
            if message:
                dep_id = dir_id = div_id = ""

        tech_filter = {"is_active": True, "organization_id": organization.id if ready else 0}
        if region_id.isdigit():
            tech_filter["region_id"] = int(region_id)
        for key, raw in (("department_id", dep_id), ("directorate_id", dir_id), ("division_id", div_id)):
            if raw.isdigit():
                tech_filter[key] = int(raw)

        groups = list(
            Group.objects.order_by("id").annotate(
                technics_count=Count(
                    "technics__id",
                    filter=Q(**{f"technics__{key}": value for key, value in tech_filter.items()}),
                    distinct=True,
                )
            ).values("id", "name", "technics_count")
        )
        group_ids = [g["id"] for g in groups]
        divisor = sum(g["technics_count"] for g in groups) or 1
        categories = list(
            Category.objects.filter(group_id__in=group_ids).order_by("group_id", "id").values("id", "name", "group_id")
        )
        lookup = {
            (row["group_id"], row["category_id"]): row["cnt"]
            for row in Technics.objects.filter(group_id__in=group_ids, category_id__isnull=False, **tech_filter)
            .values("group_id", "category_id").annotate(cnt=Count("id"))
        }

        result = []
        for position, g in enumerate(groups):
            total = g["technics_count"]
            cats = []
            for c in categories:
                if c["group_id"] != g["id"]:
                    continue
                n = lookup.get((g["id"], c["id"]), 0)
                cats.append({"id": c["id"], "name": c["name"], "count": n,
                             "share": round(n * 100 / total, 1) if total else 0})
            cats.sort(key=lambda c: (-c["count"], c["id"]))
            result.append({
                "id": g["id"], "name": g["name"], "total": total,
                "share": round(total * 100 / divisor, 1),
                "color": position % 8,                       # rang guruhning ID tartibidagi o'rniga bog'liq
                "icon": tex_group_icon(g["name"], position),  # Bootstrap ikonka nomi (eski sahifa); SPA o'zinikini tanlaydi
                "categories": cats,
            })
        result.sort(key=lambda g: (-g["total"], g["id"]))

        total = sum(g["total"] for g in result)
        top = result[0] if result and result[0]["total"] else None
        return Response({
            "filters": {"organization": org_id, "region": region_id, "department": dep_id,
                        "directorate": dir_id, "division": div_id},
            "names": _names(org_id, region_id, dep_id, dir_id, div_id),
            "ready": ready,
            "message": message,
            "kpi": {
                "total": total,
                "groups": sum(1 for g in result if g["total"]),
                "categories": sum(1 for g in result for c in g["categories"] if c["count"]),
                "top_name": top["name"] if top else None,
                "top_count": top["total"] if top else 0,
                "top_share": top["share"] if top else 0,
            },
            "groups": result,
        })


class EmployeeStats(_StatsView):
    """main.views.emp_status bilan bir xil: filtr berilmasa — joriy oy; hudud tanlanmaguncha ma'lumot bo'sh,
    "all" (Barcha hududlar) faqat `main.all_region` bilan."""

    def get(self, request):
        params = request.query_params
        emp = self.emp
        region_id = (params.get("region") or "").strip()
        raw1, date1 = _date(params, "date1")
        raw2, date2 = _date(params, "date2")
        self.check_region(region_id)

        if not (region_id or raw1 or raw2):
            date1, date2 = _month_bounds()

        orders = Order.objects.filter(receiver__isnull=False)
        all_regions_selected = self.can_all_regions and region_id == "all"
        ready = region_id.isdigit() or all_regions_selected
        if region_id.isdigit():
            orders = orders.filter(receiver_region_id=int(region_id))
        elif not all_regions_selected:
            orders = orders.none()
        if date1:
            orders = orders.filter(date_creat__date__gte=date1)
        if date2:
            orders = orders.filter(date_creat__date__lte=date2)

        rows = []
        for row in (
            orders.filter(goal__organization=emp.organization)
            .values("receiver_id")
            .annotate(
                full_name=Concat(
                    Coalesce(F("receiver__last_name"), Value("")), Value(" "),
                    Coalesce(F("receiver__first_name"), Value("")), Value(" "),
                    Coalesce(F("receiver__father_name"), Value("")),
                ),
                process_count=Count("id", filter=Q(status="process")),
                finished_count=Count("id", filter=Q(status="finished")),
                approved_count=Count("id", filter=Q(status="approved")),
                rejected_count=Count("id", filter=Q(status="rejected") | Q(status="canceled")),
                total_count=Count("id"),
                avg_rating=Avg("rating"),
            )
            .order_by("-total_count", "-approved_count")
        ):
            row["full_name"] = " ".join(row["full_name"].split())
            row["avg_rating"] = round(row["avg_rating"], 1) if row["avg_rating"] is not None else None
            rows.append(row)

        goals = list(
            Goal.objects.filter(organization=emp.organization)
            .annotate(total=Count("order", filter=Q(order__in=orders)))
            .order_by("-total").values("id", "name", "total")
        ) if ready else []

        return Response({
            "filters": {"region": region_id, "date1": date1.isoformat() if date1 else "",
                        "date2": date2.isoformat() if date2 else ""},
            "ready": ready,
            "employees": rows,
            "goals": goals,
        })


class OrganizationStats(_StatsView):
    """main.views.org_status bilan bir xil: tashkilot va hudud majburiy, sana berilmasa — joriy oy;
    faqat tanlangan davrda ariza bergan xodimlar, 20 tadan sahifalanadi."""

    def get(self, request):
        params = request.query_params
        emp = self.emp
        goal_type, kind_label = _status_goal_type(emp)
        organizations, regions = self.scoped()

        org_id = (params.get("organization") or "").strip()
        region_id = (params.get("region") or "").strip()
        dep_id, dir_id, div_id = ((params.get(k) or "").strip() for k in STRUCTURE_KEYS)
        raw1, date1 = _date(params, "date1")
        raw2, date2 = _date(params, "date2")
        if not raw1 and not raw2:
            date1, date2 = _month_bounds()
        self.check_region(region_id)

        response = {
            "filters": {"organization": org_id, "region": region_id, "department": dep_id, "directorate": dir_id,
                        "division": div_id, "date1": date1.isoformat() if date1 else "",
                        "date2": date2.isoformat() if date2 else ""},
            "names": _names(org_id, region_id, dep_id, dir_id, div_id),
            "kind_label": kind_label,
            "searched": False,
            "message": None,
            "totals": {"employees": 0, "orders": 0, "active_senders": 0},
            "count": 0,
            "page_size": ORG_STATUS_PAGE_SIZE,
            "results": [],
        }
        if not org_id.isdigit() or not region_id.isdigit():
            if any(k in params for k in ("organization", "region", *STRUCTURE_KEYS)):
                response["message"] = "Tashkilot va hududni tanlang"
            return Response(response)

        organization = get_object_or_404(organizations, pk=int(org_id))
        get_object_or_404(regions, pk=int(region_id))
        structure_error = _employee_structure_error(organization, dep_id, dir_id, div_id)
        if structure_error:
            response["message"] = structure_error
            return Response(response)

        staff = Employee.objects.filter(organization=organization, user__is_active=True, region_id=int(region_id))
        for key, raw in zip(("department_id", "directorate_id", "division_id"), (dep_id, dir_id, div_id)):
            if raw.isdigit():
                staff = staff.filter(**{key: int(raw)})

        dated = Q()
        if date1:
            dated &= Q(order_sender__date_creat__date__gte=date1)
        if date2:
            dated &= Q(order_sender__date_creat__date__lte=date2)
        rows = (
            staff.select_related("rank", "department", "directorate", "division")
            .annotate(order_count=Count("order_sender", filter=dated & Q(order_sender__goal__organization__type=goal_type),
                                        distinct=True))
            .filter(order_count__gt=0)
            .order_by("-order_count", F("department_id").asc(nulls_last=True), F("directorate_id").asc(nulls_last=True),
                      F("division_id").asc(nulls_last=True), "id")
        )
        orders = Order.objects.filter(sender__in=staff.values("id"), goal__organization__type=goal_type)
        if date1:
            orders = orders.filter(date_creat__date__gte=date1)
        if date2:
            orders = orders.filter(date_creat__date__lte=date2)

        page_obj = Paginator(rows, ORG_STATUS_PAGE_SIZE).get_page(params.get("page"))
        response.update({
            "searched": True,
            "totals": {
                "employees": staff.count(),
                "orders": orders.count(),
                "active_senders": orders.values("sender_id").distinct().count(),
            },
            "count": page_obj.paginator.count,
            "page": page_obj.number,
            "results": [
                {
                    "id": e.id,
                    "full_name": e.full_name,
                    "rank": e.rank.name if e.rank_id else None,
                    "department": e.department.name if e.department_id else None,
                    "directorate": e.directorate.name if e.directorate_id else None,
                    "division": e.division.name if e.division_id else None,
                    "order_count": e.order_count,
                }
                for e in page_obj
            ],
        })
        return Response(response)


urlpatterns = [
    path("technics/", TechnicsStats.as_view(), name="spa_stats_technics"),
    path("employees/", EmployeeStats.as_view(), name="spa_stats_employees"),
    path("organizations/", OrganizationStats.as_view(), name="spa_stats_organizations"),
    # Modal: eski sahifadagi view o'zi JSON qaytaradi (ruxsat va doira o'sha yerda) — to'g'ridan-to'g'ri ulanadi
    path("organizations/employee/<int:pk>/", org_status_employee, name="spa_stats_org_employee"),
]
