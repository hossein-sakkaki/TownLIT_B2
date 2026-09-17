#
# apps/accounts/account_deletion/handlers/organizations.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-08-04.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from apps.accounts.account_deletion.context import (
    AccountDeletionContext,
)
from apps.accounts.account_deletion.registry import (
    account_deletion_registry,
)
from apps.organizations.services.account_deletion import (
    ensure_user_can_be_permanently_deleted,
)


@account_deletion_registry.register(
    key="organizations",
    order=700,
)
def detach_organization_relations(
    context: AccountDeletionContext,
) -> None:
    """
    Protect Organization ownership governance before
    permanent profile removal.

    Non-owner Organization relations follow their model
    deletion behavior during account/profile cleanup.
    """

    ensure_user_can_be_permanently_deleted(
        user=context.user,
    )