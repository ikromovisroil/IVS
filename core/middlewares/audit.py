from core.models import AuditLog

class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # faqat login bo‘lgan userlar
        if request.user.is_authenticated:

            # faqat real harakatlar (shovqinni kamaytirish)
            if request.method in ["POST", "PUT", "PATCH", "DELETE"]:

                AuditLog.objects.create(
                    employee=getattr(request.user, "employee", None),
                    action=self.get_action(request.method),
                    model="HTTP",
                    object_id=None,
                    path=request.path,
                    method=request.method,
                    ip=self.get_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
                    description=f"{request.method} {request.path}",
                )

        return response

    def get_ip(self, request):
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0]
        return request.META.get("REMOTE_ADDR")

    def get_action(self, method):
        return {
            "POST": "create",
            "PUT": "update",
            "PATCH": "update",
            "DELETE": "delete",
        }.get(method, "view")
