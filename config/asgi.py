"""ASGI config for config project.

Bu fayl oddiy HTTP (Django) so'rovlarini va WebSocket (chat) ulanishlarini
bitta ASGI ilovasida birlashtiradi. Productionda `gunicorn config.wsgi` o'rniga
ASGI server (masalan `daphne config.asgi:application` yoki
`uvicorn config.asgi:application`) ishlatilishi kerak - aks holda WebSocket
(chat) ishlamaydi, oddiy sahifalar esa avvalgidek ishlayveradi.
"""

import os

import django
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter

from chat.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
