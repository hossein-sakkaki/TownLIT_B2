from rest_framework.response import Response
from rest_framework import status
from functools import wraps

def require_conversation_access(view_func):
    @wraps(view_func)
    def _wrapped_view(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and getattr(user, "pin_security_enabled", False):
            if request.COOKIES.get("conversation_access") != "granted":
                return Response({'error': 'PIN access required for conversation.'}, status=status.HTTP_403_FORBIDDEN)
        return view_func(self, request, *args, **kwargs)
    return _wrapped_view
