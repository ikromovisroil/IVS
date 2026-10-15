"""Bildirishnomalar markazi (sayt): ro'yxat, ochish (o'qilgan qiladi), hammasini o'qilgan qilish, hisoblagich."""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.text import Truncator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .models import Notification
from .notifications import mark_all_read, mark_read, safe_url, unread_count

PAGE_SIZE = 20
KINDS = {kind for kind, _ in Notification.KINDS}
TABS = [
    ("", "Hammasi"),
    ("unread", "O'qilmagan"),
    (Notification.KIND_ORDER, "Ariza"),
    (Notification.KIND_DEED, "Hujjat"),
    (Notification.KIND_MEETING, "Zoom"),
    (Notification.KIND_CHAT, "Chat"),
]


def _employee(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")
    return employee


@never_cache
@require_GET
@login_required
def notifications_page(request):
    employee = _employee(request)
    tab = (request.GET.get("tab") or "").strip()
    qs = Notification.objects.filter(employee=employee)
    if tab == "unread":
        qs = qs.filter(is_read=False)
    elif tab in KINDS:
        qs = qs.filter(kind=tab)
    else:
        tab = ""

    page_obj = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "core/notifications.html", {
        "tabs": TABS,
        "tab": tab,
        "page_obj": page_obj,
        "pager_other": f"&tab={tab}" if tab else "",
        "unread_total": unread_count(employee),
    })


@never_cache
@require_GET
@login_required
def notification_open(request, pk):
    """Bildirishnomani o'qilgan qilib, unga tegishli sahifaga o'tkazadi (faqat o'zinikini)."""
    employee = _employee(request)
    notification = get_object_or_404(Notification, pk=pk, employee=employee)
    mark_read(employee, [notification.id])
    return redirect(safe_url(notification.url))


@never_cache
@require_POST
@login_required
def notifications_read_all(request):
    employee = _employee(request)
    tab = (request.POST.get("tab") or "").strip()
    mark_all_read(employee, kind=tab if tab in KINDS else None)
    target = request.META.get("HTTP_REFERER") or "/notifications/"
    return redirect(target)


RECENT_LIMIT = 6


@never_cache
@require_GET
@login_required
def notifications_recent(request):
    """Qo'ng'iroqcha menyusi uchun: o'qilmagan soni va oxirgi yangi bildirishnomalar (sahifani yangilamasdan)."""
    employee = _employee(request)
    unread = Notification.objects.filter(employee=employee, is_read=False)
    items = [
        {
            "id": n.id,
            "title": n.title,
            "body": Truncator(n.body).chars(70),
            "count": n.count,
            "date": timezone.localtime(n.date_creat).strftime("%d.%m.%Y %H:%M"),
            "open_url": reverse("notification_open", args=[n.id]),
        }
        for n in unread.order_by("-date_creat", "-id")[:RECENT_LIMIT]
    ]
    return JsonResponse({"unread": unread.count(), "items": items})


@never_cache
@require_GET
@login_required
def notifications_count(request):
    return JsonResponse({"unread": unread_count(_employee(request))})
