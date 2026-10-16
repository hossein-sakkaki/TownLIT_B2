# apps/conversation/integrations/organization.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-16.
#

from __future__ import annotations

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from apps.organizations.constants import OrganizationRoleScope
from apps.organizations.models import (
    Organization,
    OrganizationMembership,
    OrganizationRelationship,
    OrganizationRole,
    OrganizationRoleAssignment,
    OrganizationRolePermission,
    OrganizationVerificationGrant,
)
from apps.organizations.selectors.ownership import (
    ORGANIZATION_MANAGER_ROLE_KEYS,
)


def _reconcile_organization(organization_id, *, emit_visibility_event=False):
    from apps.conversation.services.organization import (
        reconcile_organization_members_community,
    )

    organization = Organization.objects.filter(pk=organization_id).first()
    if organization:
        reconcile_organization_members_community(
            organization=organization,
            emit_visibility_event=emit_visibility_event,
        )


def _reconcile_organization_user(organization_id, user_id):
    from apps.conversation.services.organization import (
        reconcile_organization_user_membership,
    )

    reconcile_organization_user_membership(
        organization_id=organization_id,
        user_id=user_id,
    )


def _schedule_organization_reconciliation(
    organization_id,
    *,
    emit_visibility_event=False,
):
    if not organization_id:
        return

    transaction.on_commit(
        lambda oid=organization_id, emit=emit_visibility_event: (
            _reconcile_organization(
                oid,
                emit_visibility_event=emit,
            )
        )
    )


def _schedule_membership_reconciliation(organization_id, user_id):
    if not organization_id or not user_id:
        return

    transaction.on_commit(
        lambda oid=organization_id, uid=user_id: (
            _reconcile_organization_user(oid, uid)
        )
    )


def _clear_invalid_direct_assignments(membership_id):
    from apps.conversation.services.organization import (
        clear_invalid_direct_assignments_for_membership_id,
    )

    clear_invalid_direct_assignments_for_membership_id(membership_id)


def _schedule_direct_assignment_reconciliation(membership_id):
    if not membership_id:
        return

    transaction.on_commit(
        lambda mid=membership_id: _clear_invalid_direct_assignments(mid)
    )


def _reconcile_direct_assignments_for_role_id(role_id):
    membership_ids = (
        OrganizationRoleAssignment.objects
        .filter(role_id=role_id)
        .values_list("membership_id", flat=True)
        .distinct()
    )
    for membership_id in membership_ids:
        _clear_invalid_direct_assignments(membership_id)


def _schedule_direct_assignment_role_reconciliation(role_id):
    if not role_id:
        return
    transaction.on_commit(
        lambda rid=role_id: _reconcile_direct_assignments_for_role_id(rid)
    )


def _role_assignment_affects_manager_roster(instance) -> bool:
    if (
        getattr(instance, "scope_type", None)
        != OrganizationRoleScope.ORGANIZATION
    ):
        return False

    role_key = (
        OrganizationRole.objects
        .filter(pk=getattr(instance, "role_id", None))
        .values_list("key", flat=True)
        .first()
    )
    return role_key in ORGANIZATION_MANAGER_ROLE_KEYS


def _organization_id_for_membership_id(membership_id):
    if not membership_id:
        return None

    return (
        OrganizationMembership.objects
        .filter(pk=membership_id)
        .values_list("organization_id", flat=True)
        .first()
    )


def _broadcast_members_community_manager_roster(organization_id):
    if not organization_id:
        return

    from apps.conversation.constants import (
        OrganizationConversationContextType,
    )
    from apps.conversation.models import OrganizationDialogueContext
    from apps.conversation.serializers import DialogueSerializer
    from apps.conversation.services.event_contracts import (
        build_group_updated_event_data,
    )
    from apps.conversation.services.realtime_dispatch import (
        conv_group_send,
        conversation_dialogue_group_name,
    )

    context = (
        OrganizationDialogueContext.objects
        .select_related(
            "dialogue",
            "organization",
        )
        .filter(
            organization_id=organization_id,
            context_type=(
                OrganizationConversationContextType.MEMBERS_COMMUNITY
            ),
        )
        .first()
    )
    if context is None:
        return

    dialogue = context.dialogue
    dialogue_payload = DialogueSerializer(
        dialogue,
        context={},
    ).data

    conv_group_send(
        conversation_dialogue_group_name(dialogue.slug),
        "group_updated",
        build_group_updated_event_data(
            dialogue_slug=dialogue.slug,
            reason="organization_manager_roster_changed",
            dialogue=dialogue_payload,
        ),
    )


def _schedule_members_community_manager_roster_refresh(organization_id):
    if not organization_id:
        return

    transaction.on_commit(
        lambda oid=organization_id: (
            _broadcast_members_community_manager_roster(oid)
        )
    )


def _schedule_manager_roster_refresh_for_role_assignment(instance):
    affects_roster = getattr(
        instance,
        "_conversation_affects_manager_roster",
        None,
    )
    if affects_roster is None:
        affects_roster = _role_assignment_affects_manager_roster(instance)

    if not affects_roster:
        return

    organization_id = getattr(
        instance,
        "_conversation_manager_roster_organization_id",
        None,
    )
    if not organization_id:
        organization_id = _organization_id_for_membership_id(
            getattr(instance, "membership_id", None)
        )

    _schedule_members_community_manager_roster_refresh(organization_id)


def _membership_user_id(instance):
    cached = getattr(instance, "_conversation_membership_user_id", None)
    if cached:
        return cached

    member = getattr(instance, "member", None)
    if member is not None:
        return getattr(member, "user_id", None)

    return (
        OrganizationMembership.objects
        .filter(pk=instance.pk)
        .values_list("member__user_id", flat=True)
        .first()
    )


@receiver(
    post_save,
    sender=Organization,
    dispatch_uid="conversation_org_community_organization_saved",
)
def organization_saved_for_members_community(sender, instance, **kwargs):
    _schedule_organization_reconciliation(
        instance.id,
        emit_visibility_event=True,
    )


@receiver(
    post_save,
    sender=OrganizationVerificationGrant,
    dispatch_uid="conversation_org_community_verification_saved",
)
def verification_grant_saved_for_members_community(sender, instance, **kwargs):
    _schedule_organization_reconciliation(
        instance.organization_id,
        emit_visibility_event=True,
    )


@receiver(
    post_save,
    sender=OrganizationRelationship,
    dispatch_uid="conversation_org_community_relationship_saved",
)
def organization_relationship_saved_for_members_community(sender, instance, **kwargs):
    # Sponsored verification validity depends on the relationship status.
    _schedule_organization_reconciliation(
        instance.target_organization_id,
        emit_visibility_event=True,
    )


@receiver(
    post_save,
    sender=OrganizationMembership,
    dispatch_uid="conversation_org_community_membership_saved",
)
def organization_membership_saved_for_members_community(sender, instance, **kwargs):
    _schedule_membership_reconciliation(
        instance.organization_id,
        _membership_user_id(instance),
    )
    _schedule_direct_assignment_reconciliation(instance.id)
    _schedule_members_community_manager_roster_refresh(
        instance.organization_id
    )


@receiver(
    pre_delete,
    sender=OrganizationMembership,
    dispatch_uid="conversation_org_community_membership_pre_delete",
)
def organization_membership_pre_delete_for_members_community(sender, instance, **kwargs):
    instance._conversation_membership_user_id = _membership_user_id(instance)


@receiver(
    post_delete,
    sender=OrganizationMembership,
    dispatch_uid="conversation_org_community_membership_deleted",
)
def organization_membership_deleted_for_members_community(sender, instance, **kwargs):
    _schedule_membership_reconciliation(
        instance.organization_id,
        _membership_user_id(instance),
    )
    _schedule_members_community_manager_roster_refresh(
        instance.organization_id
    )


@receiver(
    pre_delete,
    sender=OrganizationRoleAssignment,
    dispatch_uid="conversation_org_manager_roster_role_assignment_pre_delete",
)
def organization_role_assignment_pre_delete_for_manager_roster(
    sender,
    instance,
    **kwargs,
):
    instance._conversation_affects_manager_roster = (
        _role_assignment_affects_manager_roster(instance)
    )
    instance._conversation_manager_roster_organization_id = (
        _organization_id_for_membership_id(instance.membership_id)
    )


@receiver(
    post_save,
    sender=OrganizationRoleAssignment,
    dispatch_uid="conversation_org_direct_role_assignment_saved",
)
def organization_role_assignment_saved_for_direct_inbox(sender, instance, **kwargs):
    _schedule_direct_assignment_reconciliation(instance.membership_id)
    _schedule_manager_roster_refresh_for_role_assignment(instance)


@receiver(
    post_delete,
    sender=OrganizationRoleAssignment,
    dispatch_uid="conversation_org_direct_role_assignment_deleted",
)
def organization_role_assignment_deleted_for_direct_inbox(sender, instance, **kwargs):
    _schedule_direct_assignment_reconciliation(instance.membership_id)
    _schedule_manager_roster_refresh_for_role_assignment(instance)


@receiver(
    post_save,
    sender=OrganizationRole,
    dispatch_uid="conversation_org_direct_role_saved",
)
def organization_role_saved_for_direct_inbox(sender, instance, **kwargs):
    _schedule_direct_assignment_role_reconciliation(instance.id)


@receiver(
    post_save,
    sender=OrganizationRolePermission,
    dispatch_uid="conversation_org_direct_role_permission_saved",
)
def organization_role_permission_saved_for_direct_inbox(sender, instance, **kwargs):
    _schedule_direct_assignment_role_reconciliation(instance.role_id)


@receiver(
    post_delete,
    sender=OrganizationRolePermission,
    dispatch_uid="conversation_org_direct_role_permission_deleted",
)
def organization_role_permission_deleted_for_direct_inbox(sender, instance, **kwargs):
    _schedule_direct_assignment_role_reconciliation(instance.role_id)
