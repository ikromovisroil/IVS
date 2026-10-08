"""
Statistika — saytdagi tex_status va emp_status (main/views.py) bilan bir xil hisob-kitob. 'status_employee' huquqi kerak.
"""
from django.db.models import Avg, Count, F, Q, Value
from django.db.models.functions import Coalesce, Concat
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from main.models import Category, Goal, Group, Order, Region, Technics


class _StatsBase(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def employee(self, request):
        emp = getattr(request.user, "employee", None)
        if not emp:
            raise PermissionDenied("Employee yo'q")
        if not request.user.has_perm("main.status_employee"):
            raise PermissionDenied("Statistikani ko'rish huquqi yo'q")
        return emp


class TechnicsStatsView(_StatsBase):
    """
    GET /api/stats/technics/ — o'z tashkilotining faol texnikalari guruh va kategoriya bo'yicha (soni va foizi).
    Diagramma uchun tayyor: `pie` (hamma guruh), `bar` (eng ko'p 8 guruh).
    """

    def get(self, request):
        emp = self.employee(request)
        org_id = emp.organization_id

        groups = list(
            Group.objects.order_by("id").annotate(
                technics_count=Count(
                    "technics__id",
                    filter=Q(technics__is_active=True, technics__organization_id=org_id),
                    distinct=True,
                )
            ).values("id", "name", "technics_count")
        )
        group_ids = [g["id"] for g in groups]
        total = sum(g["technics_count"] for g in groups)
        divisor = total or 1
        for g in groups:
            g["percent"] = round(g["technics_count"] * 100 / divisor, 1)

        categories = list(
            Category.objects.filter(group_id__in=group_ids).order_by("group_id", "id").values("id", "name", "group_id")
        )
        counts = {
            (row["group_id"], row["category_id"]): row["cnt"]
            for row in Technics.objects.filter(
                is_active=True, organization_id=org_id, group_id__in=group_ids, category_id__isnull=False,
            ).values("group_id", "category_id").annotate(cnt=Count("id"))
        }

        result = []
        for g in groups:
            cats = []
            for c in categories:
                if c["group_id"] != g["id"]:
                    continue
                n = counts.get((g["id"], c["id"]), 0)
                cats.append({
                    "id": c["id"], "name": c["name"], "count": n,
                    "percent": round(n * 100 / g["technics_count"], 1) if g["technics_count"] else 0,
                })
            result.append({
                "id": g["id"], "name": g["name"], "technics_count": g["technics_count"],
                "percent": g["percent"], "categories": cats,
            })

        top = sorted(groups, key=lambda x: x["technics_count"], reverse=True)[:8]
        return Response({
            "total": total,
            "groups": result,
            "pie": {"labels": [g["name"] for g in groups], "values": [g["technics_count"] for g in groups]},
            "bar": {"labels": [g["name"] for g in top], "values": [g["technics_count"] for g in top]},
        })


class EmployeeStatsView(_StatsBase):
    """
    GET /api/stats/employees/?region=&date1=&date2= — bajaruvchi xodimlar bo'yicha arizalar statistikasi
    (o'z tashkiloti ariza turlari bo'yicha). Hech narsa berilmasa — joriy oy (saytdagidek); biror filtr berilsa
    faqat berilgani qo'llanadi. Sana — arizaning yaratilgan sanasi (YYYY-MM-DD).
    `process_count` — jarayonda, `finished_count` — bajarildi, `approved_count` — tasdiqlandi,
    `rejected_count` — rad etilgan va bekor qilingan, `avg_rating` — o'rtacha baho.
    """

    def get(self, request):
        emp = self.employee(request)
        params = request.query_params
        region = (params.get("region") or "").strip()
        raw1 = (params.get("date1") or "").strip()
        raw2 = (params.get("date2") or "").strip()

        date1 = parse_date(raw1) if raw1 else None
        date2 = parse_date(raw2) if raw2 else None
        if raw1 and not date1:
            raise ValidationError({"date1": "Sana formati noto'g'ri (YYYY-MM-DD)"})
        if raw2 and not date2:
            raise ValidationError({"date2": "Sana formati noto'g'ri (YYYY-MM-DD)"})
        if region and not region.isdigit():
            raise ValidationError({"region": "Noto'g'ri qiymat"})

        if not (region or raw1 or raw2):
            today = timezone.localdate()
            date1 = today.replace(day=1)
            nxt = date1.replace(year=date1.year + 1, month=1) if date1.month == 12 else date1.replace(month=date1.month + 1)
            date2 = nxt - timezone.timedelta(days=1)

        orders = Order.objects.filter(receiver__isnull=False)
        if region:
            orders = orders.filter(receiver_region_id=int(region))
        if date1:
            orders = orders.filter(date_creat__date__gte=date1)
        if date2:
            orders = orders.filter(date_creat__date__lte=date2)

        employees = (
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
        )
        goals = (
            Goal.objects.filter(organization=emp.organization)
            .annotate(total=Count("order", filter=Q(order__in=orders)))
            .order_by("-total").values("id", "name", "total")
        )
        rows = []
        for e in employees:
            e = dict(e)
            e["full_name"] = " ".join(e["full_name"].split())
            e["avg_rating"] = round(e["avg_rating"], 2) if e["avg_rating"] is not None else None
            rows.append(e)

        return Response({
            "period": {"date1": date1.isoformat() if date1 else None, "date2": date2.isoformat() if date2 else None},
            "region": int(region) if region else None,
            "employees": rows,
            "goals": list(goals),
        })
