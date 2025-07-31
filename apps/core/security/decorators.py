from rest_framework.response import Response
from rest_framework import status
from functools import wraps


# Require LITshield Access ------------------------------------------
def require_litshield_access(scope: str = "general"):
    """
    Decorator to protect actions with LITShield.
    Requires a valid cookie like: <scope>_access=granted,
    but skips if user's pin security is disabled.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(self, request, *args, **kwargs):
            user = request.user
            cookie_key = f"{scope}_access"

            # ✅ اگر کاربر لاگین نیست، رد شود
            if not user or not user.is_authenticated:
                return Response(
                    {'error': 'Authentication required.'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # ✅ اگر امنیت PIN غیرفعال است، اجازه بده
            if not getattr(user, "pin_security_enabled", False):
                return view_func(self, request, *args, **kwargs)

            # ✅ اگر کوکی معتبر وجود دارد، اجازه بده
            if request.COOKIES.get(cookie_key) == "granted":
                return view_func(self, request, *args, **kwargs)

            # ❌ در غیر این صورت، دسترسی رد شود
            return Response(
                {'error': f'LITShield PIN access required for {scope}.'},
                status=status.HTTP_403_FORBIDDEN
            )

        return _wrapped_view
    return decorator
