# apps/organizations/services/creation.py
#
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-09-12.
#

from django.db import IntegrityError, transaction

from apps.organizations.constants import (
    OrganizationAuditAction,
    OrganizationAuditSource,
    OrganizationConnectionType,
    OrganizationMembershipStatus,
    OrganizationVisibility,
)
from apps.organizations.models import (
    Organization,
    OrganizationAuditLog,
    OrganizationConnection,
    OrganizationMembership,
)
from apps.organizations.services.eligibility import (
    ensure_user_can_create_organization,
)
from apps.organizations.services.governance import (
    bootstrap_organization_governance,
)
from apps.organizations.services.roles import (
    assign_organization_role,
    bootstrap_organization_access,
    get_owner_role,
)
from apps.organizations.services.slugs import (
    generate_unique_organization_slug,
)
from apps.subscriptions.models import SubscriptionAccount


@transaction.atomic
def create_organization(
    *,
    creator,
    name,
    kind,
    description=None,
    history=None,
    statement_of_faith=None,
    statement_of_purpose=None,
    public_email=None,
    public_phone_number=None,
    website_url=None,
    country=None,
    city=None,
    primary_language=None,
    secondary_language=None,
    timezone="UTC",
    logo=None,
    visibility=OrganizationVisibility.PUBLIC,
):
    member = ensure_user_can_create_organization(creator)

    normalized_name = " ".join(
        str(name or "").split()
    )

    if not normalized_name:
        from django.core.exceptions import ValidationError

        raise ValidationError({
            "name": "Organization name is required.",
        })

    subscription_account = SubscriptionAccount.objects.create(
        billing_email=getattr(creator, "email", None),
    )

    organization = Organization(
        name=normalized_name,
        slug=generate_unique_organization_slug(
            normalized_name
        ),
        kind=kind,
        description=description,
        history=history,
        statement_of_faith=statement_of_faith,
        statement_of_purpose=statement_of_purpose,
        public_email=public_email,
        public_phone_number=public_phone_number,
        website_url=website_url,
        country=country,
        city=city,
        primary_language=primary_language,
        secondary_language=secondary_language,
        timezone=timezone or "UTC",
        logo=logo,
        visibility=visibility,
        subscription_account=subscription_account,
        created_by=creator,
    )
    organization.full_clean()

    for attempt in range(5):
        try:
            with transaction.atomic():
                organization.save()
            break
        except IntegrityError:
            if attempt == 4:
                raise

            organization.slug = generate_unique_organization_slug(
                f"{normalized_name}-{attempt + 2}"
            )
    else:
        raise IntegrityError(
            "Unable to reserve a unique organization slug."
        )

    connection = OrganizationConnection(
        organization=organization,
        user=creator,
        relationship_type=OrganizationConnectionType.MEMBER,
    )
    connection.full_clean()
    connection.save()

    membership = OrganizationMembership(
        organization=organization,
        member=member,
        connection=connection,
        approved_by=creator,
        status=OrganizationMembershipStatus.ACTIVE,
    )
    membership.full_clean()
    membership.save()

    bootstrap_organization_access(organization)
    bootstrap_organization_governance(organization)

    assign_organization_role(
        membership=membership,
        role=get_owner_role(organization),
        actor=creator,
        bypass_protection=True,
    )

    OrganizationAuditLog.objects.create(
        organization=organization,
        action=OrganizationAuditAction.ORGANIZATION_CREATED,
        source=OrganizationAuditSource.SERVICE,
        actor=creator,
        target_user=creator,
        membership=membership,
        metadata={
            "kind": organization.kind,
            "slug": organization.slug,
        },
    )

    return organization
