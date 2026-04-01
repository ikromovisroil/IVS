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
        .filter(sender=employee,organization_id=4,status__in=["viewed", "accepted", "finished"],)
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

    if action == "rejected":
        order.status = "rejected"
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


@never_cache
@login_required
def order_approved(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    if request.method != "POST":
        return redirect("/")

    order_id = request.POST.get("order_id")
    rating = request.POST.get("rating")

    order = get_object_or_404(Order, id=order_id)
    order.rating = int(rating)
    order.status = "approved"
    order.receiver_seen = False
    order.save()

    messages.success(request, "Zayafka tasdiqlandi!")
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
        .filter(sender=employee,organization_id=4,status__in=["approved", "rejected",],)
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

    order = get_object_or_404(Order, pk=pk)

    if order.status == "accepted":
        messages.warning(request, "Bu ariza allaqachon qabul qilingan")
        return redirect('order_receiver_activ')

    order.status = "accepted"
    order.receiver = employee
    order.save()

    messages.success(request, "Ariza qabul qilindi!")
    return redirect('order_receiver_activ')


@never_cache
@login_required
@role_required("order")
def order_receiver_activ(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orders_qs = (
        Order.objects
        .filter(receiver=employee,organization_id=4, status__in=["accepted", "finished"])
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


from django.db.models import F
@never_cache
@require_POST
@transaction.atomic
@login_required
@role_required("order")
def ordermaterial_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    order_id = request.POST.get("order_id")
    technics_id = request.POST.get("technics_id")
    material_ids = request.POST.getlist("material_id[]")
    numbers = request.POST.getlist("number[]")

    # 🔒 Order ni lock qilib olamiz (parallel submit bo‘lsa ham)
    order = get_object_or_404(Order.objects.select_for_update(), id=order_id)

    # ✅ Texnika majburiy bo‘lsa: tekshirish
    if technics_id:
        order.technics_id = technics_id

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

        # ✅ Yetarlilik tekshiruvi
        if material.number < n:
            messages.info(request, f"{material.name} yetarli emas! Omborda {material.number} dona bor.")
            return redirect(request.META.get("HTTP_REFERER", "/"))

        # ✅ OrderMaterial yaratish
        OrderMaterial.objects.create(order=order, material=material, number=n)

        # ✅ Ombordan ayrish (atomic)
        material.number = F("number") - n
        material.save(update_fields=["number"])

    # ✅ Status yakunlandi qilish
    order.status = "finished"
    order.save(update_fields=["technics", "status", "date_edit", "date_finished"])

    messages.success(request, "Ariza yakunlandi!")
    return redirect(request.META.get("HTTP_REFERER", "/"))


@never_cache
@login_required
@role_required("order")
def order_receiver_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orders_qs = (
        Order.objects
        .filter(receiver=employee,organization_id=4,status__in=["approved", "rejected",],)
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
        .filter(sender=employee,organization=employee.organization,status__in=["viewed", "accepted", "finished"],)
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

    back_url = request.META.get("HTTP_REFERER", "/")
    goal_id = (request.POST.get("goal") or "").strip()
    body = (request.POST.get("body") or "").strip()

    if not goal_id.isdigit():
        messages.info(request, "Ariza turi tanlanmadi yoki noto‘g‘ri.")
        return redirect("order_sender")

    goal = get_object_or_404(Goal, id=int(goal_id))

    Order.objects.create(
        organization=employee.organization,
        sender=employee,
        goal=goal,
        body=body,
    )
    messages.success(request, "Ariza yuborildi")
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
        .filter(sender=employee,organization=employee.organization,status__in=["approved", "rejected",],)
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

    order = get_object_or_404(Order, pk=pk)

    if order.status == "accepted":
        messages.warning(request, "Bu ariza allaqachon qabul qilingan")
        return redirect('order_receiver_all')

    order.status = "accepted"
    order.receiver = employee
    order.save()

    messages.success(request, "Ariza qabul qilindi!")
    return redirect('order_receiver_activ_all')


@never_cache
@login_required
@role_required("order")
def order_receiver_activ_all(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orders_qs = (
        Order.objects
        .filter(receiver=employee, organization=employee.organization, status__in=["accepted", "finished"])
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
    order.status = "approved"
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
        .filter(receiver=employee,organization=employee.organization,status__in=["approved", "rejected",],)
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
@role_required("confirm")
@transaction.atomic
def order_agrement_material(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    order_id = request.POST.get("order_id")
    ordermaterial_ids = request.POST.getlist("ordermaterial_id[]")
    givens = request.POST.getlist("given[]")

    if not order_id:
        messages.error(request, "Ariza ID topilmadi.")
        return redirect("order_agrement")

    order = get_object_or_404(
        Order.objects.select_for_update().select_related("receiver", "sender"),
        id=order_id
    )

    # if order.receiver and order.receiver != employee:
    #     raise PermissionDenied("Siz bu arizani tasdiqlay olmaysiz.")

    try:
        if not ordermaterial_ids:
            order.status = "approved"
            order.user = employee
            order.save(update_fields=["status", "user", ])
            messages.success(request, "Ariza muvaffaqiyatli tasdiqlandi.")
            return redirect("order_agrement_arxiv")

        for om_id, given in zip(ordermaterial_ids, givens):
            if not om_id:
                continue

            order_material = OrderMaterial.objects.select_for_update().filter(
                id=om_id,
                order=order
            ).first()

            if not order_material:
                continue

            try:
                qty = int(given)
            except (TypeError, ValueError):
                qty = 0

            if qty < 0:
                qty = 0

            order_material.given = qty
            order_material.save(update_fields=["given"])

        order.status = "approved"
        order.user = employee
        order.save(update_fields=["status","user",])

        messages.success(request, "Ariza muvaffaqiyatli tasdiqlandi.")

    except Exception as e:
        messages.error(request, f"Xatolik yuz berdi: {e}")

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
        .filter(user=employee,organization=employee.organization,status__in=["approved", "rejected",],)
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

    if order.receiver != employee:
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