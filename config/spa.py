"""
Yangi React interfeysi (frontend/) — /app/ ostida.

`npm run build` natijasi static/spa/ ga tushadi (collectstatic orqali STATIC_ROOT ga, WhiteNoise beradi);
bu view esa /app/ ostidagi har qanday yo'l uchun static/spa/index.html ni qaytaradi — marshrutni React o'zi hal qiladi.
"""
from functools import lru_cache

from django.conf import settings
from django.http import Http404, HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie

INDEX = settings.BASE_DIR / "static" / "spa" / "index.html"


@lru_cache(maxsize=1)
def _cached_index() -> str:
    return INDEX.read_text(encoding="utf-8")


def _index() -> str:
    # DEBUG da har safar o'qiladi (qayta build qilinsa server qayta ishga tushmasdan yangilanadi)
    return INDEX.read_text(encoding="utf-8") if settings.DEBUG else _cached_index()


@never_cache
def spa_service_worker(request):
    """
    Brauzer push service worker'i (frontend/public/sw.js). /app/ ostida beriladi, shuning uchun scope=/app/ bo'ladi;
    build qilingan bo'lsa static/spa/sw.js, aks holda (ishlab chiqarish) frontend/public/sw.js.
    """
    for path in (settings.BASE_DIR / "static" / "spa" / "sw.js", settings.BASE_DIR / "frontend" / "public" / "sw.js"):
        if path.exists():
            response = HttpResponse(path.read_text(encoding="utf-8"), content_type="application/javascript")
            response["Service-Worker-Allowed"] = "/app/"
            return response
    raise Http404("sw.js topilmadi")


@never_cache
@ensure_csrf_cookie  # SPA POST/PATCH so'rovlari csrftoken cookie'sini o'qiydi
def spa_index(request, path=""):
    if not INDEX.exists():
        raise Http404("Yangi interfeys build qilinmagan: cd frontend && npm run build")
    return HttpResponse(_index())
