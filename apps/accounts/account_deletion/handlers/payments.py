#
#  apps/accounts/account_deletion/handlers/payments.py
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
from apps.payment.models import Payment


@account_deletion_registry.register(
    key="payments",
    order=100,
)
def purge_payment_identity(
    context: AccountDeletionContext,
) -> None:
    """
    Retain financial records without account identity.
    """
    Payment.objects.filter(
        user=context.user,
    ).update(
        user=None,
        email=None,
        cancel_token=None,
        cancel_token_created_at=None,
        confirm_token=None,
        confirm_token_created_at=None,
    )