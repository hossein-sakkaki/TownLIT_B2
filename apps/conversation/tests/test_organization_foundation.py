# apps/conversation/tests/test_organization_foundation.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from django.core.exceptions import ValidationError
from django.db import models
from django.test import SimpleTestCase

from apps.conversation.constants import (
    OrganizationConversationContextType,
    OrganizationConversationStatus,
    OrganizationConversationWaitingFor,
)
from apps.conversation.models import (
    OrganizationDialogueContext,
    OrganizationMessageAttribution,
)
from apps.organizations.constants import (
    DEFAULT_ROLE_DEFINITIONS,
    OrganizationPermissionKey,
    OrganizationRoleKey,
)


MESSENGER_PERMISSION_KEYS = {
    OrganizationPermissionKey.VIEW_MESSENGER,
    OrganizationPermissionKey.REPLY_MESSENGER,
    OrganizationPermissionKey.ASSIGN_MESSENGER,
    OrganizationPermissionKey.MANAGE_MESSENGER,
}


class OrganizationConversationFoundationContractTests(SimpleTestCase):
    """Database-free contract tests for the 8F.1 foundation."""

    databases = set()

    def test_context_type_values_are_stable(self):
        self.assertEqual(
            OrganizationConversationContextType.DIRECT,
            "direct",
        )
        self.assertEqual(
            OrganizationConversationContextType.MEMBERS_COMMUNITY,
            "members_community",
        )

    def test_status_values_are_stable(self):
        self.assertEqual(OrganizationConversationStatus.OPEN, "open")
        self.assertEqual(
            OrganizationConversationStatus.RESOLVED,
            "resolved",
        )
        self.assertEqual(OrganizationConversationStatus.CLOSED, "closed")

    def test_waiting_for_values_are_stable(self):
        self.assertEqual(
            OrganizationConversationWaitingFor.NONE,
            "none",
        )
        self.assertEqual(
            OrganizationConversationWaitingFor.ORGANIZATION,
            "organization",
        )
        self.assertEqual(
            OrganizationConversationWaitingFor.PARTICIPANT,
            "participant",
        )

    def test_dialogue_context_relationship_contract(self):
        dialogue_field = OrganizationDialogueContext._meta.get_field(
            "dialogue"
        )
        organization_field = OrganizationDialogueContext._meta.get_field(
            "organization"
        )
        participant_field = OrganizationDialogueContext._meta.get_field(
            "participant_user"
        )
        assignee_field = OrganizationDialogueContext._meta.get_field(
            "assigned_to_membership"
        )

        self.assertIsInstance(dialogue_field, models.OneToOneField)
        self.assertEqual(
            dialogue_field.remote_field.related_name,
            "organization_context",
        )
        self.assertEqual(
            organization_field.remote_field.related_name,
            "conversation_contexts",
        )
        self.assertTrue(participant_field.null)
        self.assertTrue(participant_field.blank)
        self.assertTrue(assignee_field.null)
        self.assertTrue(assignee_field.blank)
        self.assertIs(
            assignee_field.remote_field.on_delete,
            models.SET_NULL,
        )

    def test_dialogue_context_constraints_are_declared(self):
        constraints = {
            constraint.name: constraint
            for constraint in OrganizationDialogueContext._meta.constraints
        }

        self.assertEqual(
            set(constraints),
            {
                "uq_conv_org_direct_context",
                "uq_conv_org_community_slot",
                "ck_conv_org_context_shape",
            },
        )

        direct_constraint = constraints["uq_conv_org_direct_context"]
        community_constraint = constraints["uq_conv_org_community_slot"]

        self.assertIsInstance(direct_constraint, models.UniqueConstraint)
        self.assertEqual(
            tuple(direct_constraint.fields),
            ("organization", "context_type", "participant_user"),
        )

        self.assertIsInstance(community_constraint, models.UniqueConstraint)
        self.assertEqual(
            tuple(community_constraint.fields),
            ("organization", "context_type", "canonical_slot"),
        )

        self.assertIsInstance(
            constraints["ck_conv_org_context_shape"],
            models.CheckConstraint,
        )

    def test_dialogue_context_indexes_are_declared(self):
        indexes = {
            index.name: tuple(index.fields)
            for index in OrganizationDialogueContext._meta.indexes
        }

        self.assertEqual(
            indexes["conv_org_ctx_type_status_idx"],
            ("organization", "context_type", "status"),
        )
        self.assertEqual(
            indexes["conv_org_ctx_participant_idx"],
            ("participant_user", "context_type"),
        )

    def test_direct_context_clears_canonical_slot(self):
        context = OrganizationDialogueContext(
            context_type=OrganizationConversationContextType.DIRECT,
            canonical_slot=1,
        )

        context._sync_canonical_slot()

        self.assertIsNone(context.canonical_slot)

    def test_members_community_sets_canonical_slot(self):
        context = OrganizationDialogueContext(
            context_type=(
                OrganizationConversationContextType.MEMBERS_COMMUNITY
            ),
        )

        context._sync_canonical_slot()

        self.assertEqual(context.canonical_slot, 1)

    def test_direct_context_requires_participant_without_database(self):
        context = OrganizationDialogueContext(
            context_type=OrganizationConversationContextType.DIRECT,
        )

        with self.assertRaises(ValidationError) as captured:
            context.clean()

        self.assertIn(
            "participant_user",
            captured.exception.message_dict,
        )

    def test_members_community_rejects_direct_only_state_without_database(self):
        context = OrganizationDialogueContext(
            context_type=(
                OrganizationConversationContextType.MEMBERS_COMMUNITY
            ),
            status=OrganizationConversationStatus.RESOLVED,
            waiting_for=OrganizationConversationWaitingFor.PARTICIPANT,
        )

        with self.assertRaises(ValidationError) as captured:
            context.clean()

        self.assertIn("status", captured.exception.message_dict)
        self.assertIn("waiting_for", captured.exception.message_dict)

    def test_message_attribution_relationship_contract(self):
        message_field = OrganizationMessageAttribution._meta.get_field(
            "message"
        )
        organization_field = OrganizationMessageAttribution._meta.get_field(
            "organization"
        )
        membership_field = OrganizationMessageAttribution._meta.get_field(
            "actor_membership"
        )

        self.assertIsInstance(message_field, models.OneToOneField)
        self.assertEqual(
            message_field.remote_field.related_name,
            "organization_attribution",
        )
        self.assertEqual(
            organization_field.remote_field.related_name,
            "message_attributions",
        )
        self.assertTrue(membership_field.null)
        self.assertTrue(membership_field.blank)
        self.assertIs(
            membership_field.remote_field.on_delete,
            models.SET_NULL,
        )

    def test_message_attribution_snapshot_contract(self):
        display_name = OrganizationMessageAttribution._meta.get_field(
            "actor_display_name_snapshot"
        )
        username = OrganizationMessageAttribution._meta.get_field(
            "actor_username_snapshot"
        )
        membership_public_id = (
            OrganizationMessageAttribution._meta.get_field(
                "actor_membership_public_id_snapshot"
            )
        )

        self.assertEqual(display_name.max_length, 255)
        self.assertEqual(username.max_length, 150)
        self.assertTrue(membership_public_id.null)
        self.assertTrue(membership_public_id.blank)

    def test_message_attribution_index_is_declared(self):
        indexes = {
            index.name: tuple(index.fields)
            for index in OrganizationMessageAttribution._meta.indexes
        }

        self.assertEqual(
            indexes["conv_org_attr_created_idx"],
            ("organization", "created_at"),
        )


class OrganizationMessengerPermissionDefinitionTests(SimpleTestCase):
    """Database-free permission/default-role contract tests."""

    databases = set()

    @staticmethod
    def _role_permissions():
        return {
            definition["key"]: set(definition["permissions"])
            for definition in DEFAULT_ROLE_DEFINITIONS
        }

    def test_messenger_permission_keys_are_stable(self):
        self.assertEqual(
            MESSENGER_PERMISSION_KEYS,
            {
                "organizations.messenger.view",
                "organizations.messenger.reply",
                "organizations.messenger.assign",
                "organizations.messenger.manage",
            },
        )

    def test_owner_receives_all_messenger_permissions(self):
        definitions = self._role_permissions()

        self.assertTrue(
            MESSENGER_PERMISSION_KEYS.issubset(
                definitions[OrganizationRoleKey.OWNER]
            )
        )

    def test_administrator_receives_all_messenger_permissions(self):
        definitions = self._role_permissions()

        self.assertTrue(
            MESSENGER_PERMISSION_KEYS.issubset(
                definitions[OrganizationRoleKey.ADMINISTRATOR]
            )
        )

    def test_other_default_roles_receive_no_messenger_permissions(self):
        definitions = self._role_permissions()

        for role_key, permission_keys in definitions.items():
            if role_key in {
                OrganizationRoleKey.OWNER,
                OrganizationRoleKey.ADMINISTRATOR,
            }:
                continue

            self.assertTrue(
                MESSENGER_PERMISSION_KEYS.isdisjoint(permission_keys),
                msg=(
                    f"Default role {role_key!r} unexpectedly received "
                    "Organization Messenger permissions."
                ),
            )
