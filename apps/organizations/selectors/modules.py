# apps/organizations/selectors/modules.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from apps.organizations.constants import OrganizationModuleActivationStatus
from apps.organizations.models import (
    OrganizationModuleActivation,
    OrganizationModuleDefinition,
)


def organization_module_catalog_queryset(*, public_only=False):
    queryset = OrganizationModuleDefinition.objects.filter(
        is_active=True,
    )

    if public_only:
        queryset = queryset.filter(is_public_catalog=True)

    return queryset.order_by("sort_order", "name", "id")


def organization_module_activations_queryset(*, organization):
    return (
        OrganizationModuleActivation.objects
        .select_related("organization", "module")
        .filter(organization=organization)
        .order_by("module__sort_order", "module__name", "id")
    )


def enabled_organization_module_activations_queryset(*, organization):
    return organization_module_activations_queryset(
        organization=organization,
    ).filter(status=OrganizationModuleActivationStatus.ENABLED)
