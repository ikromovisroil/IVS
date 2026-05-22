import base64
import json
import logging
import secrets
import requests
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from django.db import transaction
from django.utils import timezone
from django.core.files.base import ContentFile
import string
from .sso_utils import *
from .utils import *
from .html_pdf import *
from .models import *

logger = logging.getLogger(__name__)


# -----------------------
# 1) Login page
# -----------------------
def login_page(request):
    return render(request, "users/login.html")


# -----------------------
# 2) Start flow
# -----------------------
@never_cache
def sso_start_login(request):
    # Login uchun umumiy SSO sahifa chiqadi
    request.session["SSO_FLOW"] = {"purpose": "login"}
    request.session.modified = True
    return redirect("sso_start")


@never_cache
@login_required
def sso_start_approve(request):
    """
    Approve uchun umumiy SSO sahifaga emas,
    to'g'ridan-to'g'ri E-IMZO sign endpointga yuboramiz.
    """
    pending = request.session.get("PENDING_APPROVE")
    if not pending:
        messages.info(request, "Tasdiqlash topilmadi")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    role = pending.get("role")
    redirect_url = pending.get("redirect_url") or "/"

    # request.user login bo'lgan bo'lishi kerak
    req_emp = getattr(request.user, "employee", None)
    if not req_emp:
        messages.error(request, "Employee topilmadi")
        return redirect(redirect_url)

    # doc qiymatini aniq va tekshiriladigan qilib yasaymiz
    if role in ("sender", "receiver"):
        deed_id = pending.get("deed_id")
        if not deed_id:
            messages.error(request, "Deed topilmadi")
            return redirect(redirect_url)

        doc_value = f"deed-{deed_id}-{role}-{req_emp.id}"

    elif role == "consent":
        consent_id = pending.get("consent_id")
        if not consent_id:
            messages.error(request, "Consent topilmadi")
            return redirect(redirect_url)

        doc_value = f"consent-{consent_id}-{req_emp.id}"

    else:
        messages.error(request, "Noto‘g‘ri approve turi")
        return redirect(redirect_url)

    request.session["PENDING_EIMZO"] = {
        "doc": doc_value,
        "redirect_url": redirect_url,
    }
    request.session.modified = True

    sign_url = build_eimzo_sign_url(request, doc_value)
    return redirect(sign_url)


# -----------------------
# 3) Login uchun PKCE + redirect page
# -----------------------
@never_cache
def sso_start(request):
    return render(request, "users/sso.html", {
        "client_id": settings.SSO_CLIENT_ID,
        "sso_auth_url": settings.SSO_AUTH_URL,
        "redirect_uri": get_sso_redirect_uri(request),
    })


# -----------------------
# 4) Login callback page
# -----------------------
@never_cache
def sso_callback(request):
    return render(request, "users/callback.html", {
        "redirect_uri": get_sso_redirect_uri(request),
    })


# -----------------------
# 5) Login exchange (faqat login uchun)
# -----------------------
@csrf_exempt
@never_cache
@require_POST
def sso_exchange(request):
    try:
        flow    = request.session.get("SSO_FLOW") or {}
        purpose = (flow.get("purpose") or "").strip()

        if purpose != "login":
            return JsonResponse(
                {"status": "error", "message": "Bu endpoint faqat login uchun", "redirect": "/sso/login/"},
                status=400
            )

        try:
            body = json.loads(request.body or "{}")
        except Exception:
            return JsonResponse(
                {"status": "error", "message": "JSON noto'g'ri", "redirect": "/sso/login/"},
                status=400
            )

        code          = (body.get("code")         or "").strip()
        code_verifier = (body.get("codeVerifier") or "").strip()
        redirect_uri  = (body.get("redirectUri")  or "").strip()

        if not code or not code_verifier or not redirect_uri:
            return JsonResponse(
                {"status": "error", "message": "SSO parametrlari to'liq emas", "redirect": "/sso/login/"},
                status=400
            )

        token_data = exchange_code_for_token(code, code_verifier, redirect_uri) or {}
        id_token   = token_data.get("id_token")
        if not id_token:
            raise PermissionDenied("id_token kelmadi")

        user_data = decode_jwt(id_token) or {}
        sso_pinfl = str(user_data.get("pinfl") or "").strip()
        if not sso_pinfl:
            raise PermissionDenied("SSO token ichida pinfl topilmadi")

        employee = Employee.objects.select_related(
            "user", "organization"
        ).filter(pinfl=sso_pinfl).first()

        if not employee or not employee.user:
            try:
                from .gateway import GatewayClient

                gateway_data = GatewayClient.current_citizen(sso_pinfl)
                result       = gateway_data.get("result") or {}
                positions    = result.get("positions") or []

                if not positions:
                    return JsonResponse(
                        {"status": "forbidden", "message": "Gatewayda ish joyi topilmadi", "redirect": "/sso/login/"},
                        status=403
                    )

                dep_ids = [
                    str(pos.get("dep_id") or "").strip()
                    for pos in positions
                    if pos.get("dep_id")
                ]

                if not dep_ids:
                    return JsonResponse(
                        {"status": "forbidden", "message": "Pozitsiyalarda dep_id topilmadi", "redirect": "/sso/login/"},
                        status=403
                    )

                base_username = f"{result.get('name', '')}.{result.get('surname', '')}".lower()

                with transaction.atomic():
                    username = base_username
                    counter  = 1
                    while User.objects.filter(username=username).exists():
                        username = f"{base_username}{counter}"
                        counter += 1

                    user = User.objects.create_user(
                        username=username,
                        password=secrets.token_urlsafe(16),
                    )

                    # Avval employee olamiz, keyin fieldlarni to'ldiramiz
                    employee             = user.employee
                    employee.pinfl       = sso_pinfl
                    employee.first_name  = (result.get("name")       or "").strip()
                    employee.last_name   = (result.get("surname")    or "").strip()
                    employee.father_name = (result.get("partonimic") or "").strip()

                    # dep_id bo'yicha Department / Directorate / Division topamiz
                    for dep_id in dep_ids:
                        department = Department.objects.filter(code=dep_id).first()
                        if department:
                            employee.department = department
                            break

                        directorate = Directorate.objects.filter(code=dep_id).first()
                        if directorate:
                            employee.directorate = directorate
                            break

                        division = Division.objects.filter(code=dep_id).first()
                        if division:
                            employee.division = division
                            break

                    employee.save()

                    rol, _ = Rol.objects.get_or_create(employee=employee)
                    rol.save()

            except Exception as gateway_error:
                logger.exception("Gateway yoki user yaratishda xatolik")
                return JsonResponse(
                    {"status": "forbidden", "message": str(gateway_error), "redirect": "/sso/login/"},
                    status=403
                )

        # --- Umumiy tekshiruvlar (yangi va mavjud user uchun ham) ---

        if not employee or not employee.user:
            return JsonResponse(
                {"status": "error", "message": "Foydalanuvchi aniqlanmadi", "redirect": "/sso/login/"},
                status=500
            )

        if not employee.user.is_active:
            return JsonResponse(
                {"status": "forbidden", "message": "Foydalanuvchi bloklangan", "redirect": "/sso/login/"},
                status=403
            )

        auth_login(request, employee.user)
        request.session.pop("SSO_FLOW", None)
        request.session.modified = True
        return JsonResponse({"status": "ok", "redirect": "/profil/"}, status=200)

    except PermissionDenied as e:
        return JsonResponse({"status": "error", "message": str(e), "redirect": "/sso/login/"}, status=403)
    except Exception as e:
        logger.exception("SSO ERROR")
        return JsonResponse({"status": "error", "message": f"SSO xatolik: {e}", "redirect": "/sso/login/"}, status=500)


# -----------------------
# 6) E-IMZO return (approve uchun)
# -----------------------
@never_cache
@login_required
def eimzo_return(request):
    pending       = request.session.get("PENDING_APPROVE")
    pending_eimzo = request.session.get("PENDING_EIMZO")

    def clear_session():
        request.session.pop("PENDING_APPROVE", None)
        request.session.pop("PENDING_EIMZO", None)
        request.session.pop("SSO_FLOW", None)
        request.session.modified = True

    try:
        if not pending or not pending_eimzo:
            messages.info(request, "Imzolash sessiyasi topilmadi")
            return redirect("/")

        returned_doc = (request.GET.get("doc") or "").strip()
        sent_doc     = (pending_eimzo.get("doc") or "").strip()

        if returned_doc and sent_doc and returned_doc != sent_doc:
            messages.info(request, "Imzolash hujjati mos emas")
            return redirect(pending_eimzo.get("redirect_url") or "/")

        role         = pending.get("role")
        message      = (pending.get("message") or "").strip()
        redirect_url = pending.get("redirect_url") or "/"

        req_emp = getattr(request.user, "employee", None)
        if not req_emp:
            messages.info(request, "Employee yo'q")
            return redirect(redirect_url)

        # ---- sender/receiver approve ----
        if role in ("sender", "receiver"):
            deed_id = pending.get("deed_id")
            if not deed_id:
                raise PermissionDenied("Deed yo'q")

            approver_name = getattr(req_emp, "full_name", None) or str(req_emp)

            with transaction.atomic():
                deed = Deed.objects.select_for_update().get(pk=int(deed_id))

                if role == "sender" and deed.sender_id != req_emp.id:
                    raise PermissionDenied("Sender emassiz")
                if role == "receiver" and deed.receiver_id != req_emp.id:
                    raise PermissionDenied("Receiver emassiz")

                now = timezone.now()

                if role == "sender":
                    if deed.status_sender != "approved":
                        deed.status_sender  = "approved"
                        deed.message_sender = message or ""
                        deed.date_sender    = now
                        deed.save(update_fields=["status_sender", "message_sender", "date_sender"])
                else:
                    if deed.status_receiver != "approved":
                        deed.status_receiver  = "approved"
                        deed.message_receiver = message or ""
                        deed.date_receiver    = now
                        deed.save(update_fields=["status_receiver", "message_receiver", "date_receiver"])

                is_final = (
                    (deed.receiver_id is None and deed.status_sender == "approved")
                    or (
                        deed.receiver_id is not None
                        and deed.status_sender == "approved"
                        and deed.status_receiver == "approved"
                    )
                )
                deed_pk = deed.pk

            if is_final:
                try:
                    deed      = Deed.objects.get(pk=deed_pk)
                    pdf_bytes = deed_to_pdf_bytes(deed)

                    if deed.file:
                        deed.file.delete(save=False)

                    pdf_name = f"akt_{timezone.now().strftime('%Y%m%d')}_{secrets.token_urlsafe(6)}.pdf"
                    deed.file.save(pdf_name, ContentFile(pdf_bytes), save=True)

                    sign_pdf_inplace(
                        pdf_path=deed.file.path,
                        request=request,
                        approver_name=approver_name,
                        deed_id=deed.pk,
                    )
                    messages.success(request, "Hujjat muvaffaqiyatli imzolandi")

                except HtmlPdfError as e:
                    messages.info(request, f"PDF yaratilmadi: {e}")
                    return redirect(redirect_url)
                except TimeoutError as e:
                    messages.info(request, str(e))
                    return redirect(redirect_url)
                except Exception:
                    logger.exception("PDF rebuild/sign error")
                    messages.info(request, "PDF imzolashda xatolik")
                    return redirect(redirect_url)

            clear_session()
            return redirect(redirect_url)

        # ---- consent approve ----
        if role == "consent":
            consent_id = pending.get("consent_id")
            if not consent_id:
                raise PermissionDenied("consent_id yo'q")

            consent = get_object_or_404(
                DeedConsent.objects.select_related("employee__user"),
                pk=int(consent_id)
            )

            if consent.employee.user_id != request.user.id:
                raise PermissionDenied("Ruxsat yo'q")

            if consent.status != "approved":
                consent.status  = "approved"
                consent.message = message or ""
                consent.save(update_fields=["status", "message"])

            clear_session()
            messages.success(request, "Kelishuv muvaffaqiyatli tasdiqlandi")
            return redirect(redirect_url)

        raise PermissionDenied("Noto'g'ri pending turi")

    except PermissionDenied as e:
        messages.info(request, str(e))
        return redirect("/")
    except Exception as e:
        logger.exception("E-IMZO RETURN ERROR")
        messages.info(request, f"E-IMZO xatolik: {e}")
        return redirect("/")
    finally:
        clear_session()


def exchange_code_for_token(code: str, code_verifier: str, redirect_uri: str) -> dict:
    auth = base64.b64encode(
        f"{settings.SSO_CLIENT_ID}:{settings.SSO_CLIENT_SECRET}".encode()
    ).decode()

    data = {
        "grant_type":    "authorization_code",
        "code":          code,
        "code_verifier": code_verifier,
        "redirect_uri":  redirect_uri,
    }

    try:
        r = requests.post(
            settings.SSO_TOKEN_URL,
            data=data,
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type":  "application/x-www-form-urlencoded",
            },
            timeout=20,
        )
    except requests.exceptions.RequestException as e:
        raise PermissionDenied(f"SSO ga ulanishda xatolik: {e}")

    if r.status_code != 200:
        raise PermissionDenied(f"SSO token olinmadi: {r.status_code} {r.text[:200]}")

    try:
        return r.json()
    except ValueError:
        raise PermissionDenied("SSO javob JSON emas")


@never_cache
@login_required
def logout(request):
    auth_logout(request)
    return redirect("/sso/login/")