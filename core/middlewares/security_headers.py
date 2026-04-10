# core/middlewares/security_headers.py

class SecurityHeadersMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Restrict powerful browser features
        response["Permissions-Policy"] = (
            "accelerometer=(), "
            "autoplay=(), "
            "camera=(), "
            "display-capture=(), "
            "encrypted-media=(), "
            "fullscreen=(self), "
            "geolocation=(), "
            "gyroscope=(), "
            "magnetometer=(), "
            "microphone=(), "
            "midi=(), "
            "payment=(), "
            "publickey-credentials-get=(self), "
            "usb=(), "
            "web-share=(self), "
            "xr-spatial-tracking=()"
        )

        csp = (
            "default-src 'self'; "
            "base-uri 'self'; "
            "object-src 'none'; "
            "frame-ancestors 'none'; "
            "form-action 'self'; "
            "img-src 'self' data: blob: https:; "
            "font-src 'self' data: https:; "
            "style-src 'self' 'unsafe-inline' https:; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https:; "
            "connect-src 'self' https: wss:; "
            "media-src 'self' blob: https:; "
            "worker-src 'self' blob:; "
            "manifest-src 'self'; "
            "frame-src 'self' https:;"
        )
        response["Content-Security-Policy"] = csp

        # Helpful extra hardening headers
        response["X-Permitted-Cross-Domain-Policies"] = "none"

        # Disable FLoC / similar cohorting
        response["Permissions-Policy"] += ", browsing-topics=()"

        return response