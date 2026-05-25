import base64
import hashlib
import json
import secrets
from urllib.parse import urlencode
from django.conf import settings


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def make_code_verifier() -> str:
    return secrets.token_urlsafe(64)[:128]


def make_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    return b64url(digest)


def decode_jwt(token: str) -> dict:
    try:
        payload  = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


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