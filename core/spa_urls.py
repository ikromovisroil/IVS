"""
Bildirishnoma manzillari: serverda saqlangan eski sayt yo'llari → yangi interfeys (/app/...) sahifalari.

Brauzer push (Web Push) bosilganda foydalanuvchi shu manzilga o'tadi. Android (FCM) va bildirishnomalar markazi
eski yo'lni o'zgarishsiz oladi (ularni o'zlari moslaydi).
"""
from django.conf import settings

SPA_PATHS = {
    "/": "",
    "/order/sender/": "orders",
    "/order/receiver/": "orders/execute",
    "/contact/user/": "messages",
    "/contact/agrement/": "messages/agree",
    "/chat/": "chat",
    "/chat/meetings/": "meetings",
    "/files/": "files",
    "/notifications/": "notifications",
}


def spa_url(url):
    """Eski sayt yo'li (yoki allaqachon /app/... yo'li) → yangi interfeys yo'li; noma'lum bo'lsa bosh sahifa."""
    base = settings.SPA_URL                       # "/app/"
    url = (url or "/").strip()
    if url.startswith(base) and not url.startswith("//"):
        return url
    path = url.split("?", 1)[0].split("#", 1)[0]
    return base + SPA_PATHS.get(path, "")
