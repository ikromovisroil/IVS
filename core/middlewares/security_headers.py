# core/middlewares/security_headers.py

class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

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
            "xr-spatial-tracking=(), "
            "browsing-topics=()"
        )

        response["Content-Security-Policy"] = (
            "default-src 'self'; "
            "base-uri 'self'; "
            "object-src 'none'; "
            "frame-ancestors 'self'; "
            "form-action 'self' https://sso.mf.uz; "
            "img-src 'self' data: blob: https:; "
            "font-src 'self' data: https:; "
            "style-src 'self' 'unsafe-inline' https:; "
            "script-src 'self' 'unsafe-inline' https:; "
            "connect-src 'self' https://sso.mf.uz https: wss:; "
            "media-src 'self' blob: https:; "
            "worker-src 'self' blob:; "
            "manifest-src 'self'; "
            "frame-src 'self' https://sso.mf.uz https:;"
        )

        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["X-Permitted-Cross-Domain-Policies"] = "none"

        return response