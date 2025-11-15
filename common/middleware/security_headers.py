# common/middleware/security_headers.py
from django.utils.deprecation import MiddlewareMixin

class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Backend SHOULD NOT send CSP.
    CSP is fully handled by Next.js to avoid double-policy conflicts.

    This middleware ONLY sets safe security headers:
      - X-Content-Type-Options
      - Referrer-Policy
      - Permissions-Policy
    """

    def process_response(self, request, response):
        # Always set safe headers
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()"
        )

        # ❌ DO NOT set CSP
        # If backend accidentally sets it elsewhere, remove it:
        if "Content-Security-Policy" in response:
            del response["Content-Security-Policy"]

        return response
