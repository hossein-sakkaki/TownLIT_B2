#
#  apps/accounts/account_deletion/handlers/communication.py
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
from apps.communication.models import (
    EmailCampaign,
    EmailLog,
    ExternalContact,
    UnsubscribedUser,
)


@account_deletion_registry.register(
    key="communication",
    order=200,
)
def purge_communication_identity(
    context: AccountDeletionContext,
) -> None:
    """
    Remove marketing identity and anonymize retained logs.
    """
    ExternalContact.objects.filter(
        email__iexact=context.original_email,
    ).delete()

    UnsubscribedUser.objects.filter(
        email__iexact=context.original_email,
    ).delete()

    for campaign in EmailCampaign.objects.filter(
        recipients=context.user,
    ).iterator():
        campaign.recipients.remove(
            context.user
        )

    EmailLog.objects.filter(
        user=context.user,
    ).update(
        user=None,
        email=context.anonymized_email,
    )

    EmailLog.objects.filter(
        email__iexact=context.original_email,
    ).update(
        email=context.anonymized_email,
    )