# common/middleware/security_headers.py
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

def _origin_from(url: str | None, default: str = "") -> str:
    try:
        if not url:
            return default
        # Accept full URL and keep "<scheme>://<host[:port]>"
        from urllib.parse import urlparse
        u = urlparse(url)
        if u.scheme and u.netloc:
            return f"{u.scheme}://{u.netloc}"
        return default
    except Exception:
        return default

class ContentSecurityPolicyMiddleware(MiddlewareMixin):
    """
    Send CSP from backend for API responses only (avoid double-CSP on Next's HTML).
    If you must apply on HTML too, keep it compatible with Next (include blob: in default-src).
    """

    # Restrict to these path prefixes (tune for your project)
    API_PREFIXES = ("/api/", "/admin/")  # add others if needed
    APPLY_TO_HTML = False  # set True only if you intentionally want CSP on HTML from Django

    def process_response(self, request, response):
        path = (request.path or "")
        content_type = (response.headers.get("Content-Type") or response.get("Content-Type") or "").lower()
        is_html = "text/html" in content_type

        # Apply only to API/admin (non-HTML). Avoid touching Next's HTML on :3000.
        if not any(path.startswith(pfx) for pfx in self.API_PREFIXES):
            # Not an API path; skip unless explicitly allowed
            if is_html and not self.APPLY_TO_HTML:
                return response

        # Build dynamic origins (optional)
        BACKEND_ORIGIN = _origin_from(getattr(settings, "BACKEND_ORIGIN", ""), "")
        MEDIA_ORIGIN = _origin_from(getattr(settings, "AWS_PUBLIC_MEDIA_ORIGIN", ""), "https://townlit-media.s3.us-east-1.amazonaws.com")
        GOOGLE_FONTS_CSS = "https://fonts.googleapis.com"
        GOOGLE_FONTS_STATIC = "https://fonts.gstatic.com"

        # Useful S3 wildcards (for signed/non-regional hosts)
        S3_WILDCARDS = "https://*.s3.amazonaws.com https://*.s3.*.amazonaws.com"

        csp = "; ".join([
            # ✅ include blob: in default-src to avoid blob fallback errors
            "default-src 'self' blob:",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:",  # dev-friendly; tighten in prod
            f"style-src 'self' 'unsafe-inline' {GOOGLE_FONTS_CSS}",
            f"style-src-elem 'self' 'unsafe-inline' {GOOGLE_FONTS_CSS}",
            # Images/Media from self/data/blob + S3 + backend (add https: for dev convenience)
            f"img-src 'self' data: blob: {MEDIA_ORIGIN} {S3_WILDCARDS} {BACKEND_ORIGIN} https:",
            f"media-src 'self' data: blob: {MEDIA_ORIGIN} {S3_WILDCARDS} {BACKEND_ORIGIN} https:",
            f"font-src 'self' data: {GOOGLE_FONTS_STATIC} https:",
            # XHR/fetch/WebSocket
            f"connect-src 'self' blob: {MEDIA_ORIGIN} {BACKEND_ORIGIN} http: https: ws: wss:",
            "worker-src 'self' blob:",
            "frame-src 'self' blob:",
            "child-src 'self' blob:",
            "frame-ancestors 'self'",
            "object-src 'none'",
        ])

        response["Content-Security-Policy"] = csp
        response["X-Content-Type-Options"] = "nosniff"
        response["Referrer-Policy"] = "no-referrer"
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response
