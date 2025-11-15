# common/middleware/security_headers.py
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from urllib.parse import urlparse

def _origin_from(url: str | None, default: str = "") -> str:
    try:
        if not url:
            return default
        u = urlparse(url)
        if u.scheme and u.netloc:
            return f"{u.scheme}://{u.netloc}"
        return default
    except Exception:
        return default

class ContentSecurityPolicyMiddleware(MiddlewareMixin):
    """
    Send CSP from backend for API responses only.
    Do NOT apply CSP on Django Admin HTML to avoid CSRF 'Origin: null' issues.
    """
    API_PREFIXES = ("/api/",) 
    APPLY_TO_HTML = False

    def _set_common_security_headers(self, response):
        response.setdefault("X-Content-Type-Options", "nosniff")
        # اجازهٔ fallback امن برای CSRF:
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")

    def process_response(self, request, response):
        path = (request.path or "")
        content_type = (response.headers.get("Content-Type") or response.get("Content-Type") or "").lower()
        is_html = "text/html" in content_type

        # ⛔️ هرگز روی HTML ادمین CSP ست نکن
        if path.startswith("/admin/") and is_html:
            self._set_common_security_headers(response)
            return response

        # فقط روی API (و در صورت نیاز HTMLهای غیرادمین) اعمال شود
        if not any(path.startswith(pfx) for pfx in self.API_PREFIXES):
            if is_html and not self.APPLY_TO_HTML:
                self._set_common_security_headers(response)
                return response

        BACKEND_ORIGIN = _origin_from(getattr(settings, "BACKEND_ORIGIN", ""), "")
        MEDIA_ORIGIN = _origin_from(getattr(settings, "AWS_PUBLIC_MEDIA_ORIGIN", ""),
                                    "https://townlit-media.s3.us-east-1.amazonaws.com")
        GOOGLE_FONTS_CSS = "https://fonts.googleapis.com"
        GOOGLE_FONTS_STATIC = "https://fonts.gstatic.com"
        S3_WILDCARDS = "https://*.s3.amazonaws.com https://*.s3.*.amazonaws.com"

        csp = "; ".join([
            "default-src 'self' blob:",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:",  # در prod سفت‌ترش کن
            f"style-src 'self' 'unsafe-inline' {GOOGLE_FONTS_CSS}",
            f"style-src-elem 'self' 'unsafe-inline' {GOOGLE_FONTS_CSS}",
            f"img-src 'self' data: blob: {MEDIA_ORIGIN} {S3_WILDCARDS} {BACKEND_ORIGIN} https:",
            f"media-src 'self' data: blob: {MEDIA_ORIGIN} {S3_WILDCARDS} {BACKEND_ORIGIN} https:",
            f"font-src 'self' data: {GOOGLE_FONTS_STATIC} https:",
            f"connect-src 'self' blob: {MEDIA_ORIGIN} {BACKEND_ORIGIN} http: https: ws: wss:",
            "worker-src 'self' blob:",
            "frame-src 'self' blob:",
            "child-src 'self' blob:",
            "frame-ancestors 'self'",
            "object-src 'none'",
        ])

        response["Content-Security-Policy"] = csp
        self._set_common_security_headers(response)
        return response
