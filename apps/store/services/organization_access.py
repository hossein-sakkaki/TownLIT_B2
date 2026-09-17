# apps/store/services/organization_access.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)

from apps.organizations.models import Organization
from apps.organizations.selectors.ownership import (
    effective_organization_owner_memberships_queryset,
)


def effective_owned_organizations_queryset(
    *,
    user,
):
    if (
        not user
        or not getattr(
            user,
            "is_authenticated",
            False,
        )
    ):
        return Organization.objects.none()

    organization_ids = (
        effective_organization_owner_memberships_queryset()
        .filter(
            member__user=user,
        )
        .values_list(
            "organization_id",
            flat=True,
        )
    )

    return Organization.objects.filter(
        id__in=organization_ids,
    )


def user_owns_organization(
    *,
    user,
    organization,
) -> bool:
    if (
        not user
        or not getattr(
            user,
            "is_authenticated",
            False,
        )
        or organization is None
    ):
        return False

    return (
        effective_organization_owner_memberships_queryset()
        .filter(
            member__user=user,
            organization=organization,
        )
        .exists()
    )


def ensure_user_owns_organization(
    *,
    user,
    organization,
):
    if not user_owns_organization(
        user=user,
        organization=organization,
    ):
        raise PermissionDenied(
            "You do not have permission to manage "
            "this organization's store."
        )


def resolve_store_create_organization(
    *,
    user,
    organization_id=None,
):
    owned = effective_owned_organizations_queryset(
        user=user,
    )

    if organization_id not in (
        None,
        "",
    ):
        try:
            organization_id = int(
                organization_id
            )
        except (
            TypeError,
            ValueError,
        ):
            raise ValidationError({
                "organization": (
                    "A valid organization ID is required."
                ),
            })

        organization = (
            owned
            .filter(
                pk=organization_id,
            )
            .first()
        )

        if organization is None:
            raise PermissionDenied(
                "You do not have permission to create "
                "a store for this organization."
            )

        return organization

    candidates = list(
        owned.order_by("id")[:2]
    )

    if not candidates:
        raise PermissionDenied(
            "An owned organization is required "
            "to create a store."
        )

    if len(candidates) > 1:
        raise ValidationError({
            "organization": (
                "Organization is required when you own "
                "more than one organization."
            ),
        })

    return candidates[0]