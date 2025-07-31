# core/security/access.py
from datetime import timedelta
from django.utils import timezone
from rest_framework.response import Response
from django.conf import settings


DEFAULT_ACCESS_DURATION = settings.LITSHIELD_ACCESS_EXPIRATION_SECONDS


# Grant LITshield Access -------------------------------------------------------------
def grant_litshield_access(scope: str, user, response_data: dict = None, max_age: int = DEFAULT_ACCESS_DURATION):
    expires = timezone.now() + timedelta(seconds=max_age)
    data = {
        "access_granted": True,
        "expires_at": expires.isoformat(),
    }
    if response_data:
        data.update(response_data)

    response = Response(data, status=200)
    response.set_cookie(
        f"{scope}_access",
        "granted",
        max_age=max_age,
        httponly=True,
        secure=True,
        samesite="Lax",
    )
    return response


# Revoke LITshield Access -------------------------------------------------------------
def revoke_litshield_access(scope: str):
    response = Response({"message": f"{scope} access revoked"}, status=200)
    response.delete_cookie(
        f"{scope}_access",
        path="/",
        samesite="Lax",
    )
    return response


# Check LITshield Access -------------------------------------------------------------
def check_litshield_access(scope: str, request):
    user = getattr(request, "user", None)

    # ✅ اگر کاربر ندارد یا ورود نکرده:
    if user is None or not user.is_authenticated:
        return Response({"access_granted": False, "pin_security_enabled": None})

    # ✅ اگر سیستم امنیتی PIN فعال نیست، نیازی به مودال نیست:
    if not getattr(user, "pin_security_enabled", False):
        return Response({
            "access_granted": False,
            "pin_security_enabled": False,
            "expires_at": None
        })

    # ✅ اگر دسترسی از قبل وجود دارد (از طریق کوکی):
    cookie_key = f"{scope}_access"
    if request.COOKIES.get(cookie_key) == "granted":
        expires = timezone.now() + timedelta(seconds=DEFAULT_ACCESS_DURATION)
        return Response({
            "access_granted": True,
            "pin_security_enabled": True,
            "expires_at": expires.isoformat()
        })

    # ❌ در غیر این صورت، دسترسی وجود ندارد
    return Response({
        "access_granted": False,
        "pin_security_enabled": True,
        "expires_at": None
    })


