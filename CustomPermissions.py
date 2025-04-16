from rest_framework.permissions import BasePermission, SAFE_METHODS

class GeneralCustomPermission(BasePermission):
    message = ''
    
    def has_permission(self, request, obj):
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.user_register == request.user
        # return super().has_object_permission(request, view, obj)