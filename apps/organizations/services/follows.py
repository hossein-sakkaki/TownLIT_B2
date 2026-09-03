# apps/organizations/services/follows.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.organizations.constants import (
    OrganizationAuditAction,
    OrganizationAuditSource,
    OrganizationConnectionStatus,
    OrganizationConnectionType,
    OrganizationStatus,
    OrganizationVisibility,
)
from apps.organizations.feature_flags import (
    ensure_organizations_enabled,
)
from apps.organizations.models import (
    Organization,
    OrganizationAuditLog,
    OrganizationConnection,
)


def _ensure_user_can_follow(user):
    if not user or not getattr(user, "is_authenticated", False):
        raise ValidationError("Authentication is required.")

    if not getattr(user, "is_active", False):
        raise ValidationError("The account is not active.")

    if getattr(user, "is_deleted", False):
        raise ValidationError("The account is deactivated.")

    if getattr(user, "is_suspended", False):
        raise ValidationError("The account is suspended.")

    if getattr(user, "is_account_paused", False):
        raise ValidationError("The account is paused.")


@transaction.atomic
def follow_organization(*, user, organization):
    ensure_organizations_enabled()
    _ensure_user_can_follow(user)

    organization = Organization.objects.select_for_update().get(
        pk=organization.pk
    )

    if organization.status != OrganizationStatus.ACTIVE:
        raise ValidationError(
            "Only active organizations can be followed."
        )

    if organization.visibility == OrganizationVisibility.PRIVATE:
        raise ValidationError(
            "Private organizations cannot be followed publicly."
        )

    current = (
        OrganizationConnection.objects
        .select_for_update()
        .filter(
            organization=organization,
            user=user,
            status=OrganizationConnectionStatus.ACTIVE,
        )
        .first()
    )

    if current:
        if (
            current.relationship_type
            == OrganizationConnectionType.MEMBER
        ):
            raise ValidationError(
                "Official organization members cannot also be followers."
            )

        return current

    connection = OrganizationConnection(
        organization=organization,
        user=user,
        relationship_type=OrganizationConnectionType.FOLLOWER,
    )
    connection.full_clean()

    try:
        with transaction.atomic():
            connection.save()
    except IntegrityError:
        return OrganizationConnection.objects.get(
            organization=organization,
            user=user,
            status=OrganizationConnectionStatus.ACTIVE,
        )

    OrganizationAuditLog.objects.create(
        organization=organization,
        action=OrganizationAuditAction.FOLLOWED,
        source=OrganizationAuditSource.SERVICE,
        actor=user,
        target_user=user,
    )

    return connection


@transaction.atomic
def unfollow_organization(*, user, organization, now=None):
    ensure_organizations_enabled()
    _ensure_user_can_follow(user)
    now = now or timezone.now()

    connection = (
        OrganizationConnection.objects
        .select_for_update()
        .filter(
            organization=organization,
            user=user,
            status=OrganizationConnectionStatus.ACTIVE,
        )
        .first()
    )

    if not connection:
        return None

    if (
        connection.relationship_type
        == OrganizationConnectionType.MEMBER
    ):
        raise ValidationError(
            "Official members must leave the organization instead of unfollowing it."
        )

    connection.status = OrganizationConnectionStatus.ENDED
    connection.ended_at = now
    connection.end_reason = "user_unfollowed"
    connection.save(
        update_fields=[
            "status",
            "ended_at",
            "end_reason",
            "updated_at",
        ]
    )

    OrganizationAuditLog.objects.create(
        organization=organization,
        action=OrganizationAuditAction.UNFOLLOWED,
        source=OrganizationAuditSource.SERVICE,
        actor=user,
        target_user=user,
    )

    return connection
