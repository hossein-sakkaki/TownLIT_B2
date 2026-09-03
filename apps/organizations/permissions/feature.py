# apps/organizations/permissions/feature.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from rest_framework.permissions import BasePermission

from apps.organizations.feature_flags import organizations_enabled


class OrganizationsEnabledPermission(BasePermission):
    message = "Organizations are currently unavailable."

    def has_permission(self, request, view):
        return organizations_enabled()
