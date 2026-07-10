from .views import *
from main.ajax_views import *
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from main.sso_views import *
from django.db import transaction, DatabaseError
import base64
import binascii
from .html_pdf import _create_deed_for_order


# yangi arizalar
@never_cache
@require_GET
@login_required
def order_sender(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Order.objects
        .filter(sender=employee,goal__type="atm", status__in=["viewed", "process", "finished"],)
        .select_related( "goal", "technics","user", "receiver", "sender")
        .order_by("-id")
    )
    print(orders_qs)

    paginator = Paginator(orders_qs, 20)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
        "goal":     Goal.objects.filter(type="atm").order_by("id"),
    }
    return render(request, "main/order_sender.html", context)


@never_cache
@require_POST
@login_required
def order_decide(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    back_url = request.META.get("HTTP_REFERER", "/")
    action   = (request.POST.get("action") or "").strip()

    if action not in {"approved", "canceled"}:
        messages.info(request, "Noma'lum amal")
        return redirect(back_url)

    order = get_object_or_404(Order, pk=pk)

    if order.sender_id != employee.id and order.user_id != employee.id:
        raise PermissionDenied("Sizda bu arizani o'zgartirish huquqi yo'q")

    if action == "canceled":
        rating = None
    else:
        rating_raw = (request.POST.get("rating") or "").strip()
        try:
            rating = int(rating_raw)
        except (TypeError, ValueError):
            messages.info(request, "Baho noto'g'ri")
            return redirect(back_url)

        if rating not in {1, 2, 3, 4, 5}:
            messages.info(request, "Baho 1 dan 5 gacha bo'lishi kerak")
            return redirect(back_url)

    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=pk)

            order.status = action
            if rating:
                order.rating = rating
            order.save(update_fields=["status", "rating"])

    except DatabaseError:
        messages.info(request, "Xatolik yuz berdi. Qayta urinib ko'ring")
        return redirect(back_url)

    if action == "canceled":
        messages.success(request, "Ariza bekor qilindi")
    else:
        messages.success(request, "Ariza tasdiqlandi")

    return redirect(back_url)


# arizalar arxivi
@never_cache
@require_GET
@login_required
def order_sender_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Order.objects
        .filter(
            sender=employee, goal__type="atm",
            status__in=["approved", "accepted", "canceled", "rejected"],
        )
        .select_related(
            "goal", "technics",
            "user", "receiver", "sender"
        )
        .order_by("-id")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj  = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
        "goal":     Goal.objects.filter(type="atm").order_by("id"),
    }
    return render(request, "main/order_sender_arxiv.html", context)


@never_cache
@require_POST
@login_required
def order_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    back_url = request.META.get("HTTP_REFERER", "/")
    goal_id  = (request.POST.get("goal") or "").strip()
    body     = (request.POST.get("body") or "").strip() or None

    if not goal_id.isdigit():
        messages.info(request, "Ariza turi tanlanmadi")
        return redirect(back_url)

    goal = get_object_or_404(Goal, pk=int(goal_id))

    Order.objects.create(
        sender_id=employee.id,
        goal=goal,
        message_sender=body,
        status="viewed",
    )

    messages.success(request, "Ariza yuborildi")
    return redirect(back_url)


# yangi arizalar
@never_cache
@require_GET
@login_required
@role_required("order_edit")
def order_sender_user(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Order.objects
        .filter(user=employee, goal__type="atm")
        .select_related("goal", "technics", "user", "receiver", "sender")
        .order_by("-id")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
        "goal":     Goal.objects.filter(type="atm").order_by("id"),
        "organizations": Organization.objects.only("id", "name").order_by("id"),
    }
    return render(request, "main/order_sender_user.html", context)


@never_cache
@require_POST
@login_required
@role_required("order_edit")
def order_user_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    back_url = request.META.get("HTTP_REFERER", "/")
    goal_id  = (request.POST.get("goal") or "").strip()
    emp_id = (request.POST.get("employee") or "").strip()
    body     = (request.POST.get("body") or "").strip() or None

    if not goal_id.isdigit():
        messages.info(request, "Ariza turi tanlanmadi")
        return redirect(back_url)

    if not emp_id.isdigit():
        messages.info(request, "Xodim tanlanmadi")
        return redirect(back_url)

    goal = get_object_or_404(Goal, pk=int(goal_id))
    emp = get_object_or_404(Employee, pk=int(emp_id))


    Order.objects.create(
        sender_id=emp.id,
        user_id=employee.id,
        goal=goal,
        message_sender=body,
        status="viewed",
    )

    messages.success(request, "Ariza yuborildi")
    return redirect(back_url)


@never_cache
@require_GET
@login_required
@role_required("order")
def order_receiver(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    if employee.rol.client:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Order.objects
        .filter(sender__region=employee.region, goal__type="atm", status="viewed")
        .select_related( "goal", "technics", "user", "receiver", "sender")
        .order_by("-id")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
    }

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "main/partials/order_receiver_rows.html", context)

    return render(request, "main/order_receiver.html", context)


@never_cache
@require_POST
@login_required
@role_required("order")
def order_accepted(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.rol, "client", False):
        raise PermissionDenied("Sizga ruxsat yo'q")

    back_url = request.META.get("HTTP_REFERER") or "/"

    # Tekshiruvlar transaction tashqarisida
    order = get_object_or_404(Order, pk=pk)

    if order.status != "viewed" or order.receiver_id is not None:
        messages.info(request, "Bu ariza boshqa xodim tomonidan allaqachon qabul qilingan")
        return redirect(back_url)

    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=pk)

            # Race condition — qayta tekshiramiz
            if order.status != "viewed" or order.receiver_id is not None:
                messages.info(request, "Bu ariza boshqa xodim tomonidan allaqachon qabul qilingan")
                return redirect(back_url)

            order.status   = "process"
            order.receiver = employee
            order.save(update_fields=["status", "receiver"])

    except DatabaseError:
        messages.info(request, "Xatolik yuz berdi. Qayta urinib ko'ring")
        return redirect(back_url)

    messages.success(request, "Ariza muvaffaqiyatli qabul qilindi")
    return redirect("order_receiver_activ")


@never_cache
@require_GET
@login_required
@role_required("order")
def order_receiver_activ(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.rol, "client", False):
        raise PermissionDenied("Sizga ruxsat yo'q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Order.objects
        .filter(receiver=employee, goal__type="atm", status__in=["process", "finished"],)
        .select_related("goal", "technics","user", "receiver", "sender")
        .order_by("-id")
    )

    materials = (
        Material.objects
        .filter(
            employee__in=MaterialUser.objects.filter(
                receiver=employee
            ).values("sender"),
            is_active=True,
        )
        .select_related("unit", "employee")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj  = paginator.get_page(page_number)

    context = {
        "page_obj":  page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
        "materials": materials,
    }
    return render(request, "main/order_receiver_activ.html", context)


@never_cache
@require_POST
@login_required
@role_required("order")
@transaction.atomic
def order_material_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.rol, "client", False):
        raise PermissionDenied("Sizga ruxsat yo'q")

    back_url    = request.META.get("HTTP_REFERER") or "/"
    order_id    = (request.POST.get("order_id")    or "").strip()
    technics_id = (request.POST.get("technics_id") or "").strip()
    material_ids = request.POST.getlist("material_id[]")
    numbers      = request.POST.getlist("number[]")

    if not order_id.isdigit():
        messages.info(request, "Ariza ID topilmadi")
        return redirect(back_url)

    if technics_id and not technics_id.isdigit():
        messages.info(request, "Texnika ID noto'g'ri")
        return redirect(back_url)

    order = get_object_or_404(
        Order.objects.select_for_update(),
        id=int(order_id)
    )

    if not order.receiver_id:
        messages.info(request, "Ariza hali hech kimga biriktirilmagan")
        return redirect(back_url)

    if order.receiver_id != employee.id:
        messages.info(request, "Bu arizani faqat uni qabul qilgan xodim yakunlay oladi")
        return redirect(back_url)

    if order.status not in ["process", "finished"]:
        messages.info(request, "Bu ariza yakunlanishi mumkin emas")
        return redirect(back_url)

    # Texnika saqlash
    if technics_id:
        order.technics_id = int(technics_id)

    # Materiallar tozalash
    pairs = []
    seen  = set()

    for m_id, num in zip(material_ids, numbers):
        if not m_id:
            continue
        try:
            m_id = int(m_id)
            n    = int(num or 1)
        except (ValueError, TypeError):
            messages.info(request, "Material yoki son noto'g'ri kiritilgan")
            return redirect(back_url)

        if n <= 0:
            messages.info(request, "Material soni 0 yoki manfiy bo'lishi mumkin emas")
            return redirect(back_url)

        if m_id in seen:
            messages.info(request, "Bir xil materialni bir necha marta kiritmang")
            return redirect(back_url)

        seen.add(m_id)
        pairs.append((m_id, n))

    if pairs:
        materials = list(
            Material.objects
            .select_for_update()
            .filter(id__in=[m for m, _ in pairs], is_active=True)
            .order_by("id")
        )
        materials_map = {m.id: m for m in materials}

        # Yetarliligini tekshirish
        for m_id, n in pairs:
            mat = materials_map.get(m_id)
            if not mat:
                messages.info(request, "Material topilmadi yoki faol emas")
                return redirect(back_url)
            if (mat.number or 0) < n:
                messages.info(request, f'"{mat.name}" yetarli emas. Omborda {mat.number} dona bor')
                return redirect(back_url)

        # Yozish
        order_materials = []
        for m_id, n in pairs:
            mat = materials_map[m_id]
            order_materials.append(OrderMaterial(order=order, material=mat, number=n))
            Material.objects.filter(pk=mat.pk).update(number=F("number") - n)

        OrderMaterial.objects.bulk_create(order_materials)

    order.status = "finished"
    order.save(update_fields=["status", "technics_id"])

    messages.success(request, "Ariza muvaffaqiyatli yakunlandi")
    return redirect(back_url)


@never_cache
@require_GET
@login_required
@role_required("order")
def order_receiver_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.rol, "client", False):
        raise PermissionDenied("Sizga ruxsat yo'q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Order.objects
        .filter(receiver=employee, goal__type="atm", status__in=["approved", "accepted", "canceled", "rejected"],)
        .select_related("goal", "technics","user", "receiver", "sender")
        .order_by("-id")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj  = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
    }
    return render(request, "main/order_receiver_arxiv.html", context)


@never_cache
@require_GET
@login_required
@role_required("order")
def order_receiver_deed(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.rol, "client", False):
        raise PermissionDenied("Sizga ruxsat yo'q")

    order = get_object_or_404(
        Order.objects.select_related(
            "sender", "sender__organization",
            "sender__department", "receiver",
        ),
        pk=pk,
    )

    if order.receiver_id != employee.id:
        raise PermissionDenied("Sizga ruxsat yo'q")

    if not order.sender_id:
        raise PermissionDenied("Ariza jo'natuvchisi yo'q")

    emp_bos = (
        Employee.objects
        .filter(
            organization=order.sender.organization,
        )
        .select_related("organization", "rank")
    )

    employees = (
        Employee.objects
        .filter(
            Q(organization=order.sender.organization) |
            Q(organization=employee.organization)
        )
        .select_related("organization", "rank")
        .distinct()
    )

    context = {
        "order":    order,
        "emp_bos":  emp_bos,
        "employee": employees,
    }
    return render(request, "main/order_receiver_deed.html", context)


@never_cache
@require_POST
@login_required
@role_required("order")
def order_receiver_deed_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if getattr(employee.rol, "client", False):
        raise PermissionDenied("Sizga ruxsat yo'q")

    back_url    = request.META.get("HTTP_REFERER") or "/"
    sender_id  = (request.POST.get("sender")  or "").strip()
    message    = (request.POST.get("message") or "").strip() or None
    agreements = request.POST.getlist("agreements[]")

    # --- Body Base64 orqali keladi (WAF'ni chetlab o'tish uchun) ---
    body_encoded = (request.POST.get("body_encoded") or "").strip()
    body = ""
    if body_encoded:
        try:
            body = base64.b64decode(body_encoded).decode("utf-8").strip()
        except (binascii.Error, UnicodeDecodeError, ValueError):
            body = ""

    sender = Employee.objects.filter(id=sender_id).first() if sender_id.isdigit() else None
    if not sender:
        messages.info(request, "Imzolovchi xodim tanlanmadi")
        return redirect(back_url)

    if not body:
        messages.info(request, "Hujjat matni bo'sh bo'lmasin")
        return redirect(back_url)

    # 1. DB — transaction ichida
    with transaction.atomic():
        deed = Deed.objects.create(
            sender_id=sender.id,
            user_id=employee.id,
            message_user=message,
            body=body,
            status='act',
        )

        ids = list({int(x) for x in agreements if (x or "").strip().isdigit()})
        ids = [i for i in ids if i != sender.id]

        if ids:
            emps = Employee.objects.filter(id__in=ids).only("id")
            objs = [DeedConsent(deed=deed, employee=e, status="viewed") for e in emps]
            DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

    # 2. PDF — transaction tashqarisida
    try:
        pdf_bytes = deed_to_pdf_bytes(deed)
        pdf_bytes = add_text_watermark_pdf_bytes(pdf_bytes, "TASDIQLANMAGAN")
        pdf_name  = f"akt_{timezone.now().strftime('%Y%m%d')}_{secrets.token_urlsafe(6)}.pdf"
        deed.file.save(pdf_name, ContentFile(pdf_bytes), save=True)
    except HtmlPdfError as e:
        messages.info(request, f"PDF yaratilmadi: {e}")

    messages.success(request, "Imzolashga yuborildi")
    return redirect("contact_user")


# yangi arizalar imv
@never_cache
@require_GET
@login_required
def order_sender_barn(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if not getattr(employee.rol, "client", False):
        raise PermissionDenied("Sizga ruxsat yo'q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Order.objects
        .filter(
            sender=employee, organization=employee.organization, goal__type="barn",
            status__in=["viewed", "process", "finished", "approved"],
        )
        .select_related("organization", "user", "receiver", "sender")
        .order_by("-id")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj  = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
    }
    return render(request, "main/order_sender_barn.html", context)


@never_cache
@require_POST
@login_required
def order_decide_barn(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if not getattr(employee.rol, "client", False):
        raise PermissionDenied("Sizga ruxsat yo'q")

    back_url = request.META.get("HTTP_REFERER", "/")
    action   = (request.POST.get("action") or "").strip()

    if action not in {"canceled", "accepted"}:
        messages.info(request, "Noma'lum amal")
        return redirect(back_url)

    # Tekshiruvlar transaction tashqarisida
    order = get_object_or_404(Order, pk=pk)

    if order.sender_id != employee.id:
        messages.info(request, "Ariza sizga tegishli emas")
        return redirect(back_url)

    if action == "canceled" and order.status in {"accepted", "approved", "canceled", "rejected"}:
        messages.info(request, "Bu ariza bo'yicha amal bajarilgan")
        return redirect(back_url)

    if action == "accepted" and order.status != "approved":
        messages.info(request, "Bu ariza hozir qabul qilinmaydi")
        return redirect(back_url)

    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=pk)

            # Race condition — qayta tekshirish
            if action == "canceled" and order.status in {"accepted", "approved", "canceled", "rejected"}:
                messages.info(request, "Bu ariza bo'yicha amal bajarilgan")
                return redirect(back_url)

            if action == "accepted" and order.status != "approved":
                messages.info(request, "Bu ariza hozir qabul qilinmaydi")
                return redirect(back_url)

            order.status = action
            order.save(update_fields=["status"])

            if action == "accepted":
                if order.materials.exists():
                    try:
                        _create_deed_for_order(order, request)
                    except HtmlPdfError:
                        messages.error(request, "Ariza qabul qilindi, lekin hujjat yaratilmadi. Qayta urinib ko'ring")
                        raise
                    except Exception:
                        messages.error(request, "Ariza qabul qilindi, lekin hujjatga imzo/QR urishda xatolik yuz berdi")
                        raise

    except DatabaseError:
        messages.info(request, "Xatolik yuz berdi. Qayta urinib ko'ring")
        return redirect(back_url)

    if action == "canceled":
        messages.success(request, "Ariza bekor qilindi")
    else:

        messages.success(request, "Ariza yakunlandi")

    return redirect(back_url)


@never_cache
@require_GET
@login_required
def order_sender_arxiv_barn(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if not getattr(employee.rol, "client", False):
        raise PermissionDenied("Sizga ruxsat yo'q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Order.objects
        .filter(
            sender=employee,
            goal__type="barn",
            organization=employee.organization,
            status__in=["accepted", "canceled", "rejected"],
        )
        .select_related(
            "organization", "goal", "technics",
            "user", "receiver", "sender"
        )
        .order_by("-id")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj  = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
    }
    return render(request, "main/order_sender_arxiv_barn.html", context)


@never_cache
@require_GET
@login_required
def order_sender_material_barn(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if not getattr(employee.rol, "client", False):
        raise PermissionDenied("Sizga ruxsat yo'q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Material.objects
        .filter(
            organization=employee.organization,
            is_active=True,
        )
        .select_related("organization", "unit")
        .order_by("-id")
    )

    cart_material_ids = set(
        OrderMaterial.objects.filter(
            order__isnull=True,
            user=employee,
            material__isnull=False,
        ).values_list("material_id", flat=True)
    )

    paginator = Paginator(orders_qs, 20)
    page_obj  = paginator.get_page(page_number)

    context = {
        "page_obj":          page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
        "cart_material_ids": cart_material_ids,
    }
    return render(request, "main/order_sender_material_barn.html", context)


@never_cache
@require_GET
@login_required
def order_sender_basket_barn(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if not getattr(employee.rol, "client", False):
        raise PermissionDenied("Sizga ruxsat yo'q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        OrderMaterial.objects
        .filter(
            order__isnull=True,
            user=employee,
            material__isnull=False,
        )
        .select_related("order", "user", "material", "material__unit")
        .order_by("-id")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj  = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
        "goal": Goal.objects.filter(type="barn").order_by("id"),
    }
    return render(request, "main/order_sender_basket_barn.html", context)


@never_cache
@require_POST
@login_required
@transaction.atomic
def create_order_sender_from(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if not getattr(employee.rol, "client", False):
        raise PermissionDenied("Sizga ruxsat yo'q")

    cart_items = list(
        OrderMaterial.objects
        .select_for_update()
        .filter(
            user=employee,
            order__isnull=True,
            material__isnull=False
        )
        .select_related("material")
    )

    body = (request.POST.get("body") or "").strip() or None
    goal_id  = (request.POST.get("goal") or "").strip()

    goal = get_object_or_404(Goal, pk=int(goal_id))

    order = Order.objects.create(
        organization=employee.organization,
        goal=goal,
        sender=employee,
        message_sender=body,
        status="viewed",
    )

    for item in cart_items:
        number = request.POST.get(f"number_{item.id}")
        if number and number.isdigit():
            item.number = max(int(number), 1)
        item.order = order

    OrderMaterial.objects.bulk_update(cart_items, ["number", "order"])

    messages.success(request, "Ariza yuborildi")
    return redirect("order_sender_barn")


@never_cache
@require_GET
@login_required
@role_required("order")
def order_receiver_barn(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if not getattr(employee.rol, "client", False):
        raise PermissionDenied("Sizga ruxsat yo'q")

    page_number = request.GET.get("page", 1)

    if employee.region_id:
        orders_qs = (
            Order.objects
            .filter(
                goal__type="barn",
                sender__region_id=employee.region_id,
                organization=employee.organization,
                status="viewed",
            )
            .select_related(
                "organization", "goal", "technics",
                "user", "receiver", "sender"
            )
            .order_by("-id")
        )
    else:
        orders_qs = Order.objects.none()

    paginator = Paginator(orders_qs, 20)
    page_obj  = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
    }

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "main/partials/order_receiver_barn_rows.html", context)

    return render(request, "main/order_receiver_barn.html", context)


@never_cache
@require_POST
@login_required
@role_required("order")
def order_accepted_barn(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if not getattr(employee.rol, "client", False):
        raise PermissionDenied("Sizga ruxsat yo'q")

    back_url = request.META.get("HTTP_REFERER") or "/"
    action   = (request.POST.get("action") or "").strip()

    if action not in {"process", "rejected"}:
        messages.info(request, "Noto'g'ri amal tanlandi")
        return redirect(back_url)

    # Tekshiruvlar transaction tashqarisida
    order = (
        Order.objects
        .filter(
            pk=pk,
            organization_id=employee.organization_id,
            status="viewed",
        )
        .first()
    )

    if not order:
        messages.info(request, "Ariza topilmadi yoki allaqachon ko'rib chiqilgan")
        return redirect(back_url)

    try:
        with transaction.atomic():
            order = (
                Order.objects
                .select_for_update()
                .filter(pk=pk, status="viewed")
                .first()
            )

            # Race condition — qayta tekshirish
            if not order:
                messages.info(request, "Ariza allaqachon ko'rib chiqilgan")
                return redirect(back_url)

            order.receiver = employee
            order.status   = action
            order.save(update_fields=["status", "receiver"])

    except DatabaseError:
        messages.info(request, "Xatolik yuz berdi. Qayta urinib ko'ring")
        return redirect(back_url)

    if action == "process":
        messages.success(request, "Ariza qabul qilindi")
        return redirect("order_receiver_activ_barn")

    messages.success(request, "Ariza rad etildi")
    return redirect(back_url)


@never_cache
@require_GET
@login_required
@role_required("order")
def order_receiver_activ_barn(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if not getattr(employee.rol, "client", False):
        raise PermissionDenied("Sizga ruxsat yo'q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Order.objects
        .filter(
            goal__type="barn",
            receiver=employee,
            organization=employee.organization,
            status__in=["process", "finished"],
        )
        .select_related(
            "organization", "goal", "technics",
            "user", "receiver", "sender"
        )
        .order_by("-id")
    )

    materials = (
        Material.objects
        .filter(
            organization=employee.organization,
            is_active=True,
        )
        .select_related("unit")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj  = paginator.get_page(page_number)

    context = {
        "page_obj":  page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
        "materials": materials,
    }
    return render(request, "main/order_receiver_activ_barn.html", context)


@never_cache
@require_POST
@login_required
@role_required("order")
def order_material_barn(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if not getattr(employee.rol, "client", False):
        raise PermissionDenied("Sizga ruxsat yo'q")

    back_url          = request.META.get("HTTP_REFERER", "/")
    order_id          = (request.POST.get("order_id") or "").strip()
    body              = (request.POST.get("body") or "").strip()
    ordermaterial_ids = request.POST.getlist("ordermaterial_id[]")
    givens            = request.POST.getlist("given[]")

    if not order_id.isdigit():
        messages.info(request, "Ariza ID noto'g'ri")
        return redirect(back_url)

    if len(ordermaterial_ids) != len(givens):
        messages.info(request, "Yuborilgan ma'lumotlar mos emas")
        return redirect(back_url)

    if len(ordermaterial_ids) != len(set(ordermaterial_ids)):
        messages.info(request, "Takroriy materiallar yuborildi")
        return redirect(back_url)

    try:
        with transaction.atomic():
            order = get_object_or_404(
                Order.objects.select_for_update(),
                pk=int(order_id)
            )

            order_materials = list(
                OrderMaterial.objects
                .select_for_update()
                .filter(order=order, id__in=ordermaterial_ids)
            )

            om_map = {str(item.id): item for item in order_materials}

            if len(om_map) != len(ordermaterial_ids):
                messages.info(request, "Ba'zi materiallar topilmadi")
                return redirect(back_url)

            material_ids = [om.material_id for om in order_materials if om.material_id]
            if len(material_ids) != len(order_materials):
                messages.info(request, "Ba'zi materiallarga bog'lanish topilmadi")
                return redirect(back_url)

            materials    = list(Material.objects.select_for_update().filter(id__in=material_ids))
            material_map = {m.id: m for m in materials}

            if len(material_map) != len(set(material_ids)):
                messages.info(request, "Ba'zi materiallar bazada topilmadi")
                return redirect(back_url)

            ordermaterial_to_update = []
            material_changed_ids    = set()

            for om_id, given_value in zip(ordermaterial_ids, givens):
                om = om_map.get(str(om_id))
                if not om:
                    messages.info(request, f"Arizadagi material topilmadi: {om_id}")
                    return redirect(back_url)

                material = material_map.get(om.material_id)
                if not material:
                    messages.info(request, "Material topilmadi")
                    return redirect(back_url)

                try:
                    given = int(given_value)
                except (TypeError, ValueError):
                    messages.info(request, f"{material.name} uchun beriladigan son noto'g'ri")
                    return redirect(back_url)

                if given <= 0:
                    messages.info(request, f"{material.name} uchun beriladigan son manfiy bo'lishi mumkin emas")
                    return redirect(back_url)

                old_given = om.given or 0
                delta     = given - old_given

                if delta > 0 and material.number < delta:
                    messages.info(
                        request,
                        f"{material.name} omborda yetarli emas. Omborda: {material.number}, kerak: {delta}"
                    )
                    return redirect(back_url)

                material.number -= delta
                material_changed_ids.add(material.id)
                om.given = given
                ordermaterial_to_update.append(om)

            for mid in material_changed_ids:
                if material_map[mid].number < 0:
                    messages.info(request, f"{material_map[mid].name} uchun qoldiq manfiy bo'lib qoldi")
                    return redirect(back_url)

            if ordermaterial_to_update:
                OrderMaterial.objects.bulk_update(ordermaterial_to_update, ["given"])

            changed_materials = [material_map[mid] for mid in material_changed_ids]
            if changed_materials:
                Material.objects.bulk_update(changed_materials, ["number"])

            order.status = "finished"
            order.message_receiver = body
            order.save(update_fields=["status","message_receiver"])

    except DatabaseError:
        messages.info(request, "Xatolik yuz berdi. Qayta urinib ko'ring")
        return redirect(back_url)

    messages.success(request, "Ariza tasdiqlandi")
    return redirect(back_url)


@never_cache
@require_GET
@login_required
@role_required("order")
def order_receiver_arxiv_barn(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if not getattr(employee.rol, "client", False):
        raise PermissionDenied("Sizga ruxsat yo'q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Order.objects
        .filter(
            goal__type="barn",
            receiver=employee,
            organization=employee.organization,
            status__in=["approved", "accepted", "canceled", "rejected"],
        )
        .select_related(
            "organization", "goal", "technics",
            "user", "receiver", "sender"
        )
        .order_by("-id")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj  = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
        }
    return render(request, "main/order_receiver_arxiv_barn.html", context)


@never_cache
@require_GET
@login_required
@role_required("confirm")
def order_agrement(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if not getattr(employee.rol, "client", False):
        raise PermissionDenied("Sizga ruxsat yo'q")

    page_number = request.GET.get("page", 1)

    if employee.region_id:
        orders_qs = (
            Order.objects
            .filter(
                goal__type="barn",
                receiver__region_id=employee.region_id,
                organization=employee.organization,
                status="finished",
            )
            .select_related(
                "organization", "goal", "technics",
                "user", "receiver", "sender"
            )
            .order_by("-id")
        )
    else:
        orders_qs = Order.objects.none()

    paginator = Paginator(orders_qs, 20)
    page_obj  = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
    }
    return render(request, "main/order_agrement.html", context)


@never_cache
@require_POST
@login_required
@role_required("confirm")
def order_agrement_material(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if not getattr(employee.rol, "client", False):
        raise PermissionDenied("Sizga ruxsat yo'q")

    back_url          = request.META.get("HTTP_REFERER", "/")
    order_id          = (request.POST.get("order_id") or "").strip()
    action            = (request.POST.get("action")   or "").strip()
    ordermaterial_ids = request.POST.getlist("ordermaterial_id[]")
    givens            = request.POST.getlist("given[]")

    if not order_id.isdigit():
        messages.info(request, "Ariza ID noto'g'ri")
        return redirect(back_url)

    if action not in ["approved", "rejected"]:
        messages.info(request, "Amal noto'g'ri")
        return redirect(back_url)

    # Tasdiqlash uchun validatsiya
    if action == "approved":
        if len(ordermaterial_ids) != len(givens):
            messages.info(request, "Yuborilgan ma'lumotlar mos emas")
            return redirect(back_url)
        if len(ordermaterial_ids) != len(set(ordermaterial_ids)):
            messages.info(request, "Takroriy materiallar yuborildi")
            return redirect(back_url)
        if not all(str(x).isdigit() for x in ordermaterial_ids):
            messages.info(request, "Material ID noto'g'ri")
            return redirect(back_url)

    try:
        with transaction.atomic():
            order = get_object_or_404(
                Order.objects.select_for_update(),
                pk=int(order_id)
            )

            if order.status != "finished":
                messages.info(request, "Bu arizani tasdiqlash yoki rad etish mumkin emas")
                return redirect(back_url)

            # ── RAD ETISH ──────────────────────────────
            if action == "rejected":
                order_materials = list(
                    OrderMaterial.objects
                    .select_for_update(of=("self",))
                    .filter(order=order)
                    .select_related("material")
                )

                material_ids = [
                    om.material_id for om in order_materials
                    if om.material_id and (om.given or 0) > 0
                ]
                materials    = list(Material.objects.select_for_update().filter(id__in=material_ids))
                material_map = {m.id: m for m in materials}

                changed_materials       = []
                changed_order_materials = []

                for om in order_materials:
                    old_given = om.given or 0
                    if old_given > 0:
                        mat = material_map.get(om.material_id)
                        if mat:
                            mat.number = (mat.number or 0) + old_given
                            changed_materials.append(mat)
                        om.given = 0
                        changed_order_materials.append(om)

                if changed_materials:
                    Material.objects.bulk_update(changed_materials, ["number"])
                if changed_order_materials:
                    OrderMaterial.objects.bulk_update(changed_order_materials, ["given"])

                order.status = "rejected"
                order.user = employee
                order.save(update_fields=["status", "user"])

            # ── TASDIQLASH ─────────────────────────────
            else:
                order_materials = list(
                    OrderMaterial.objects
                    .select_for_update(of=("self",))
                    .filter(order=order, id__in=ordermaterial_ids)
                    .select_related("material")
                )
                om_map = {str(item.id): item for item in order_materials}

                if len(om_map) != len(ordermaterial_ids):
                    messages.info(request, "Ba'zi materiallar topilmadi")
                    return redirect(back_url)

                material_ids = [om.material_id for om in order_materials if om.material_id]
                if len(material_ids) != len(order_materials):
                    messages.info(request, "Ba'zi materiallarga bog'lanish topilmadi")
                    return redirect(back_url)

                materials    = list(Material.objects.select_for_update().filter(id__in=material_ids))
                material_map = {m.id: m for m in materials}

                if len(material_map) != len(set(material_ids)):
                    messages.info(request, "Ba'zi materiallar bazada topilmadi")
                    return redirect(back_url)

                ordermaterial_to_update = []
                material_changed_ids    = set()

                for om_id, given_value in zip(ordermaterial_ids, givens):
                    om       = om_map.get(str(om_id))
                    material = material_map.get(om.material_id)

                    try:
                        given = int(given_value)
                    except (TypeError, ValueError):
                        messages.info(request, f"{material.name} uchun beriladigan son noto'g'ri")
                        return redirect(back_url)

                    if given < 0:
                        messages.info(request, f"{material.name} uchun beriladigan son manfiy bo'lishi mumkin emas")
                        return redirect(back_url)

                    old_given = om.given or 0
                    delta     = given - old_given

                    if delta > 0 and (material.number or 0) < delta:
                        messages.info(
                            request,
                            f"{material.name} omborda yetarli emas. Omborda: {material.number}, kerak: {delta}"
                        )
                        return redirect(back_url)

                    material.number = (material.number or 0) - delta
                    material_changed_ids.add(material.id)
                    om.given = given
                    ordermaterial_to_update.append(om)

                for mid in material_changed_ids:
                    if material_map[mid].number < 0:
                        messages.info(request, f"{material_map[mid].name} uchun qoldiq manfiy bo'lib qoldi")
                        return redirect(back_url)

                if ordermaterial_to_update:
                    OrderMaterial.objects.bulk_update(ordermaterial_to_update, ["given"])

                changed_materials = [material_map[mid] for mid in material_changed_ids]
                if changed_materials:
                    Material.objects.bulk_update(changed_materials, ["number"])

                order.status = "approved"
                order.user = employee
                order.save(update_fields=["status", "user"])

    except DatabaseError as e:
        messages.info(request, "Xatolik yuz berdi. Qayta urinib ko'ring")
        return redirect(back_url)

    if action == "rejected":
        messages.success(request, "Ariza rad etildi. Materiallar omborga qaytarildi")
    else:
        messages.success(request, "Ariza tasdiqlandi")

    return redirect("order_agrement_arxiv")


@never_cache
@require_GET
@login_required
@role_required("confirm")
def order_agrement_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo'q")

    if not getattr(employee.rol, "client", False):
        raise PermissionDenied("Sizga ruxsat yo'q")

    page_number = request.GET.get("page", 1)

    orders_qs = (
        Order.objects
        .filter(
            user=employee,
            goal__type="barn",
            organization=employee.organization,
            status__in=["approved", "accepted", "canceled", "rejected"],
        )
        .select_related(
            "organization", "goal", "technics",
            "user", "receiver", "sender"
        )
        .order_by("-id")
    )

    paginator = Paginator(orders_qs, 20)
    page_obj  = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "row_start": page_obj.start_index() if paginator.count else 0,
    }
    return render(request, "main/order_agrement_arxiv.html", context)