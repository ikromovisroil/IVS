"""
WebSocket uchun JWT autentifikatsiya (Android): ws://.../ws/chat/?token=<access>

Token berilmasa — odatdagi sessiya (sayt) autentifikatsiyasi saqlanadi. Token yaroqsiz/eskirgan bo'lsa
foydalanuvchi anonim bo'ladi va ulanish 4401 kodi bilan yopiladi (ilova tokenni yangilab qayta ulanishi kerak).
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser


@database_sync_to_async
def _user_from_token(raw_token):
    from rest_framework_simplejwt.exceptions import TokenError
    from rest_framework_simplejwt.tokens import AccessToken

    try:
        token = AccessToken(raw_token)
        user = get_user_model().objects.get(pk=token["user_id"])
    except (TokenError, KeyError, get_user_model().DoesNotExist):
        return AnonymousUser()
    return user if user.is_active else AnonymousUser()


class JWTQueryAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query = parse_qs((scope.get("query_string") or b"").decode())
        token = (query.get("token") or [None])[0]
        if token:
            scope = dict(scope)
            scope["user"] = await _user_from_token(token)
        return await super().__call__(scope, receive, send)
