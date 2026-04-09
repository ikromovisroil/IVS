from .views import *
from main.ajax_views import *
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from main.sso_views import *
from django.db import transaction, DatabaseError

# yangi arizalar
@never_cache
@require_GET
@login_required
def order_sender(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orders_qs = (
        Order.objects
        .filter(sender=employee,organization_id=4,status__in=["viewed", "process", "finished",],)
        .select_related("goal", "technics", "user", "receiver", "sender")
        .order_by("-id")
    )

    goals_qs = (
        Goal.objects
        .filter(organization_id=4)
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


@never_cache
@require_POST
@login_required
def order_decide(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")
    action = (request.POST.get("action") or "").strip()

    if action not in {"approved", "canceled"}:
        messages.info(request, "Noma’lum amal!")
        return redirect(back_url)

    try:
        with transaction.atomic():
            order = get_object_or_404(
                Order.objects.select_for_update(),
                pk=pk,
            )

            if not order:
                messages.info(request, "Ariza topilmadi!")
                return redirect(back_url)

            if order.sender_id != employee.id:
                raise PermissionDenied("Sizda bu arizani o‘zgartirish huquqi yo‘q")

            if order.status != "finished":
                messages.info(request, "Faqat bajarilgan arizani tasdiqlash yoki bekor qilish mumkin.")
                return redirect(back_url)

            if action == "canceled":
                order.status = "canceled"
                order.save(update_fields=["status", "date_edit"])
                messages.success(request, "Ariza bekor qilindi!")
                return redirect(back_url)

            rating_raw = (request.POST.get("rating") or "").strip()

            try:
                rating = int(rating_raw)
            except (TypeError, ValueError):
                messages.info(request, "Baho noto‘g‘ri!")
                return redirect(back_url)

            if rating not in {1, 2, 3, 4, 5}:
                messages.info(request, "Baho 1 dan 5 gacha bo‘lishi kerak!")
                return redirect(back_url)

            order.rating = rating
            order.status = "approved"
            order.save(update_fields=["rating", "status", "date_edit"])

    except DatabaseError:
        messages.info(request, "Xatolik yuz berdi. Qayta urinib ko‘ring.")
        return redirect(back_url)

    messages.info(request, "Amal bajarilmadi.")
    return redirect(back_url)


# arizalar arxivi
@never_cache
@require_GET
@login_required
def order_sender_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    orders_qs = (
        Order.objects
        .filter(sender=employee,organization_id=4,status__in=["approved", "accepted", "canceled", "rejected",],)
        .select_related("goal", "technics", "user", "receiver", "sender")
        .order_by("-id")
    )

    goals_qs = (
        Goal.objects
        .filter(organization_id=4)
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

    with transaction.atomic():
        goal = get_object_or_404(
            Goal.objects.select_related("organization"),
            pk=int(goal_id)
        )

        Order.objects.create(
            organization_id=goal.organization.id,
            sender_id=employee.id,
            goal_id=goal.id,
            body=body,
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

    orders_qs = (
        Order.objects
        .filter(sender__region=employee.region,organization_id=4, status="viewed")
        .select_related("goal", "technics", "user", "receiver", "sender")
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

    try:
        with transaction.atomic():
            order = (
                Order.objects
                .select_for_update()
                .select_related("receiver", "sender", "organization")
                .filter(pk=pk)
                .first()
            )

            if not order:
                messages.info(request, "Ariza topilmadi")
                return redirect(back_url)

            # Faqat hali hech kim olmagan va viewed holatdagi ariza olinadi
            if order.status != "viewed" or order.receiver_id is not None:
                messages.info(request, "Bu ariza boshqa xodim tomonidan allaqachon qabul qilingan")
                return redirect(back_url)

            order.status = "process"
            order.receiver = employee
            order.save(update_fields=["status", "receiver", "date_edit"])

    except Exception as e:
        messages.info(request, f"Xatolik yuz berdi: {e}")
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
        raise PermissionDenied("Employee yo‘q")

    if employee.rol.client:
        raise PermissionDenied("Sizga ruxsat yo‘q")

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
@login_required
@role_required("order")
@transaction.atomic
def order_material_post(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    if employee.rol.client:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    back_url = request.META.get("HTTP_REFERER") or "/"

    order_id = request.POST.get("order_id")
    technics_id = request.POST.get("technics_id")
    material_ids = request.POST.getlist("material_id[]")
    numbers = request.POST.getlist("number[]")

    if not order_id:
        messages.info(request, "Ariza ID topilmadi!")
        return redirect(back_url)

    # 1) Order ni lock qilamiz
    order = get_object_or_404(
        Order.objects.select_for_update().select_related("receiver"),
        id=order_id
    )

    # 3) Faqat shu arizani qabul qilgan odam yakunlay oladi
    if not order.receiver_id:
        messages.info(request, "Ariza hali hech kimga biriktirilmagan.")
        return redirect(back_url)

    if order.receiver_id != employee.id:
        messages.info(request, "Bu arizani faqat uni qabul qilgan xodim yakunlay oladi.")
        return redirect(back_url)

    # 4) Texnika bo‘lmasa faqat orderni finished qilamiz
    # xohlasang buni majburiy ham qilsa bo‘ladi
    if not technics_id:
        order.status = "finished"
        order.save(update_fields=["status", "date_edit"])
        messages.success(request, "Ariza yakunlandi!")
        return redirect(back_url)

    # 5) Materiallar ro‘yxatini tozalab olamiz
    pairs = []
    seen_materials = set()

    for m_id, num in zip(material_ids, numbers):
        if not m_id:
            continue

        try:
            m_id = int(m_id)
            n = int(num or 1)
        except (ValueError, TypeError):
            messages.info(request, "Material yoki son noto‘g‘ri kiritilgan.")
            return redirect(back_url)

        if n <= 0:
            messages.info(request, "Material soni 0 yoki manfiy bo‘lishi mumkin emas.")
            return redirect(back_url)

        # Bir xil material formda 2 marta kelib qolsa oldini olamiz
        if m_id in seen_materials:
            messages.info(request, "Bir xil materialni bir necha marta kiritmang.")
            return redirect(back_url)

        seen_materials.add(m_id)
        pairs.append((m_id, n))

    # 6) Orderga texnika saqlaymiz
    order.technics_id = technics_id
    order.save(update_fields=["technics_id", "date_edit"])

    # 7) Material tanlanmagan bo‘lsa ham finished qilamiz
    if not pairs:
        order.status = "finished"
        order.save(update_fields=["status", "date_edit"])
        messages.success(request, "Ariza yakunlandi!")
        return redirect(back_url)

    material_id_list = [m_id for m_id, _ in pairs]

    # 8) Deadlock bo‘lmasligi uchun materiallarni bir xil tartibda lock qilamiz
    materials = list(
        Material.objects
        .select_for_update()
        .filter(id__in=material_id_list, is_active=True)
        .order_by("id")
    )

    materials_map = {m.id: m for m in materials}

    # 9) Avval hamma material yetarliligini tekshirib chiqamiz
    for m_id, n in pairs:
        material = materials_map.get(m_id)
        if not material:
            messages.info(request, "Material topilmadi yoki faol emas.")
            return redirect(back_url)

        current_number = material.number or 0
        if current_number < n:
            messages.info(
                request,
                f'"{material.name}" yetarli emas. Omborda {current_number} dona bor.'
            )
            return redirect(back_url)

    # 10) Hammasi joyida bo‘lsa, keyin yozamiz va kamaytiramiz
    order_materials = []
    for m_id, n in pairs:
        material = materials_map[m_id]

        order_materials.append(
            OrderMaterial(
                order=order,
                material=material,
                number=n
            )
        )

        Material.objects.filter(pk=material.pk).update(number=F("number") - n)

    OrderMaterial.objects.bulk_create(order_materials)

    # 11) Oxirida orderni finished qilamiz
    order.status = "finished"
    order.save(update_fields=["status", "date_edit"])

    messages.success(request, "Ariza muvaffaqiyatli yakunlandi!")
    return redirect(back_url)


@never_cache
@require_GET
@login_required
@role_required("order")
def order_receiver_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    if employee.rol.client:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    orders_qs = (
        Order.objects
        .filter(receiver=employee,organization_id=4,status__in=["approved", "accepted", "canceled", "rejected",],)
        .select_related("goal", "organization", "receiver", "sender")
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
@require_GET
@login_required
@role_required("order")
def order_receiver_deed(request, pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    if employee.rol.client:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    order = get_object_or_404(
        Order.objects.select_related(
            "sender","sender__organization","sender__department","receiver",),
        pk=pk,
    )

    if order.receiver_id != employee.id:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    my_dep_id = employee.department_id

    emp_bos = (
        Employee.objects
        .filter(organization=order.sender.organization,rol__boss=True,)
        .select_related("organization")
    )

    employees = (
        Employee.objects
        .filter(Q(department=order.sender.department) | Q(department_id=my_dep_id))
        .select_related("organization")
        .distinct()
    )

    context = {
        "order": order,
        "emp_bos": emp_bos,
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
        raise PermissionDenied("Employee yo‘q")

    if employee.rol.client:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    # formdan keladiganlar
    sender_id = (request.POST.get("sender") or "").strip()
    message = (request.POST.get("message") or "").strip() or None
    agreements = request.POST.getlist("agreements[]")
    body = request.POST.get("body") or ""

    # sender obyekt
    sender = Employee.objects.filter(id=sender_id).first() if sender_id.isdigit() else None
    if not sender:
        messages.info(request, "Imzolovchi xodim tanlanmadi")
        return redirect("akt_get")

    if not body.strip():
        messages.info(request, "Hujjat matni (body) bo‘sh bo‘lmasin")
        return redirect("akt_get")

    # ✅ Deed yaratamiz
    deed = Deed.objects.create(
        sender_id=sender.id,  # FK obyekt
        user_id=employee.id,  # FK obyekt
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
        messages.info(request, f"PDF yaratilmadi: {e}")

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
@require_GET
@login_required
def order_sender_all(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    if not employee.rol.client:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    orders_qs = (
        Order.objects
        .filter(sender=employee,organization=employee.organization,status__in=["viewed", "process", "finished", "approved"],)
        .select_related("goal", "receiver", "sender")
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

    if not employee.rol.client:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    back_url = request.META.get("HTTP_REFERER") or "order_sender_all"

    goal_id = (request.POST.get("goal") or "").strip()
    body = (request.POST.get("body") or "").strip()

    if not goal_id.isdigit():
        messages.info(request, "Ariza turi tanlanmadi yoki noto‘g‘ri.")
        return redirect("order_sender_all")

    goal = get_object_or_404(
        Goal, id=int(goal_id),
        organization_id=employee.organization.id
    )

    Order.objects.create(
        organization_id=employee.organization_id,
        sender_id=employee.id,
        goal_id=goal.id,
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

    if not employee.rol.client:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    back_url = request.META.get("HTTP_REFERER", "/")
    action = (request.POST.get("action") or "").strip()

    if action not in {"canceled", "accepted"}:
        messages.warning(request, "Noma’lum amal!")
        return redirect(back_url)

    try:
        with transaction.atomic():
            order = get_object_or_404(
                Order.objects.select_for_update(),
                pk=pk,
            )

            if not order:
                messages.info(request, "Ariza topilmadi!")
                return redirect(back_url)

            if order.sender_id != employee.id:
                messages.info(request, "Ariza sizga tegishli emas.")
                return redirect(back_url)

            if action == "canceled":
                # Faqat hali yakuniy bosqichga o'tmagan arizani bekor qilish
                if order.status in {"accepted", "approved", "canceled", "rejected"}:
                    messages.info(request, "Bu ariza bo‘yicha amal bajarilgan.")
                    return redirect(back_url)

                order.status = "canceled"
                order.save(update_fields=["status", "date_edit"])
                messages.success(request, "Ariza bekor qilindi!")
                return redirect(back_url)

            if action == "accepted":
                # Client faqat approved bo'lgan arizani yakuniy qabul qiladi
                if order.status != "approved":
                    messages.info(request, "Bu ariza hozir qabul qilinmaydi.")
                    return redirect(back_url)

                order.status = "accepted"
                order.save(update_fields=["status", "date_edit"])
                messages.success(
                    request,
                    "Ariza yakunlandi, materiallarni ombordan olishingiz mumkin."
                )
                return redirect(back_url)

    except DatabaseError:
        messages.info(request, "Xatolik yuz berdi. Qayta urinib ko‘ring.")
        return redirect(back_url)

    messages.info(request, "Amal bajarilmadi.")
    return redirect(back_url)


# arizalar arxivi
@never_cache
@require_GET
@login_required
def order_sender_arxiv_all(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    if not employee.rol.client:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    orders_qs = (
        Order.objects
        .filter(sender=employee,organization=employee.organization,status__in=["accepted", "canceled", "rejected",],)
        .select_related("goal", "organization", "receiver", "sender")
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
    return render(request, "main/order_sender_arxiv_all.html", context)


@never_cache
@require_GET
@login_required
@role_required("order")
def order_receiver_all(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    if not employee.rol.client:
        raise PermissionDenied("Sizga ruxsat yo‘q")

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

    if not employee.rol.client:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    back_url = request.META.get("HTTP_REFERER") or "/"
    action = (request.POST.get("action") or "").strip()

    if action not in {"process", "rejected"}:
        messages.info(request, "Noto‘g‘ri amal tanlandi.")
        return redirect(back_url)

    try:
        with transaction.atomic():
            order = (
                Order.objects
                .select_for_update()
                .filter(
                    pk=pk,
                    sender_id=employee.id,
                    organization_id=employee.organization_id,
                    status="viewed",
                )
                .first()
            )

            if not order:
                messages.info(request, "Ariza topilmadi yoki allaqachon ko‘rib chiqilgan.")
                return redirect(back_url)

            if action == "process":
                order.status = "process"
                order.save(update_fields=["status", "date_edit"])
                messages.success(request, "Ariza qabul qilindi.")
                return redirect("order_receiver_activ_all")

            order.status = "rejected"
            order.save(update_fields=["status", "date_edit"])
            messages.success(request, "Ariza rad etildi.")
            return redirect(back_url)

    except DatabaseError:
        messages.error(request, "Xatolik yuz berdi. Qayta urinib ko‘ring.")
        return redirect(back_url)


@never_cache
@require_GET
@login_required
@role_required("order")
def order_receiver_activ_all(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    if not employee.rol.client:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    orders_qs = (
        Order.objects
        .filter(receiver=employee, organization=employee.organization, status__in=["process", "finished"])
        .select_related("goal", "organization", "receiver", "sender")
        .order_by("-id")
    )

    materials = Material.objects.filter(
        organization_id=employee.organization.id,
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

    if not employee.rol.client:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    order_id = request.POST.get("order_id")
    material_ids = request.POST.getlist("material_id[]")
    numbers = request.POST.getlist("number[]")

    order = get_object_or_404(
        Order.objects.select_for_update(),
        id=order_id,
    )

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
@require_GET
@login_required
@role_required("order")
def order_receiver_arxiv_all(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    if not employee.rol.client:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    orders_qs = (
        Order.objects
        .filter(receiver=employee,organization=employee.organization,status__in=["approved", "accepted", "canceled", "rejected",],)
        .select_related("goal", "organization", "receiver", "sender")
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
@require_GET
@login_required
@role_required("confirm")
def order_agrement(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    if not employee.rol.client:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    orders_qs = (
        Order.objects
        .filter(receiver__region=employee.region,organization=employee.organization, status__in=["finished"])
        .select_related("goal", "organization", "receiver", "sender")
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
def order_agrement_material(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    if not employee.rol.client:
        raise PermissionDenied("Sizga ruxsat yo‘q")

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
@require_GET
@login_required
@role_required("confirm")
def order_agrement_arxiv(request):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    if not employee.rol.client:
        raise PermissionDenied("Sizga ruxsat yo‘q")

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
@require_GET
@login_required
@role_required("confirm")
def order_agrement_deed(request,pk):
    employee = getattr(request.user, "employee", None)
    if not employee:
        raise PermissionDenied("Employee yo‘q")

    if not employee.rol.client:
        raise PermissionDenied("Sizga ruxsat yo‘q")

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


    if not employee.rol.client:
        raise PermissionDenied("Sizga ruxsat yo‘q")

    # formdan keladiganlar
    sender_id = (request.POST.get("sender") or "").strip()
    message = (request.POST.get("message") or "").strip() or None
    agreements = request.POST.getlist("agreements[]")
    body = request.POST.get("body") or ""

    # sender obyekt
    sender = Employee.objects.filter(id=sender_id).first() if sender_id.isdigit() else None
    if not sender:
        messages.info(request, "Imzolovchi xodim tanlanmadi")
        return redirect("akt_get")

    if not body.strip():
        messages.info(request, "Hujjat matni (body) bo‘sh bo‘lmasin")
        return redirect("akt_get")

    # ✅ Deed yaratamiz
    deed = Deed.objects.create(
        sender_id=sender.id,  # FK obyekt
        user_id=employee.id,  # FK obyekt
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