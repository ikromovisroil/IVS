"""
Bosh sahifa (React: /dashboard) — umumiy ko'rinish. Superuser — butun tizim; "Statistikani ko'rish" (status_employee)
huquqi borlar — o'z ko'rish doirasida (`all_organization` / `all_region` bo'lmasa o'z tashkiloti va hududi).

* overview/?days=7|30|90 — davr ko'rsatkichlari (oldingi teng davr bilan solishtirib), arizalar dinamikasi,
  holatlar, texnika holati, eng faol ijrochilar, ariza turlari, so'nggi arizalar va hujjatlar.

Rejimlar (javobdagi scope.mode): "all" — superuser; "worker" — xizmat ko'rsatuvchi tashkilot xodimi (ATM arizalari);
"client" — mijoz tashkiloti xodimi: faqat o'z tashkilotining OMBORXONA arizalari (ATM arizalari emas) va materiallar.
Texnika bloki 'view_technics', materiallar bloki 'view_material' huquqi bo'lsa chiqadi (aks holda null).
"""
from datetime import timedelta

from django.db.models import Avg, Count, DecimalField, DurationField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncDate
from django.urls import path
from django.utils import timezone
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from main.models import Deed, Employee, Liable, Material, Order, Organization, Region, Technics

PERIODS = (7, 30, 90)
DONE = ("finished", "approved", "accepted")
CLOSED = ("canceled", "rejected")
STALE_DAYS = 3  # imzo kutilayotgan hujjat shuncha kundan eski bo'lsa "kechikkan"


class CanSeeDashboard(permissions.BasePermission):
    """Superuser yoki "Statistikani ko'rish" huquqi bor xodim."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_superuser or user.has_perm("main.status_employee")))


class Scope:
    """Ko'rish doirasi: tashkilot/hudud (None — cheklanmagan) va rejim (all | worker | client)."""

    def __init__(self, user):
        self.user = user
        self.employee = None
        self.mode = "all"
        self.org = None
        self.region = None
        self.region_limited = False
        if user.is_superuser:
            return
        emp = getattr(user, "employee", None)
        if not emp:
            raise PermissionDenied("Employee yo'q")
        self.employee = emp
        client = bool(emp.organization_id and emp.organization.type != "worker")
        self.mode = "client" if client else "worker"
        # Mijoz hech qachon o'z tashkilotidan tashqarini ko'rmaydi; xizmat tashkiloti — all_organization bo'lsa hammasi
        if client or not user.has_perm("main.all_organization"):
            if not emp.organization_id:
                raise PermissionDenied("Tashkilot ko'rsatilmagan")
            self.org = emp.organization_id
        if not user.has_perm("main.all_region"):
            self.region_limited = True
            self.region = emp.region_id

    @property
    def barn(self):
        return self.mode == "client"

    @property
    def unlimited(self):
        return self.org is None and not self.region_limited

    def employees_q(self, prefix=""):
        """Employee maydoniga (prefix bilan, masalan "sender__") tashkilot va hudud sharti."""
        q = Q()
        if self.org is not None:
            q &= Q(**{f"{prefix}organization_id": self.org})
        if self.region_limited:
            q &= Q(**{f"{prefix}region_id": self.region}) if self.region is not None else Q(pk__in=[])
        return q

    def orders(self):
        qs = Order.objects.all()
        if self.mode == "all":
            return qs
        if self.barn:
            # Mijoz: faqat o'z tashkilotining omborxona (material) arizalari
            return qs.filter(self.employees_q("sender__"), goal__organization__type="client")
        # Xizmat tashkiloti: o'z tashkiloti/hududi yuborgan yoki ijro etgan arizalar
        if self.unlimited:
            return qs
        return qs.filter(self.employees_q("sender__") | self.employees_q("receiver__"))

    def deeds(self):
        qs = Deed.objects.all()
        if self.mode == "all" or self.unlimited:
            return qs
        return qs.filter(self.employees_q("user__") | self.employees_q("sender__") | self.employees_q("receiver__"))

    def technics(self):
        """Texnikalar ro'yxati bilan bir xil doira (TechnicsViewSet): view_technics, Liable kategoriyalari, tashkilot/hudud."""
        qs = Technics.objects.filter(is_active=True)
        if self.mode == "all":
            return qs
        if not self.user.has_perm("main.view_technics"):
            return None
        liable_ids = Liable.categorys.through.objects.filter(liable__employee=self.employee).values_list("category_id", flat=True)
        qs = qs.filter(category_id__in=liable_ids)
        if self.org is not None:
            qs = qs.filter(organization_id=self.org)
        if self.region_limited:
            qs = qs.filter(region_id=self.region) if self.region is not None else qs.none()
        return qs

    def materials(self):
        """Materiallar ro'yxati bilan bir xil doira (MaterialViewSet): view_material, o'z tashkiloti, ruxsat etilgan xodimlar."""
        qs = Material.objects.filter(is_active=True)
        if self.mode == "all":
            return qs
        if not self.user.has_perm("main.view_material"):
            return None
        from api.views import MaterialViewSet

        ids = MaterialViewSet()._visible_employee_ids(self.user, self.employee)
        return qs.filter(organization_id=self.employee.organization_id, employee_id__in=ids)

    def label(self):
        org = Organization.objects.filter(pk=self.org).values_list("name", flat=True).first() if self.org is not None else None
        region = None
        if self.region_limited and self.region is not None:
            region = Region.objects.filter(pk=self.region).values_list("name", flat=True).first()
        return {"mode": self.mode, "organization": org, "region": region, "barn": self.barn}


def _deed_pending_q():
    """Hali kimdir imzolamagan va hech kim rad etmagan hujjatlar."""
    waiting = Q(status_sender="viewed") | (Q(receiver__isnull=False) & Q(status_receiver="viewed"))
    rejected = Q(status_sender="rejected") | Q(status_receiver="rejected")
    return waiting & ~rejected


def _person(e):
    if not e:
        return None
    return {
        "id": e.id,
        "name": e.full_name,
        "rank": e.rank.name if e.rank_id else None,
        "organization": e.organization.name if e.organization_id else None,
    }


class OverviewView(APIView):
    permission_classes = [CanSeeDashboard]

    def get(self, request):
        try:
            days = int(request.query_params.get("days", 30))
        except ValueError:
            days = 30
        if days not in PERIODS:
            days = 30

        scope = Scope(request.user)
        now = timezone.now()
        today = timezone.localdate()
        start = now - timedelta(days=days)
        prev_start = start - timedelta(days=days)

        orders = scope.orders()
        in_period = orders.filter(date_creat__gte=start)
        in_prev = orders.filter(date_creat__gte=prev_start, date_creat__lt=start)
        done_period = orders.filter(date_finished__gte=start)
        done_prev = orders.filter(date_finished__gte=prev_start, date_finished__lt=start)

        # Kunlik (7/30 kun) yoki haftalik (90 kun) dinamika: yaratilgan va bajarilgan arizalar
        bucket = 1 if days <= 30 else 7
        n_buckets = -(-days // bucket)  # yuqoriga yaxlitlash: 90 kun → 13 hafta, KPI davri to'liq qamraladi
        first_day = today - timedelta(days=n_buckets * bucket - 1)
        created_by_day = dict(
            orders.filter(date_creat__date__gte=first_day).annotate(d=TruncDate("date_creat"))
            .values("d").annotate(c=Count("id")).values_list("d", "c")
        )
        done_by_day = dict(
            orders.filter(date_finished__date__gte=first_day).annotate(d=TruncDate("date_finished"))
            .values("d").annotate(c=Count("id")).values_list("d", "c")
        )
        trend = []
        for i in range(n_buckets):
            b_start = first_day + timedelta(days=i * bucket)
            span = [b_start + timedelta(days=k) for k in range(bucket)]
            trend.append({
                "date": b_start.isoformat(),
                "created": sum(created_by_day.get(d, 0) for d in span),
                "done": sum(done_by_day.get(d, 0) for d in span),
            })

        # O'rtacha bajarish vaqti (qabul qilingandan tayyor bo'lguncha), soatda
        duration = ExpressionWrapper(F("date_finished") - F("date_process"), output_field=DurationField())

        def avg_hours(qs):
            v = qs.filter(date_process__isnull=False).annotate(t=duration).aggregate(a=Avg("t"))["a"]
            return round(v.total_seconds() / 3600, 1) if v else None

        status_counts = dict(in_period.values("status").annotate(c=Count("id")).values_list("status", "c"))

        executors = (
            done_period.filter(receiver__isnull=False).values("receiver")
            .annotate(done=Count("id"), rating=Avg("rating")).order_by("-done")[:5]
        )
        people = Employee.objects.select_related("rank", "organization").in_bulk([x["receiver"] for x in executors])

        goals = (
            in_period.filter(goal__isnull=False).values("goal__name", "goal__organization__type")
            .annotate(c=Count("id")).order_by("-c")[:8]
        )

        recent = (
            orders.select_related("goal", "sender__organization", "sender__rank", "receiver")
            .order_by("-date_creat")[:6]
        )
        status_display = dict(Order._meta.get_field("status").choices)

        deeds = scope.deeds()
        pending = deeds.filter(_deed_pending_q())
        pending_count = pending.count()
        deed_kinds = dict(Deed._meta.get_field("status").choices)
        recent_deeds = pending.select_related("sender", "user").order_by("-date_creat")[:4]

        technics = scope.technics()
        if technics is not None:
            tech_status = dict(technics.values("status").annotate(c=Count("id")).values_list("status", "c"))
            tech_groups = list(technics.values("group__name").annotate(c=Count("id")).order_by("-c", "group__name"))

        materials = scope.materials()
        materials_block = None
        if materials is not None:
            stocked = materials.filter(number__gt=0)
            value = ExpressionWrapper(F("number") * F("price"), output_field=DecimalField(max_digits=18, decimal_places=2))
            materials_block = {
                "items": stocked.count(),
                "empty": materials.filter(number__lte=0).count(),
                "total_sum": str(stocked.aggregate(s=Sum(value))["s"] or 0),
                # Omborda eng ko'p qolgan materiallar
                "top": [
                    {"id": m.id, "name": m.name, "unit": m.unit.name if m.unit_id else None, "number": m.number}
                    for m in stocked.select_related("unit").order_by("-number", "name")[:5]
                ],
            }

        employees_qs = Employee.objects.filter(user__is_active=True)
        if scope.mode != "all":
            employees_qs = employees_qs.filter(scope.employees_q())

        return Response({
            "scope": scope.label(),
            "period": {"days": days, "start": start.date().isoformat(), "end": today.isoformat(), "bucket_days": bucket},
            "kpis": {
                "orders_new": {"value": in_period.count(), "prev": in_prev.count()},
                "orders_done": {"value": done_period.count(), "prev": done_prev.count()},
                "avg_hours": {"value": avg_hours(done_period), "prev": avg_hours(done_prev)},
                "deeds_pending": {
                    "value": pending_count,
                    "stale": pending.filter(date_creat__lt=now - timedelta(days=STALE_DAYS)).count(),
                },
            },
            "trend": trend,
            "orders_status": {
                "viewed": status_counts.get("viewed", 0),
                "process": status_counts.get("process", 0),
                "done": sum(status_counts.get(s, 0) for s in DONE),
                "closed": sum(status_counts.get(s, 0) for s in CLOSED),
            },
            "technics_status": {s: tech_status.get(s, 0) for s in ("active", "free", "repair", "defect")} if technics is not None else None,
            # Turlar (guruhlar) bo'yicha: eng ko'p 4 tasi, qolgani "Boshqalar"
            "technics_groups": ([
                {"name": g["group__name"] or "Turi ko'rsatilmagan", "count": g["c"]} for g in tech_groups[:4]
            ] + (
                [{"name": "Boshqalar", "count": sum(g["c"] for g in tech_groups[4:])}] if len(tech_groups) > 4 else []
            )) if technics is not None else None,
            "materials": materials_block,
            "top_executors": [
                {**(_person(people.get(x["receiver"])) or {"id": x["receiver"], "name": "—"}),
                 "done": x["done"], "rating": round(x["rating"], 1) if x["rating"] else None}
                for x in executors
            ],
            "top_goals": [
                {"name": g["goal__name"], "barn": g["goal__organization__type"] == "client", "count": g["c"]}
                for g in goals
            ],
            "recent_orders": [
                {
                    "id": o.id,
                    "goal": o.goal.name if o.goal_id else None,
                    "sender": _person(o.sender),
                    "receiver": o.receiver.full_name if o.receiver_id else None,
                    "status": o.status,
                    "status_display": status_display.get(o.status, o.status),
                    "date": o.date_creat,
                }
                for o in recent
            ],
            "deeds": {
                "pending": pending_count,
                "approved": deeds.filter(date_sender__gte=start, status_sender="approved").exclude(status_receiver="rejected").count(),
                "rejected": deeds.filter(Q(date_sender__gte=start, status_sender="rejected") | Q(date_receiver__gte=start, status_receiver="rejected")).count(),
                "recent": [
                    {
                        "id": d.id,
                        "kind": d.status,
                        "kind_display": deed_kinds.get(d.status, d.status),
                        "code": d.code,
                        "signer": d.sender.full_name if d.sender_id else None,
                        "author": d.user.full_name if d.user_id else None,
                        "date": d.date_creat,
                    }
                    for d in recent_deeds
                ],
            },
            "totals": {
                "employees": employees_qs.count(),
                "organizations": Organization.objects.count() if scope.org is None else 1,
                "technics": technics.count() if technics is not None else None,
                "materials": materials.count() if materials is not None else None,
            },
        })


urlpatterns = [
    path("overview/", OverviewView.as_view()),
]
