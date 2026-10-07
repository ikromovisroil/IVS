"""
JWT autentifikatsiyasi + audit.

Saytdagi AuditMiddleware (core/middlewares/audit.py) faqat Django `request.user` (sessiya) bilan ishlaydi, shu sabab
JWT bilan kelgan API so'rovlari (yozuv amallari) audit jurnaliga tushmasdi. Bu sinf foydalanuvchini aniqlagach uni
Django so'roviga ham yozadi va signal-audit (core/signals) uchun joriy xodimni o'rnatadi.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.request_context import set_current_employee


class AuditJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            user, token = result
            request._request.user = user   # AuditMiddleware so'rov oxirida shuni ko'radi
            set_current_employee(getattr(user, "employee", None))
        return result
