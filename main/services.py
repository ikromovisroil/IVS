import base64
import requests

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from main.models import Employee

User = get_user_model()


def exchange_code_for_token(code: str, code_verifier: str, redirect_uri: str) -> dict:
    """
    OneID authorization_code → token (PKCE)
    """
    if not all([code, code_verifier, redirect_uri]):
        raise PermissionDenied("SSO ma'lumotlari to‘liq emas")

    auth = base64.b64encode(
        f"{settings.SSO_CLIENT_ID}:{settings.SSO_CLIENT_SECRET}".encode("utf-8")
    ).decode("utf-8")

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
    }

    try:
        response = requests.post(
            settings.SSO_TOKEN_URL,
            data=data,
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=10,
        )
    except requests.RequestException:
        raise PermissionDenied("SSO server bilan aloqa yo‘q")

    if response.status_code != 200:
        raise PermissionDenied("SSO token olinmadi")

    return response.json()
