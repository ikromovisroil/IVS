import logging
import requests

from django.conf import settings
from django.core.cache import cache


logger = logging.getLogger(__name__)


class GatewayError(Exception):
    pass


class GatewayClient:
    TOKEN_CACHE_KEY = "gateway_access_token"
    REFRESH_CACHE_KEY = "gateway_refresh_token"

    TOKEN_URL = "/api/v1/auth/token"
    CURRENT_CITIZEN_URL = "/api/v1/egov/current-citizen"

    @classmethod
    def _base_url(cls):
        base_url = getattr(settings, "GATEWAY_BASE_URL", "").rstrip("/")
        if not base_url:
            raise GatewayError("GATEWAY_BASE_URL settings.py da topilmadi")
        return base_url

    @classmethod
    def _post(cls, url, payload, headers=None):
        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers or {
                    "Content-Type": "application/json",
                    "Accept": "*/*",
                },
                timeout=30,
            )
            return response
        except requests.RequestException as e:
            logger.exception("Gateway request error")
            raise GatewayError(f"Gateway bilan aloqa xatosi: {e}")

    @classmethod
    def get_token(cls):
        access_token = cache.get(cls.TOKEN_CACHE_KEY)
        if access_token:
            return access_token

        url = cls._base_url() + cls.TOKEN_URL

        payload = {
            "grant_type": "password",
            "username": settings.GATEWAY_USERNAME,
            "password": settings.GATEWAY_PASSWORD,
            "refresh_token": None,
        }

        response = cls._post(url, payload)

        if response.status_code != 200:
            raise GatewayError(
                f"Token olishda xato: {response.status_code} | {response.text}"
            )

        data = response.json()

        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        expires_in = int(data.get("expires_in", 3600000)) // 1000

        if not access_token:
            raise GatewayError("Gateway access_token qaytarmadi")

        cache.set(cls.TOKEN_CACHE_KEY, access_token, max(expires_in - 60, 60))

        if refresh_token:
            cache.set(cls.REFRESH_CACHE_KEY, refresh_token, 7 * 24 * 60 * 60)

        return access_token

    @classmethod
    def refresh_token(cls):
        refresh_token = cache.get(cls.REFRESH_CACHE_KEY)

        if not refresh_token:
            cache.delete(cls.TOKEN_CACHE_KEY)
            return cls.get_token()

        url = cls._base_url() + cls.TOKEN_URL

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        response = cls._post(url, payload)

        if response.status_code != 200:
            cache.delete(cls.TOKEN_CACHE_KEY)
            cache.delete(cls.REFRESH_CACHE_KEY)
            return cls.get_token()

        data = response.json()

        access_token = data.get("access_token")
        new_refresh_token = data.get("refresh_token")
        expires_in = int(data.get("expires_in", 3600000)) // 1000

        if not access_token:
            cache.delete(cls.TOKEN_CACHE_KEY)
            return cls.get_token()

        cache.set(cls.TOKEN_CACHE_KEY, access_token, max(expires_in - 60, 60))

        if new_refresh_token:
            cache.set(cls.REFRESH_CACHE_KEY, new_refresh_token, 7 * 24 * 60 * 60)

        return access_token

    @classmethod
    def current_citizen(cls, pinfl):
        if not pinfl:
            raise GatewayError("PINFL bo‘sh bo‘lishi mumkin emas")

        token = cls.get_token()

        url = cls._base_url() + cls.CURRENT_CITIZEN_URL

        headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Authorization": f"Bearer {token}",
        }

        payload = {
            "pinfl": str(pinfl),
        }

        response = cls._post(url, payload, headers=headers)

        if response.status_code == 401:
            token = cls.refresh_token()
            headers["Authorization"] = f"Bearer {token}"
            response = cls._post(url, payload, headers=headers)

        if response.status_code != 200:
            raise GatewayError(
                f"Current citizen xatosi: {response.status_code} | {response.text}"
            )

        try:
            return response.json()
        except ValueError:
            raise GatewayError("Gateway JSON formatda javob qaytarmadi")