# apps/conversation/services/organization/direct_selectors.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from __future__ import annotations

from django.db.models import Count, Exists, F, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.conversation.constants import (
    OrganizationConversationContextType,
    OrganizationConversationStatus,
)
from apps.conversation.models import Message, OrganizationDialogueContext
from apps.organizations.constants import (
    ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
    OrganizationPermissionKey,
    OrganizationRoleScope,
)
from apps.organizations.models import OrganizationRoleAssignment
from apps.organizations.services.access import get_current_membership_for_user


def organization_direct_incoming_messages_queryset(*, context):
    return Message.objects.filter(
        dialogue_id=context.dialogue_id,
        sender_id=context.participant_user_id,
        is_system=False,
        is_delivery_ready=True,
        organization_attribution__isnull=True,
    )


def organization_direct_unread_queryset(*, context, operator_user):
    return organization_direct_incoming_messages_queryset(
        context=context,
    ).exclude(
        seen_by_users=operator_user,
    )


def organization_direct_unread_count(*, context, operator_user) -> int:
    return organization_direct_unread_queryset(
        context=context,
        operator_user=operator_user,
    ).count()


def _effective_assignee_role_assignments(*, now):
    return (
        OrganizationRoleAssignment.objects
        .filter(
            membership_id=OuterRef("assigned_to_membership_id"),
            membership__status__in=ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
            is_active=True,
            revoked_at__isnull=True,
            starts_at__lte=now,
            scope_type=OrganizationRoleScope.ORGANIZATION,
            scope_key="",
            role__is_active=True,
            role__role_permissions__permission__key__in=(
                OrganizationPermissionKey.REPLY_MESSENGER,
                OrganizationPermissionKey.MANAGE_MESSENGER,
            ),
            role__role_permissions__permission__is_active=True,
        )
        .filter(
            Q(ends_at__isnull=True)
            | Q(ends_at__gt=now)
        )
    )


def organization_direct_total_unread_count(*, organization, operator_user) -> int:
    return (
        Message.objects
        .filter(
            dialogue__organization_context__organization=organization,
            dialogue__organization_context__context_type=(
                OrganizationConversationContextType.DIRECT
            ),
            dialogue__organization_context__status__in=(
                OrganizationConversationStatus.OPEN,
                OrganizationConversationStatus.RESOLVED,
            ),
            sender_id=F(
                "dialogue__organization_context__participant_user_id"
            ),
            is_system=False,
            is_delivery_ready=True,
            organization_attribution__isnull=True,
        )
        .exclude(seen_by_users=operator_user)
        .distinct()
        .count()
    )


def build_organization_direct_inbox_queryset(
    *,
    organization,
    operator_user,
    status_filter="open",
    assignment_filter="all",
    unread_only=False,
):
    now = timezone.now()
    unread_messages = (
        Message.objects
        .filter(
            dialogue_id=OuterRef("dialogue_id"),
            sender_id=OuterRef("participant_user_id"),
            is_system=False,
            is_delivery_ready=True,
            organization_attribution__isnull=True,
        )
        .exclude(seen_by_users=operator_user)
    )
    unread_count = (
        unread_messages
        .order_by()
        .values("dialogue_id")
        .annotate(total=Count("id", distinct=True))
        .values("total")[:1]
    )
    latest_message_ts = (
        Message.objects
        .filter(
            dialogue_id=OuterRef("dialogue_id"),
            is_delivery_ready=True,
        )
        .order_by("-timestamp", "-id")
        .values("timestamp")[:1]
    )

    queryset = (
        OrganizationDialogueContext.objects
        .filter(
            organization=organization,
            context_type=OrganizationConversationContextType.DIRECT,
        )
        .select_related(
            "dialogue",
            "dialogue__last_message__sender",
            "dialogue__last_message__organization_attribution__organization",
            "dialogue__last_message__organization_attribution__actor_membership",
            "dialogue__last_message__reply_to__sender",
            "organization",
            "participant_user",
            "assigned_to_membership__member__user",
        )
        .prefetch_related(
            "dialogue__last_message__seen_by_users",
            "dialogue__last_message__encryptions",
        )
        .annotate(
            has_unread=Exists(unread_messages),
            operator_unread_count=Coalesce(
                Subquery(
                    unread_count,
                    output_field=IntegerField(),
                ),
                Value(0),
            ),
            has_effective_assignee=Exists(
                _effective_assignee_role_assignments(now=now)
            ),
            last_activity=Subquery(latest_message_ts),
        )
    )

    normalized_status = str(status_filter or "open").strip().lower()
    if normalized_status in {
        OrganizationConversationStatus.OPEN,
        OrganizationConversationStatus.RESOLVED,
        OrganizationConversationStatus.CLOSED,
    }:
        queryset = queryset.filter(status=normalized_status)
    elif normalized_status != "all":
        queryset = queryset.filter(status=OrganizationConversationStatus.OPEN)

    normalized_assignment = str(assignment_filter or "all").strip().lower()
    if normalized_assignment == "unassigned":
        queryset = queryset.filter(
            Q(assigned_to_membership__isnull=True)
            | Q(has_effective_assignee=False)
        )
    elif normalized_assignment == "me":
        membership = get_current_membership_for_user(
            organization=organization,
            user=operator_user,
        )
        if not membership or membership.status not in ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES:
            return queryset.none()
        queryset = queryset.filter(
            assigned_to_membership=membership,
            has_effective_assignee=True,
        )

    if unread_only:
        queryset = queryset.filter(has_unread=True)

    return queryset.order_by(
        "-has_unread",
        "-last_activity",
        "-updated_at",
        "-id",
    )
