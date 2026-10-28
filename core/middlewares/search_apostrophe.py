"""Qidiruvda foydalanuvchi o' / g' ni oddiy apostrof bilan yozsa ham, bazadagi o‘ / g‘ topilsin (saqlashda shunday tuzatiladi)."""
from main.uz_text import normalize_og

KEYS = ("search", "q", "name")


class SearchApostropheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "GET" and any(k in request.GET for k in KEYS):
            params = request.GET.copy()
            for key in KEYS:
                values = params.getlist(key)
                fixed = [normalize_og(v) for v in values]
                if fixed != values:
                    params.setlist(key, fixed)
                    request.GET = params
        return self.get_response(request)
