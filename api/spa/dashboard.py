"""
Admin bosh sahifasi (React: /dashboard) — tizim bo'yicha umumiy ko'rinish, faqat superuser uchun.

* overview/?days=7|30|90 — davr ko'rsatkichlari (oldingi teng davr bilan solishtirib), arizalar dinamikasi,
  holatlar, texnika holati, eng faol ijrochilar, ariza turlari, so'nggi arizalar va hujjatlar.
"""
from datetime import timedelta

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.db.models.functions import TruncDate
from django.urls import path
from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from main.models import Deed, Employee, Material, Order, Organization, Technics

PERIODS = (7, 30, 90)
DONE = ("finished", "approved", "accepted")
CLOSED = ("canceled", "rejected")
STALE_DAYS = 3  # imzo kutilayotgan hujjat shuncha kundan eski bo'lsa "kechikkan"


class IsSuperuser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)


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
    permission_classes = [IsSuperuser]

    def get(self, request):
        try:
            days = int(request.query_params.get("days", 30))
        except ValueError:
            days = 30
        if days not in PERIODS:
            days = 30

        now = timezone.now()
        today = timezone.localdate()
        start = now - timedelta(days=days)
        prev_start = start - timedelta(days=days)

        orders = Order.objects.all()
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

        deeds = Deed.objects.all()
        pending = deeds.filter(_deed_pending_q())
        pending_count = pending.count()
        deed_kinds = dict(Deed._meta.get_field("status").choices)
        recent_deeds = pending.select_related("sender", "user").order_by("-date_creat")[:4]

        technics = Technics.objects.filter(is_active=True)
        tech_status = dict(technics.values("status").annotate(c=Count("id")).values_list("status", "c"))
        tech_groups = list(technics.values("group__name").annotate(c=Count("id")).order_by("-c", "group__name"))

        return Response({
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
            "technics_status": {s: tech_status.get(s, 0) for s in ("active", "free", "repair", "defect")},
            # Turlar (guruhlar) bo'yicha: eng ko'p 4 tasi, qolgani "Boshqalar"
            "technics_groups": [
                {"name": g["group__name"] or "Turi ko'rsatilmagan", "count": g["c"]} for g in tech_groups[:4]
            ] + (
                [{"name": "Boshqalar", "count": sum(g["c"] for g in tech_groups[4:])}] if len(tech_groups) > 4 else []
            ),
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
                "employees": Employee.objects.filter(user__is_active=True).count(),
                "organizations": Organization.objects.count(),
                "technics": technics.count(),
                "materials": Material.objects.filter(is_active=True).count(),
            },
        })


urlpatterns = [
    path("overview/", OverviewView.as_view()),
]
