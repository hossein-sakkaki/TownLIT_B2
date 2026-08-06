#
#  apps/accounts/account_deletion/handlers/organizations.py
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
from apps.profiles.models import Member
from apps.profilesOrg.models import (
    ChristianPublishingHouse,
    Organization,
)


@account_deletion_registry.register(
    key="organizations",
    order=700,
)
def detach_organization_relations(
    context: AccountDeletionContext,
) -> None:
    """
    Detach inactive organization relations before profile removal.
    """
    ChristianPublishingHouse.objects.filter(
        authors=context.user,
    )

    for publishing_house in (
        ChristianPublishingHouse.objects
        .filter(
            authors=context.user,
        )
        .iterator()
    ):
        publishing_house.authors.remove(
            context.user
        )

    member = Member.objects.filter(
        user=context.user,
    ).first()

    if member is None:
        return

    for organization in Organization.objects.filter(
        org_owners=member,
    ).iterator():
        organization.org_owners.remove(
            member
        )