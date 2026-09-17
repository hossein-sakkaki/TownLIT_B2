# apps/organizations/services/account_deletion.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from django.core.exceptions import ValidationError

from apps.organizations.selectors.ownership import (
    effective_organization_owner_memberships_queryset,
)


def ensure_user_can_be_permanently_deleted(
    *,
    user,
):
    """
    Prevent permanent account deletion from bypassing
    Organization ownership governance.
    """

    owns_organization = (
        effective_organization_owner_memberships_queryset()
        .filter(
            member__user=user,
        )
        .exists()
    )

    if owns_organization:
        raise ValidationError(
            (
                "Account deletion cannot be completed "
                "while the account holds active "
                "Organization ownership. Transfer or "
                "remove ownership through Organization "
                "governance first."
            )
        )