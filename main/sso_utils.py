import base64
import hashlib
import json
import secrets
from django.conf import settings

def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

def make_code_verifier() -> str:
    # RFC7636: 43..128
    return secrets.token_urlsafe(64)[:128]

def make_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    return b64url(digest)

def decode_jwt(token: str) -> dict:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))

def get_sso_redirect_uri(request) -> str:
    host = request.get_host()
    if "localhost" in host or "127.0.0.1" in host:
        return "http://localhost:8000/sso/callback/"
    return getattr(settings, "SSO_REDIRECT_URI", "https://report.imv.uz/sso/callback/")