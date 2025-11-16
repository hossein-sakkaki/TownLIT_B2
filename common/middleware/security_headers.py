# common/middleware/security_headers.py
from django.utils.deprecation import MiddlewareMixin

class ContentSecurityPolicyMiddleware(MiddlewareMixin):
    """
    Soft security headers only.
    CSP is REMOVED here because Next.js provides the unified CSP.
    This avoids conflicting CSP policies (avatar proxy + S3 + media).
    """

    # Only apply to API routes
    API_PREFIXES = ("/api/",)

    APPLY_TO_HTML = False  # don't touch HTML pages

    def _set_common_security_headers(self, response):
        # Prevent MIME sniffing
        response.setdefault("X-Content-Type-Options", "nosniff")

        # Secure referrer handling
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")

        # Privacy-safe permissions policy
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")

    def process_response(self, request, response):
        path = request.path or ""
        content_type = (
            response.headers.get("Content-Type")
            or response.get("Content-Type")
            or ""
        ).lower()

        is_html = "text/html" in content_type

        # ❌ 1) Never touch Django admin HTML
        if path.startswith("/admin/") and is_html:
            self._set_common_security_headers(response)
            return response

        # ❌ 2) Don't apply CSP to HTML pages (Next.js handles CSP)
        if is_html and not self.APPLY_TO_HTML:
            self._set_common_security_headers(response)
            return response

        # ❌ 3) ONLY add security headers for API responses
        if not any(path.startswith(pfx) for pfx in self.API_PREFIXES):
            return response

        # ⛔ NO CSP HERE — Next.js controls CSP fully

        self._set_common_security_headers(response)
        return response
