#
#  apps/accounts/account_deletion/handlers/profiles.py
#  TownLIT
#
#  Created by Hossein Sakkaki on 2026-08-04.
#  Last Update by Hossein Sakkaki on 2026-08-04.
#

from apps.accounts.account_deletion.context import (
    AccountDeletionContext,
)
from apps.accounts.account_deletion.registry import (
    account_deletion_registry,
)
from apps.profiles.models.guest import GuestUser
from apps.profiles.models.member import Member


@account_deletion_registry.register(
    key="profiles",
    order=800,
)
def purge_profile_data(
    context: AccountDeletionContext,
) -> None:
    """
    Delete Member and Guest profile rows after their content is removed.
    """
    Member.objects.filter(
        user_id=context.user.id,
    ).delete()

    GuestUser.objects.filter(
        user_id=context.user.id,
    ).delete()

    for accessor_name in (
        "client_profile",
        "customer_profile",
    ):
        try:
            profile = getattr(
                context.user,
                accessor_name,
            )
        except Exception:
            profile = None

        if profile is not None:
            profile.delete()