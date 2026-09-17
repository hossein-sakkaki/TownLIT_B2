# common/permissions.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on YYYY-MM-DD.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from rest_framework import permissions


class IsAdminOrReadOnly(
    permissions.BasePermission
):
    """
    Allow create for anyone and restrict
    other actions to staff users.
    """

    def has_permission(
        self,
        request,
        view,
    ):
        if view.action == "create":
            return True

        return bool(
            request.user
            and request.user.is_staff
        )
        
        
