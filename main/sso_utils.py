import base64
import json
from urllib.parse import urlencode
from django.conf import settings


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def decode_jwt(token: str) -> dict:
    try:
        payload  = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


def sync_employee_from_claims(employee, claims: dict) -> None:
    """
    OneID id_token dagi shaxsiy ma'lumotni xodimga yozadi: birth_date, doc_serial_number (pasport), phone_number.
    Faqat BO'SH maydonlar to'ldiriladi (mavjud qiymat o'zgarmaydi). Noto'g'ri qiymat yozilmaydi.
    Xato kirishga to'sqinlik qilmaydi.
    """
    import logging
    import re
    from datetime import date

    try:
        changed = []

        raw_birth = str(claims.get("birth_date") or "").strip()[:10]
        if raw_birth:
            try:
                birth = date.fromisoformat(raw_birth)
            except ValueError:
                birth = None
            if birth and not employee.birth_date:
                employee.birth_date = birth
                changed.append("birth_date")

        passport = str(claims.get("doc_serial_number") or "").strip().upper()
        if re.fullmatch(r"[A-Z]{2}[0-9]{7}", passport) and not employee.passport:
            employee.passport = passport
            changed.append("passport")

        phone = str(claims.get("phone_number") or "").strip()[:50]
        if phone and not employee.sso_phone:
            employee.sso_phone = phone
            changed.append("sso_phone")

        if changed:
            employee.save(update_fields=changed)
    except Exception:
        logging.getLogger(__name__).exception("OneID ma'lumotini xodimga yozib bo'lmadi (employee=%s)", getattr(employee, "pk", None))


def _get_base_url(request, local_path: str, settings_key: str) -> str:
    host = request.get_host()
    if "localhost" in host or "127.0.0.1" in host:
        return f"http://localhost:8000{local_path}"
    return getattr(settings, settings_key, "") or f"https://report.yatm.uz{local_path}"


def get_sso_redirect_uri(request) -> str:
    return _get_base_url(request, "/sso/callback/", "SSO_REDIRECT_URI")


def get_eimzo_return_uri(request) -> str:
    return _get_base_url(request, "/sso/eimzo-return/", "EIMZO_RETURN_URL")


def build_eimzo_sign_url(request, doc_value: str) -> str:
    params = {
        "redirectUri": get_eimzo_return_uri(request),
        "doc":         doc_value,
    }
    return f"{settings.SSO_EIMZO_SIGN_URL}?{urlencode(params)}"