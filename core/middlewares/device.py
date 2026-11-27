"""Qurilma turini so'rovga biriktiradi va server xatosi (5xx) qaysi qurilma/versiyada chiqqanini logga yozadi."""
import logging

from core.device import detect_device, reset_current_device, set_current_device

logger = logging.getLogger(__name__)


class DeviceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        device, version = detect_device(request)
        request.device_type, request.app_version = device, version
        token = set_current_device((device, version))
        try:
            response = self.get_response(request)
        finally:
            reset_current_device(token)
        # 503 — texnik ishlar / o'chiq xizmat: xato emas
        if response.status_code >= 500 and response.status_code != 503:
            logger.error(
                "Server xatosi %s: %s %s | qurilma=%s versiya=%s",
                response.status_code, request.method, request.path, device or "-", version or "-",
            )
        return response
