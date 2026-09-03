# apps/organizations/services/memberships.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.organizations.constants import (
    CURRENT_MEMBERSHIP_STATUSES,
    MembershipRequestDirection,
    MembershipRequestStatus,
    OrganizationAuditAction,
    OrganizationAuditSource,
    OrganizationConnectionStatus,
    OrganizationConnectionType,
    OrganizationMembershipStatus,
    OrganizationPermissionKey,
    OrganizationRoleKey,
    OrganizationStatus,
)
from apps.organizations.feature_flags import (
    ensure_organizations_enabled,
)
from apps.organizations.models import (
    OrganizationAuditLog,
    OrganizationConnection,
    OrganizationMembership,
    OrganizationMembershipRequest,
    OrganizationRoleAssignment,
)
from apps.organizations.services.access import (
    user_has_organization_permission,
)


DEFAULT_MEMBERSHIP_REQUEST_TTL_DAYS = 30


def _ensure_organization_accepts_memberships(organization):
    if organization.status != OrganizationStatus.ACTIVE:
        raise ValidationError(
            "Organization membership is unavailable while the organization is not active."
        )


def _ensure_member_can_participate(member):
    user = member.user

    if not getattr(member, "is_active", False):
        raise ValidationError(
            "An active TownLIT Member profile is required."
        )

    if not getattr(user, "is_active", False):
        raise ValidationError("The account is not active.")

    if getattr(user, "is_deleted", False):
        raise ValidationError("The account is deactivated.")

    if getattr(user, "is_suspended", False):
        raise ValidationError("The account is suspended.")

    if getattr(user, "is_account_paused", False):
        raise ValidationError("The account is paused.")


def _get_current_membership(*, organization, member):
    return (
        OrganizationMembership.objects
        .filter(
            organization=organization,
            member=member,
            status__in=CURRENT_MEMBERSHIP_STATUSES,
        )
        .first()
    )


def _get_or_validate_pending_request(*, organization, member):
    pending = (
        OrganizationMembershipRequest.objects
        .select_for_update()
        .filter(
            organization=organization,
            member=member,
            status=MembershipRequestStatus.PENDING,
        )
        .first()
    )

    if (
        pending
        and pending.expires_at
        and pending.expires_at <= timezone.now()
    ):
        pending.status = MembershipRequestStatus.EXPIRED
        pending.responded_at = timezone.now()
        pending.save(
            update_fields=[
                "status",
                "responded_at",
                "updated_at",
            ]
        )
        return None

    return pending


@transaction.atomic
def request_organization_membership(
    *,
    member,
    organization,
    message=None,
    expires_at=None,
):
    ensure_organizations_enabled()
    _ensure_member_can_participate(member)
    _ensure_organization_accepts_memberships(organization)

    if _get_current_membership(
        organization=organization,
        member=member,
    ):
        raise ValidationError(
            "The member already has an official organization membership."
        )

    existing = _get_or_validate_pending_request(
        organization=organization,
        member=member,
    )

    if existing:
        return existing

    now = timezone.now()
    expires_at = expires_at or (
        now + timedelta(
            days=DEFAULT_MEMBERSHIP_REQUEST_TTL_DAYS
        )
    )

    membership_request = OrganizationMembershipRequest(
        organization=organization,
        member=member,
        direction=(
            MembershipRequestDirection.MEMBER_TO_ORGANIZATION
        ),
        initiated_by=member.user,
        message=message,
        expires_at=expires_at,
    )
    membership_request.full_clean()

    try:
        with transaction.atomic():
            membership_request.save()
    except IntegrityError:
        return OrganizationMembershipRequest.objects.get(
            organization=organization,
            member=member,
            status=MembershipRequestStatus.PENDING,
        )

    OrganizationAuditLog.objects.create(
        organization=organization,
        action=OrganizationAuditAction.MEMBERSHIP_REQUESTED,
        source=OrganizationAuditSource.SERVICE,
        actor=member.user,
        target_user=member.user,
        membership_request=membership_request,
    )

    return membership_request


@transaction.atomic
def invite_member_to_organization(
    *,
    actor,
    organization,
    member,
    message=None,
    expires_at=None,
):
    ensure_organizations_enabled()
    _ensure_member_can_participate(member)
    _ensure_organization_accepts_memberships(organization)

    if not user_has_organization_permission(
        user=actor,
        organization=organization,
        permission_key=OrganizationPermissionKey.MANAGE_MEMBERS,
    ):
        raise PermissionDenied(
            "You do not have permission to invite organization members."
        )

    if _get_current_membership(
        organization=organization,
        member=member,
    ):
        raise ValidationError(
            "The member already has an official organization membership."
        )

    existing = _get_or_validate_pending_request(
        organization=organization,
        member=member,
    )

    if existing:
        return existing

    now = timezone.now()
    expires_at = expires_at or (
        now + timedelta(
            days=DEFAULT_MEMBERSHIP_REQUEST_TTL_DAYS
        )
    )

    membership_request = OrganizationMembershipRequest(
        organization=organization,
        member=member,
        direction=(
            MembershipRequestDirection.ORGANIZATION_TO_MEMBER
        ),
        initiated_by=actor,
        message=message,
        expires_at=expires_at,
    )
    membership_request.full_clean()

    try:
        with transaction.atomic():
            membership_request.save()
    except IntegrityError:
        return OrganizationMembershipRequest.objects.get(
            organization=organization,
            member=member,
            status=MembershipRequestStatus.PENDING,
        )

    OrganizationAuditLog.objects.create(
        organization=organization,
        action=OrganizationAuditAction.MEMBERSHIP_INVITED,
        source=OrganizationAuditSource.SERVICE,
        actor=actor,
        target_user=member.user,
        membership_request=membership_request,
    )

    return membership_request


def _ensure_request_responder(*, membership_request, actor):
    if (
        membership_request.direction
        == MembershipRequestDirection.MEMBER_TO_ORGANIZATION
    ):
        if not user_has_organization_permission(
            user=actor,
            organization=membership_request.organization,
            permission_key=OrganizationPermissionKey.MANAGE_MEMBERS,
        ):
            raise PermissionDenied(
                "Organization membership approval is required."
            )
        return

    if actor.id != membership_request.member.user_id:
        raise PermissionDenied(
            "Only the invited member can respond to this invitation."
        )


def accept_membership_request(
    *,
    membership_request,
    actor,
    response_message=None,
    now=None,
):
    ensure_organizations_enabled()
    now = now or timezone.now()
    expired = False
    membership = None

    with transaction.atomic():
        membership_request = (
            OrganizationMembershipRequest.objects
            .select_for_update()
            .select_related(
                "organization",
                "member__user",
            )
            .get(pk=membership_request.pk)
        )

        if membership_request.status != MembershipRequestStatus.PENDING:
            raise ValidationError(
                "This membership request is no longer pending."
            )

        if (
            membership_request.expires_at
            and membership_request.expires_at <= now
        ):
            membership_request.status = MembershipRequestStatus.EXPIRED
            membership_request.responded_at = now
            membership_request.save(
                update_fields=[
                    "status",
                    "responded_at",
                    "updated_at",
                ]
            )
            expired = True
        else:
            _ensure_organization_accepts_memberships(
                membership_request.organization
            )
            _ensure_request_responder(
                membership_request=membership_request,
                actor=actor,
            )
            _ensure_member_can_participate(
                membership_request.member
            )

            existing_membership = _get_current_membership(
                organization=membership_request.organization,
                member=membership_request.member,
            )

            if existing_membership:
                raise ValidationError(
                    "The member already has an official organization membership."
                )

            connection = (
                OrganizationConnection.objects
                .select_for_update()
                .filter(
                    organization=membership_request.organization,
                    user=membership_request.member.user,
                    status=OrganizationConnectionStatus.ACTIVE,
                )
                .first()
            )

            if connection:
                if (
                    connection.relationship_type
                    == OrganizationConnectionType.MEMBER
                ):
                    raise ValidationError(
                        "An active member connection already exists."
                    )

                connection.relationship_type = (
                    OrganizationConnectionType.MEMBER
                )
                connection.save(
                    update_fields=[
                        "relationship_type",
                        "updated_at",
                    ]
                )
            else:
                connection = OrganizationConnection(
                    organization=membership_request.organization,
                    user=membership_request.member.user,
                    relationship_type=(
                        OrganizationConnectionType.MEMBER
                    ),
                )
                connection.full_clean()
                connection.save()

            membership = OrganizationMembership(
                organization=membership_request.organization,
                member=membership_request.member,
                connection=connection,
                source_request=membership_request,
                approved_by=actor,
                status=OrganizationMembershipStatus.ACTIVE,
                joined_at=now,
            )
            membership.full_clean()
            membership.save()

            membership_request.status = MembershipRequestStatus.ACCEPTED
            membership_request.responded_by = actor
            membership_request.responded_at = now
            membership_request.response_message = response_message
            membership_request.save(
                update_fields=[
                    "status",
                    "responded_by",
                    "responded_at",
                    "response_message",
                    "updated_at",
                ]
            )

            OrganizationAuditLog.objects.create(
                organization=membership.organization,
                action=OrganizationAuditAction.MEMBERSHIP_ACCEPTED,
                source=OrganizationAuditSource.SERVICE,
                actor=actor,
                target_user=membership.member.user,
                membership=membership,
                membership_request=membership_request,
                metadata={
                    "request_direction": membership_request.direction,
                },
            )

    if expired:
        raise ValidationError(
            "This membership request has expired."
        )

    return membership


@transaction.atomic
def reject_membership_request(
    *,
    membership_request,
    actor,
    response_message=None,
    now=None,
):
    ensure_organizations_enabled()
    now = now or timezone.now()

    membership_request = (
        OrganizationMembershipRequest.objects
        .select_for_update()
        .select_related(
            "organization",
            "member__user",
        )
        .get(pk=membership_request.pk)
    )

    if membership_request.status != MembershipRequestStatus.PENDING:
        raise ValidationError(
            "This membership request is no longer pending."
        )

    _ensure_request_responder(
        membership_request=membership_request,
        actor=actor,
    )

    membership_request.status = MembershipRequestStatus.REJECTED
    membership_request.responded_by = actor
    membership_request.responded_at = now
    membership_request.response_message = response_message
    membership_request.save(
        update_fields=[
            "status",
            "responded_by",
            "responded_at",
            "response_message",
            "updated_at",
        ]
    )

    OrganizationAuditLog.objects.create(
        organization=membership_request.organization,
        action=OrganizationAuditAction.MEMBERSHIP_REJECTED,
        source=OrganizationAuditSource.SERVICE,
        actor=actor,
        target_user=membership_request.member.user,
        membership_request=membership_request,
    )

    return membership_request


@transaction.atomic
def withdraw_membership_request(
    *,
    membership_request,
    actor,
    now=None,
):
    ensure_organizations_enabled()
    now = now or timezone.now()

    membership_request = (
        OrganizationMembershipRequest.objects
        .select_for_update()
        .select_related(
            "organization",
            "member__user",
        )
        .get(pk=membership_request.pk)
    )

    if membership_request.status != MembershipRequestStatus.PENDING:
        raise ValidationError(
            "This membership request is no longer pending."
        )

    if (
        membership_request.direction
        != MembershipRequestDirection.MEMBER_TO_ORGANIZATION
        or actor.id != membership_request.member.user_id
    ):
        raise PermissionDenied(
            "Only the requesting member can withdraw this request."
        )

    membership_request.status = MembershipRequestStatus.WITHDRAWN
    membership_request.responded_by = actor
    membership_request.responded_at = now
    membership_request.save(
        update_fields=[
            "status",
            "responded_by",
            "responded_at",
            "updated_at",
        ]
    )

    OrganizationAuditLog.objects.create(
        organization=membership_request.organization,
        action=OrganizationAuditAction.MEMBERSHIP_WITHDRAWN,
        source=OrganizationAuditSource.SERVICE,
        actor=actor,
        target_user=membership_request.member.user,
        membership_request=membership_request,
    )

    return membership_request


@transaction.atomic
def cancel_membership_invitation(
    *,
    membership_request,
    actor,
    now=None,
):
    ensure_organizations_enabled()
    now = now or timezone.now()

    membership_request = (
        OrganizationMembershipRequest.objects
        .select_for_update()
        .select_related(
            "organization",
            "member__user",
        )
        .get(pk=membership_request.pk)
    )

    if membership_request.status != MembershipRequestStatus.PENDING:
        raise ValidationError(
            "This membership request is no longer pending."
        )

    if (
        membership_request.direction
        != MembershipRequestDirection.ORGANIZATION_TO_MEMBER
    ):
        raise ValidationError(
            "Only organization invitations can be canceled."
        )

    if not user_has_organization_permission(
        user=actor,
        organization=membership_request.organization,
        permission_key=OrganizationPermissionKey.MANAGE_MEMBERS,
    ):
        raise PermissionDenied(
            "You do not have permission to cancel this invitation."
        )

    membership_request.status = MembershipRequestStatus.CANCELED
    membership_request.responded_by = actor
    membership_request.responded_at = now
    membership_request.save(
        update_fields=[
            "status",
            "responded_by",
            "responded_at",
            "updated_at",
        ]
    )

    OrganizationAuditLog.objects.create(
        organization=membership_request.organization,
        action=OrganizationAuditAction.MEMBERSHIP_CANCELED,
        source=OrganizationAuditSource.SERVICE,
        actor=actor,
        target_user=membership_request.member.user,
        membership_request=membership_request,
    )

    return membership_request


def _ensure_membership_has_no_owner_role(membership):
    has_owner_role = OrganizationRoleAssignment.objects.filter(
        membership=membership,
        role__key=OrganizationRoleKey.OWNER,
        is_active=True,
        revoked_at__isnull=True,
    ).exists()

    if has_owner_role:
        raise ValidationError(
            "Organization owners must transfer or remove ownership through governance before leaving."
        )


@transaction.atomic
def leave_organization(*, membership, actor, now=None):
    ensure_organizations_enabled()
    now = now or timezone.now()

    membership = (
        OrganizationMembership.objects
        .select_for_update()
        .select_related(
            "organization",
            "member__user",
            "connection",
        )
        .get(pk=membership.pk)
    )

    if actor.id != membership.member.user_id:
        raise PermissionDenied(
            "Only the member can leave their organization membership."
        )

    _ensure_membership_has_no_owner_role(membership)

    return _end_membership(
        membership=membership,
        actor=actor,
        action=OrganizationAuditAction.MEMBER_LEFT,
        reason="member_left",
        now=now,
    )


@transaction.atomic
def remove_organization_member(
    *,
    membership,
    actor,
    reason=None,
    now=None,
):
    ensure_organizations_enabled()
    now = now or timezone.now()

    membership = (
        OrganizationMembership.objects
        .select_for_update()
        .select_related(
            "organization",
            "member__user",
            "connection",
        )
        .get(pk=membership.pk)
    )

    if not user_has_organization_permission(
        user=actor,
        organization=membership.organization,
        permission_key=OrganizationPermissionKey.MANAGE_MEMBERS,
    ):
        raise PermissionDenied(
            "You do not have permission to remove organization members."
        )

    _ensure_membership_has_no_owner_role(membership)

    return _end_membership(
        membership=membership,
        actor=actor,
        action=OrganizationAuditAction.MEMBER_REMOVED,
        reason=reason or "member_removed",
        now=now,
    )


def _end_membership(*, membership, actor, action, reason, now):
    if membership.status == OrganizationMembershipStatus.ENDED:
        return membership

    membership.status = OrganizationMembershipStatus.ENDED
    membership.ended_at = now
    membership.end_reason = reason
    membership.save(
        update_fields=[
            "status",
            "ended_at",
            "end_reason",
            "updated_at",
        ]
    )

    connection = OrganizationConnection.objects.select_for_update().get(
        pk=membership.connection_id
    )
    connection.status = OrganizationConnectionStatus.ENDED
    connection.ended_at = now
    connection.end_reason = reason
    connection.save(
        update_fields=[
            "status",
            "ended_at",
            "end_reason",
            "updated_at",
        ]
    )

    OrganizationRoleAssignment.objects.filter(
        membership=membership,
        is_active=True,
    ).update(
        is_active=False,
        active_slot=None,
        revoked_at=now,
        updated_at=now,
    )

    OrganizationAuditLog.objects.create(
        organization=membership.organization,
        action=action,
        source=OrganizationAuditSource.SERVICE,
        actor=actor,
        target_user=membership.member.user,
        membership=membership,
        metadata={
            "reason": reason,
        },
    )

    return membership
