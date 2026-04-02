from .views import *
from main.ajax_views import *
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from main.sso_views import *


# yangi arizalar
@never_cache
@login_required
def order_sender(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orders_qs = (
        Order.objects
        .filter(sender=employee,organization_id=4,status__in=["viewed", "process", "finished",],)
        .select_related("goal", "technics", "receiver", "sender")
        .order_by("-id")
    )

    goals_qs = (
        Goal.objects
        .filter(organization=4)
        .order_by("id")
    )

    # ✅ PAGINATION
    page_number = request.GET.get("page", 1)
    paginator = Paginator(orders_qs, 50)   # har sahifada 4 ta
    page_obj = paginator.get_page(page_number)

    context = {
        "order": page_obj,          # ✅ for loop shu orqali yuradi
        "page_obj": page_obj,       # ✅ pagination uchun
        "paginator": paginator,     # ✅ pagination uchun

        "goal": goals_qs,
    }
    return render(request, "main/order_sender.html", context)


# arizani tasdiqlash yoki bekor qilish
@never_cache
@require_POST
@login_required
def order_decide(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    order = get_object_or_404(Order, id=pk)
    action = request.POST.get("action")  # approve | reject

    if action == "canceled":
        order.status = "canceled"
        order.save()

        messages.success(request, "Ariza bekor qilindi!")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    if action == "approved":
        rating = request.POST.get("rating")

        if not rating:
            messages.error(request, "Iltimos, baho (yulduz) tanlang!")
            return redirect(request.META.get("HTTP_REFERER", "/"))

        try:
            rating = int(rating)
        except ValueError:
            messages.error(request, "Baho noto‘g‘ri!")
            return redirect(request.META.get("HTTP_REFERER", "/"))

        if rating < 1 or rating > 5:
            messages.error(request, "Baho 1 dan 5 gacha bo‘lishi kerak!")
            return redirect(request.META.get("HTTP_REFERER", "/"))

        order.rating = rating
        order.status = "approved"
        order.save()
        messages.success(request, "Ariza tasdiqlandi va baholandi!")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    messages.error(request, "Noma’lum amal!")
    return redirect(request.META.get("HTTP_REFERER", "/"))


# arizalar arxivi
@never_cache
@login_required
def order_sender_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orders_qs = (
        Order.objects
        .filter(sender=employee,organization_id=4,status__in=["approved", "accepted", "canceled", "rejected",],)
        .select_related("goal", "technics", "receiver", "sender")
        .order_by("-id")
    )

    goals_qs = (
        Goal.objects
        .filter(organization=4)
        .order_by("id")
    )

    # ✅ PAGINATION
    page_number = request.GET.get("page", 1)
    paginator = Paginator(orders_qs, 50)   # har sahifada 4 ta
    page_obj = paginator.get_page(page_number)

    context = {
        "order": page_obj,          # ✅ for loop shu orqali yuradi
        "page_obj": page_obj,       # ✅ pagination uchun
        "paginator": paginator,     # ✅ pagination uchun

        "goal": goals_qs,
    }
    return render(request, "main/order_sender_arxiv.html", context)


@never_cache
@require_POST
@login_required
def order_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")

    goal_id = (request.POST.get("goal") or "").strip()
    body = (request.POST.get("body") or "").strip()

    if not goal_id.isdigit():
        messages.info(request, "Ariza turi tanlanmadi yoki noto‘g‘ri.")
        return redirect("order_sender")

    goal = get_object_or_404(Goal, id=int(goal_id))

    Order.objects.create(
        organization=goal.organization,
        sender=employee,
        goal=goal,
        body=body,
    )
    messages.success(request, "Ariza yuborildi")
    return redirect(back_url)


@never_cache
@login_required
@role_required("order")
def order_receiver(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orders_qs = (
        Order.objects
        .filter(sender__region=employee.region,organization_id=4, status="viewed")
        .select_related("goal", "technics", "receiver", "sender")
        .order_by("-id")
    )

    page_number = request.GET.get("page", 1)
    paginator = Paginator(orders_qs, 50)
    page_obj = paginator.get_page(page_number)

    context = {
        "order": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
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
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER") or "/"

    with transaction.atomic():
        order = (
            Order.objects
            .select_for_update()
            .filter(pk=pk)
            .first()
        )

        if not order:
            messages.info(request, "Ariza topilmadi")
            return redirect(back_url)

        if order.status != "viewed":
            messages.warning(request, "Bu ariza allaqachon jarayonda yoki qabul qilingan")
            return redirect(back_url)

        order.status = "process"
        order.receiver = employee
        order.save(update_fields=["status", "receiver", "date_edit"])

    messages.success(request, "✅ Ariza qabul qilindi!")
    return redirect("order_receiver_activ")


@never_cache
@login_required
@role_required("order")
def order_receiver_activ(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orders_qs = (
        Order.objects
        .filter(receiver=employee,organization_id=4, status__in=["process", "finished"])
        .select_related("goal", "technics", "receiver", "sender")
        .order_by("-id")
    )

    sender_ids = MaterialUser.objects.filter(
        receiver=employee
    ).values_list("sender_id", flat=True)

    materials = Material.objects.filter(
        employee_id__in=sender_ids,
        is_active=True,
    )

    page_number = request.GET.get("page", 1)
    paginator = Paginator(orders_qs, 50)
    page_obj = paginator.get_page(page_number)

    context = {
        "order": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "materials": materials,
    }
    return render(request, "main/order_receiver_activ.html", context)


@never_cache
@require_POST
@transaction.atomic
@login_required
@role_required("order")
def order_material_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER") or "/"

    order_id = request.POST.get("order_id")
    technics_id = request.POST.get("technics_id")
    material_ids = request.POST.getlist("material_id[]")
    numbers = request.POST.getlist("number[]")

    if not order_id:
        messages.info(request, "Ariza ID topilmadi!")
        return redirect(back_url)

    # Order ni lock qilamiz
    order = get_object_or_404(
        Order.objects.select_for_update().select_related("receiver"),
        id=order_id
    )

    # Faqat qabul qilingan/jarayondagi arizani yakunlash mumkin
    if order.status not in ["process", "finished"]:
        messages.success(request, "Bu arizani yakunlab bo‘lmaydi")
        return redirect(back_url)

    # Xohlasa shu usernikiligini ham tekshirsa bo'ladi
    if order.receiver and order.receiver != employee:
        messages.success(request, "Bu ariza sizga biriktirilmagan")
        return redirect(back_url)

    # Texnika tanlanmasa ham faqat statusni finished qilamiz
    if not technics_id:
        order.status = "finished"
        order.save(update_fields=["status", "date_edit"])
        messages.success(request, "Ariza yakunlandi!")
        return redirect(back_url)

    order.technics_id = technics_id

    pairs = []
    for m_id, num in zip(material_ids, numbers):
        if not m_id:
            continue

        try:
            n = int(num or 1)
        except (ValueError, TypeError):
            messages.info(request, "Material soni noto‘g‘ri kiritilgan!")
            return redirect(back_url)

        if n <= 0:
            messages.info(request, "Material soni 0 yoki manfiy bo‘lishi mumkin emas!")
            return redirect(back_url)

        pairs.append((m_id, n))

    for m_id, n in pairs:
        material = Material.objects.select_for_update().filter(id=m_id, is_active=True).first()
        if not material:
            messages.info(request, "Material topilmadi!")
            return redirect(back_url)

        current_number = material.number or 0
        if current_number < n:
            messages.info(
                request,
                f"{material.name} yetarli emas! Omborda {current_number} dona bor."
            )
            return redirect(back_url)

        OrderMaterial.objects.create(
            order=order,
            material=material,
            number=n
        )

        Material.objects.filter(pk=material.pk).update(number=F("number") - n)

    order.status = "finished"
    order.save(update_fields=["technics_id", "status", "date_edit"])

    messages.success(request, "Ariza yakunlandi!")
    return redirect(back_url)


@never_cache
@login_required
@role_required("order")
def order_receiver_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orders_qs = (
        Order.objects
        .filter(receiver=employee,organization_id=4,status__in=["approved", "accepted", "canceled", "rejected",],)
        .select_related("goal", "technics", "receiver", "sender")
        .order_by("-id")
    )

    # ✅ PAGINATION
    page_number = request.GET.get("page", 1)
    paginator = Paginator(orders_qs, 50)   # har sahifada 4 ta
    page_obj = paginator.get_page(page_number)

    context = {
        "order": page_obj,          # ✅ for loop shu orqali yuradi
        "page_obj": page_obj,       # ✅ pagination uchun
        "paginator": paginator,     # ✅ pagination uchun
    }
    return render(request, "main/order_receiver_arxiv.html", context)


@never_cache
@login_required
@role_required("order")
def order_receiver_deed(request,pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    order = get_object_or_404(Order, pk=pk)

    if order.receiver != employee:
        raise PermissionDenied

    my_dep_id = request.user.employee.department_id

    context = {
        'order':order,
        'emp_bos':Employee.objects.filter(organization=order.sender.organization,rol__boss=True),
        'employee': Employee.objects.filter(Q(department=order.sender.department) | Q(department_id=my_dep_id)),
    }
    return render(request, "main/order_receiver_deed.html", context)


@never_cache
@require_POST
@login_required
@role_required("order")
def order_receiver_deed_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    # formdan keladiganlar
    sender_id = (request.POST.get("sender") or "").strip()
    message = (request.POST.get("message") or "").strip() or None
    agreements = request.POST.getlist("agreements[]")
    body = request.POST.get("body") or ""

    # sender obyekt
    sender = Employee.objects.filter(id=sender_id).first() if sender_id.isdigit() else None
    if not sender:
        messages.error(request, "Imzolovchi xodim tanlanmadi")
        return redirect("akt_get")

    if not body.strip():
        messages.error(request, "Hujjat matni (body) bo‘sh bo‘lmasin")
        return redirect("akt_get")

    # ✅ Deed yaratamiz
    deed = Deed.objects.create(
        sender=sender,  # FK obyekt
        user=employee,  # FK obyekt
        message_user=message,
        body=body,
        file_type=False,  # ✅ True/False
    )

    # ✅ PDF yaratib deed.file ga saqlaymiz
    try:
        pdf_bytes = deed_to_pdf_bytes(deed)
        wm_text = "TASDIQLANMAGAN"
        pdf_bytes = add_text_watermark_pdf_bytes(pdf_bytes, wm_text)
        today_str = timezone.now().strftime("%Y%m%d")
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        random_part = ''.join(secrets.choice(alphabet) for _ in range(6))
        pdf_name = f"akt_{today_str}_{random_part}.pdf"
        deed.file.save(pdf_name, ContentFile(pdf_bytes), save=True)

    except HtmlPdfError as e:
        messages.warning(request, f"PDF yaratilmadi: {e}")

    # ✅ kelishuvchilar IDs tozalash
    ids = []
    for x in (agreements or []):
        x = (x or "").strip()
        if x.isdigit():
            ids.append(int(x))
    ids = list(set(ids))  # uniq

    # ✅ sender va hozirgi employee’ni exclude
    exclude_ids = {sender.id}
    ids = [i for i in ids if i not in exclude_ids]

    # ✅ DeedConsent bulk_create
    if ids:
        emps = Employee.objects.filter(id__in=ids).only("id")
        objs = [DeedConsent(deed=deed, employee=e, status="viewed") for e in emps]
        DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

    messages.success(request, "Imzolashga yuborildi")
    return redirect("contact_user")



# yangi arizalar imv
@never_cache
@login_required
def order_sender_all(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orders_qs = (
        Order.objects
        .filter(sender=employee,organization=employee.organization,status__in=["viewed", "process", "finished", "approved"],)
        .select_related("receiver", "sender")
        .order_by("-id")
    )

    goals_qs = (
        Goal.objects
        .filter(organization=employee.organization)
        .order_by("id")
    )

    # ✅ PAGINATION
    page_number = request.GET.get("page", 1)
    paginator = Paginator(orders_qs, 50)   # har sahifada 4 ta
    page_obj = paginator.get_page(page_number)

    context = {
        "order": page_obj,          # ✅ for loop shu orqali yuradi
        "page_obj": page_obj,       # ✅ pagination uchun
        "paginator": paginator,     # ✅ pagination uchun

        "goal": goals_qs,
    }
    return render(request, "main/order_sender_all.html", context)


@never_cache
@require_POST
@login_required
def order_post_all(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER") or "order_sender_all"

    goal_id = (request.POST.get("goal") or "").strip()
    body = (request.POST.get("body") or "").strip()

    if not goal_id.isdigit():
        messages.info(request, "Ariza turi tanlanmadi yoki noto‘g‘ri.")
        return redirect("order_sender_all")

    goal = get_object_or_404(
        Goal,
        id=int(goal_id),
        organization=employee.organization
    )

    Order.objects.create(
        organization=employee.organization,
        sender=employee,
        goal=goal,
        body=body,
        status="viewed",
    )
    messages.success(request, "Ariza yuborildi.")
    return redirect(back_url)


@never_cache
@require_POST
@login_required
def order_decide_all(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")
    action = (request.POST.get("action") or "").strip()
    order = get_object_or_404(Order.objects.select_for_update(), id=pk)

    if order.sender != employee:
        messages.info(request, "Ariza sizga tegishli emas.")
        return redirect(back_url)

    if action == "canceled":
        if order.status in ["accepted", "approved", "canceled", "rejected"]:
            messages.info(request, "Bu ariza bo‘yicha amal bajarilgan.")
            return redirect(back_url)

        order.status = "canceled"
        order.save(update_fields=["status", "date_edit"])
        messages.success(request, "Ariza bekor qilindi!")
        return redirect(back_url)

    if action == "accepted":
        if order.status != "approved":
            messages.info(request, "Bu ariza hozir qabul qilinmaydi.")
            return redirect(back_url)

        order.status = "accepted"
        order.save(update_fields=["status", "date_edit"])
        messages.success(request, "Ariza yakunlandi, materiallar ombordan olishingiz mumkin.")
        return redirect(back_url)

    messages.info(request, "Noma’lum amal!")
    return redirect(back_url)


# arizalar arxivi
@never_cache
@login_required
def order_sender_arxiv_all(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orders_qs = (
        Order.objects
        .filter(sender=employee,organization=employee.organization,status__in=["accepted", "canceled", "rejected",],)
        .select_related("goal", "technics", "receiver", "sender")
        .order_by("-id")
    )

    goals_qs = (
        Goal.objects
        .only("id", "name",)
        .order_by("-id")
    )

    # ✅ PAGINATION
    page_number = request.GET.get("page", 1)
    paginator = Paginator(orders_qs, 50)   # har sahifada 4 ta
    page_obj = paginator.get_page(page_number)

    context = {
        "order": page_obj,          # ✅ for loop shu orqali yuradi
        "page_obj": page_obj,       # ✅ pagination uchun
        "paginator": paginator,     # ✅ pagination uchun

        "goal": goals_qs,
    }
    return render(request, "main/order_sender_arxiv_all.html", context)


@never_cache
@login_required
@role_required("order")
def order_receiver_all(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orders_qs = (
        Order.objects
        .filter(sender__region=employee.region,organization=employee.organization,status="viewed")
        .select_related("receiver", "sender")
        .order_by("-id")
    )

    page_number = request.GET.get("page", 1)
    paginator = Paginator(orders_qs, 50)
    page_obj = paginator.get_page(page_number)

    context = {
        "order": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
    }

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "main/partials/order_receiver_all.html", context)

    return render(request, "main/order_receiver_all.html", context)


@never_cache
@require_POST
@login_required
@role_required("order")
def order_accepted_all(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER") or "/"
    action = request.POST.get("action")

    with transaction.atomic():
        order = (
            Order.objects
            .select_for_update()
            .filter(pk=pk)
            .first()
        )

        if not order:
            messages.info(request, "Ariza topilmadi")
            return redirect(back_url)

        # faqat yangi ariza ustida amal bajarilsin
        if order.status != "viewed":
            messages.warning(request, "Bu ariza allaqachon jarayonda yoki ko‘rib chiqilgan")
            return redirect(back_url)

        if action == "process":
            order.status = "process"
            order.receiver = employee
            order.save()
            messages.success(request, "Ariza qabul qilindi!")
            return redirect("order_receiver_activ_all")

        elif action == "rejected":
            order.status = "rejected"
            order.receiver = employee
            order.save()
            messages.success(request, "Ariza rad etildi!")
            return redirect(back_url)

        else:
            messages.warning(request, "Noto‘g‘ri amal tanlandi")
            return redirect(back_url)


@never_cache
@login_required
@role_required("order")
def order_receiver_activ_all(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orders_qs = (
        Order.objects
        .filter(receiver=employee, organization=employee.organization, status__in=["process", "finished"])
        .select_related("goal", "technics", "receiver", "sender")
        .order_by("-id")
    )

    materials = Material.objects.filter(
        organization=employee.organization,
        is_active=True
    )

    page_number = request.GET.get("page", 1)
    paginator = Paginator(orders_qs, 50)
    page_obj = paginator.get_page(page_number)

    context = {
        "order": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "materials": materials,
    }
    return render(request, "main/order_receiver_activ_all.html", context)


@never_cache
@require_POST
@transaction.atomic
@login_required
@role_required("order")
def order_material_all(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    order_id = request.POST.get("order_id")
    material_ids = request.POST.getlist("material_id[]")
    numbers = request.POST.getlist("number[]")

    order = get_object_or_404(Order, id=order_id)

    # ✅ Materiallar bo‘sh bo‘lishi mumkin (xohlasangiz majburiy qiling)
    pairs = []
    for m_id, num in zip(material_ids, numbers):
        if not m_id:
            continue
        try:
            n = int(num or 1)
        except ValueError:
            messages.info(request, "Material soni noto‘g‘ri kiritilgan!")
            return redirect(request.META.get("HTTP_REFERER", "/"))
        if n <= 0:
            messages.info(request, "Material soni 0 yoki manfiy bo‘lishi mumkin emas!")
            return redirect(request.META.get("HTTP_REFERER", "/"))
        pairs.append((m_id, n))

    # 🔁 Har bir materialni tekshirib, ombordagi sonni xavfsiz kamaytiramiz
    for m_id, n in pairs:
        material = Material.objects.select_for_update().filter(id=m_id).first()
        if not material:
            messages.info(request, "Material topilmadi!")
            return redirect(request.META.get("HTTP_REFERER", "/"))

        OrderMaterial.objects.create(order=order, material=material, number=n)

    # ✅ Status yakunlandi qilish
    order.status = "finished"
    order.user = employee
    order.save(update_fields=["technics", "status", "date_edit", "date_approved"])

    messages.success(request, "Ariza yakunlandi!")
    return redirect(request.META.get("HTTP_REFERER", "/"))


@never_cache
@login_required
@role_required("order")
def order_receiver_arxiv_all(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orders_qs = (
        Order.objects
        .filter(receiver=employee,organization=employee.organization,status__in=["approved", "accepted", "canceled", "rejected",],)
        .select_related("goal", "technics", "receiver", "sender")
        .order_by("-id")
    )

    # ✅ PAGINATION
    page_number = request.GET.get("page", 1)
    paginator = Paginator(orders_qs, 50)   # har sahifada 4 ta
    page_obj = paginator.get_page(page_number)

    context = {
        "order": page_obj,          # ✅ for loop shu orqali yuradi
        "page_obj": page_obj,       # ✅ pagination uchun
        "paginator": paginator,     # ✅ pagination uchun
    }
    return render(request, "main/order_receiver_arxiv_all.html", context)



@never_cache
@login_required
@role_required("confirm")
def order_agrement(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orders_qs = (
        Order.objects
        .filter(receiver__region=employee.region,organization=employee.organization, status__in=["finished"])
        .select_related("goal", "technics", "receiver", "sender")
        .order_by("-id")
    )

    page_number = request.GET.get("page", 1)
    paginator = Paginator(orders_qs, 50)
    page_obj = paginator.get_page(page_number)

    context = {
        "order": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
    }
    return render(request, "main/order_agrement.html", context)


@never_cache
@require_POST
@login_required
def order_agrement_material(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")

    order_id = (request.POST.get("order_id") or "").strip()
    ordermaterial_ids = request.POST.getlist("ordermaterial_id[]")
    givens = request.POST.getlist("given[]")

    if not order_id.isdigit():
        messages.info(request, "Ariza ID noto‘g‘ri.")
        return redirect(back_url)

    if not ordermaterial_ids:
        messages.info(request, "Materiallar yuborilmadi.")
        return redirect(back_url)

    if len(ordermaterial_ids) != len(givens):
        messages.info(request, "Yuborilgan ma'lumotlar mos emas.")
        return redirect(back_url)

    # dublikat id yuborilsa xavfli holat bo‘lishi mumkin
    if len(ordermaterial_ids) != len(set(ordermaterial_ids)):
        messages.info(request, "Takroriy materiallar yuborildi.")
        return redirect(back_url)

    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update(),
            pk=int(order_id)
        )

        order_materials = list(
            OrderMaterial.objects
            .select_for_update()
            .select_related("material")
            .filter(order=order, id__in=ordermaterial_ids)
        )

        om_map = {str(item.id): item for item in order_materials}

        if len(om_map) != len(ordermaterial_ids):
            messages.info(request, "Ba'zi materiallar topilmadi.")
            return redirect(back_url)

        material_ids = [om.material_id for om in order_materials if om.material_id]
        if len(material_ids) != len(order_materials):
            messages.info(request, "Ba'zi materiallarga bog'lanish topilmadi.")
            return redirect(back_url)

        # Materiallarni ham lock qilamiz
        materials = list(
            Material.objects
            .select_for_update()
            .filter(id__in=material_ids)
        )
        material_map = {m.id: m for m in materials}

        if len(material_map) != len(set(material_ids)):
            messages.info(request, "Ba'zi materiallar bazada topilmadi.")
            return redirect(back_url)

        ordermaterial_to_update = []
        material_changed_ids = set()

        # Avval validate + xotirada hisoblash
        for om_id, given_value in zip(ordermaterial_ids, givens):
            om = om_map.get(str(om_id))
            if not om:
                messages.info(request, f"Arizadagi material topilmadi: {om_id}")
                return redirect(back_url)

            material = material_map.get(om.material_id)
            if not material:
                messages.info(request, "Material topilmadi.")
                return redirect(back_url)

            try:
                given = int(given_value)
            except (TypeError, ValueError):
                messages.info(request, f"{material.name} uchun beriladigan son noto‘g‘ri.")
                return redirect(back_url)

            if given < 0:
                messages.info(request, f"{material.name} uchun beriladigan son manfiy bo‘lishi mumkin emas.")
                return redirect(back_url)


            old_given = om.given or 0
            delta = given - old_given

            # oshirilayotgan qismni tekshiramiz
            if delta > 0 and material.number < delta:
                messages.info(
                    request,
                    f"{material.name} omborda yetarli emas. Omborda: {material.number}, kerak: {delta}"
                )
                return redirect(back_url)

            # xotirada kamaytirib/qo‘shib boramiz
            material.number -= delta
            material_changed_ids.add(material.id)

            om.given = given
            ordermaterial_to_update.append(om)

        # biror material minusga tushib qolmadimi, yana tekshirib qo‘yamiz
        for material_id in material_changed_ids:
            if material_map[material_id].number < 0:
                messages.info(request, f"{material_map[material_id].name} uchun qoldiq manfiy bo‘lib qoldi.")
                return redirect(back_url)

        # bulk update
        if ordermaterial_to_update:
            OrderMaterial.objects.bulk_update(ordermaterial_to_update, ["given"])

        changed_materials = [material_map[mid] for mid in material_changed_ids]
        if changed_materials:
            Material.objects.bulk_update(changed_materials, ["number"])

        order.user = employee
        order.status = "approved"
        order.save(update_fields=["user", "status", "date_edit"])

    messages.success(request, "Ariza tasdiqlandi")
    return redirect("order_agrement_arxiv")


@never_cache
@login_required
@role_required("confirm")
def order_agrement_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orders_qs = (
        Order.objects
        .filter(user=employee,organization=employee.organization,status__in=["approved", "accepted", "canceled", "rejected"],)
        .select_related("goal", "technics", "receiver", "sender")
        .order_by("-id")
    )

    # ✅ PAGINATION
    page_number = request.GET.get("page", 1)
    paginator = Paginator(orders_qs, 50)   # har sahifada 4 ta
    page_obj = paginator.get_page(page_number)

    context = {
        "order": page_obj,          # ✅ for loop shu orqali yuradi
        "page_obj": page_obj,       # ✅ pagination uchun
        "paginator": paginator,     # ✅ pagination uchun
    }
    return render(request, "main/order_agrement_arxiv.html", context)



@never_cache
@login_required
@role_required("confirm")
def order_agrement_deed(request,pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    order = get_object_or_404(Order, pk=pk)

    if order.user != employee:
        raise PermissionDenied

    my_dep_id = request.user.employee.department_id

    context = {
        'order':order,
        'emp_bos':Employee.objects.filter(department=order.receiver.department,rol__boss=True),
        'employee': Employee.objects.filter(Q(department=order.sender.department) | Q(department_id=my_dep_id)),
    }
    return render(request, "main/order_agrement_deed.html", context)


@never_cache
@require_POST
@login_required
@role_required("confirm")
def order_agrement_deed_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    # formdan keladiganlar
    sender_id = (request.POST.get("sender") or "").strip()
    message = (request.POST.get("message") or "").strip() or None
    agreements = request.POST.getlist("agreements[]")
    body = request.POST.get("body") or ""

    # sender obyekt
    sender = Employee.objects.filter(id=sender_id).first() if sender_id.isdigit() else None
    if not sender:
        messages.error(request, "Imzolovchi xodim tanlanmadi")
        return redirect("akt_get")

    if not body.strip():
        messages.error(request, "Hujjat matni (body) bo‘sh bo‘lmasin")
        return redirect("akt_get")

    # ✅ Deed yaratamiz
    deed = Deed.objects.create(
        sender=sender,  # FK obyekt
        user=employee,  # FK obyekt
        message_user=message,
        body=body,
        file_type=False,  # ✅ True/False
    )

    # ✅ PDF yaratib deed.file ga saqlaymiz
    try:
        pdf_bytes = deed_to_pdf_bytes(deed)
        wm_text = "TASDIQLANMAGAN"
        pdf_bytes = add_text_watermark_pdf_bytes(pdf_bytes, wm_text)
        today_str = timezone.now().strftime("%Y%m%d")
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        random_part = ''.join(secrets.choice(alphabet) for _ in range(6))
        pdf_name = f"akt_{today_str}_{random_part}.pdf"
        deed.file.save(pdf_name, ContentFile(pdf_bytes), save=True)

    except HtmlPdfError as e:
        messages.warning(request, f"PDF yaratilmadi: {e}")

    # ✅ kelishuvchilar IDs tozalash
    ids = []
    for x in (agreements or []):
        x = (x or "").strip()
        if x.isdigit():
            ids.append(int(x))
    ids = list(set(ids))  # uniq

    # ✅ sender va hozirgi employee’ni exclude
    exclude_ids = {sender.id}
    ids = [i for i in ids if i not in exclude_ids]

    # ✅ DeedConsent bulk_create
    if ids:
        emps = Employee.objects.filter(id__in=ids).only("id")
        objs = [DeedConsent(deed=deed, employee=e, status="viewed") for e in emps]
        DeedConsent.objects.bulk_create(objs, ignore_conflicts=True)

    messages.success(request, "Imzolashga yuborildi")
    return redirect("contact_user")