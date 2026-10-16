# apps/conversation/tests/test_organization_direct_inbox.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-15.
#

import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import SimpleTestCase

from apps.conversation.constants import (
    OrganizationConversationStatus,
    OrganizationConversationWaitingFor,
)
from apps.conversation.policies import (
    ConversationContextKind,
    ConversationSecurityMode,
)
from apps.conversation.realtime.mixins.message import MessageMixin
from apps.conversation.serializers.message import MessageSerializer
from apps.conversation.serializers.organization.direct import (
    OrganizationDirectThreadSerializer,
)
from apps.conversation.services.message_creation import create_text_message
from apps.conversation.services.message_mutations import (
    _organization_direct_message_mutation_unavailable,
)
from apps.conversation.services.message_pins import (
    _organization_direct_feature_unavailable as pins_unavailable,
)
from apps.conversation.services.message_reactions import (
    _organization_direct_feature_unavailable as reactions_unavailable,
)
from apps.conversation.services.organization.attribution import (
    actor_display_name_snapshot,
)
from apps.conversation.services.organization.direct_access import (
    ASSIGN_PERMISSION_KEYS,
    MANAGE_PERMISSION_KEYS,
    REPLY_PERMISSION_KEYS,
    VIEW_PERMISSION_KEYS,
    organization_operator_can_view,
)
from apps.conversation.services.organization.direct_workflow import (
    membership_is_assignable_to_messenger,
    organization_reply_state,
    participant_message_state,
)
from apps.conversation.urls import urlpatterns
from apps.conversation.views.mixins.message_state import (
    _external_organization_direct_seen_payload,
)
from apps.organizations.constants import (
    OrganizationAuditAction,
    OrganizationMembershipStatus,
    OrganizationPermissionKey,
)


class _ExistsResult:
    def __init__(self, exists):
        self._exists = bool(exists)

    def exists(self):
        return self._exists


class _SeenRelation:
    def __init__(self, *, organization_seen=False):
        self.organization_seen = organization_seen
        self.values_list_called = False

    def values_list(self, *args, **kwargs):
        self.values_list_called = True
        return [99]

    def exclude(self, **kwargs):
        return _ExistsResult(self.organization_seen)


class OrganizationDirectInboxContractTests(SimpleTestCase):
    """DB-free contract tests for Phase 8F.4."""

    databases = set()

    def _direct_resolution(self, *, participant_user_id=2):
        return SimpleNamespace(
            kind=ConversationContextKind.ORGANIZATION_DIRECT,
            is_organization=True,
            organization_context=SimpleNamespace(
                participant_user_id=participant_user_id,
            ),
        )

    def _organization(self):
        return SimpleNamespace(
            id=50,
            public_id=uuid4(),
            slug="townlit-society",
            name="TownLIT Society",
            short_name="TownLIT",
            brand_color=None,
            logo=None,
            thumbnail=None,
        )

    def test_audit_action_keys_are_stable(self):
        self.assertEqual(
            OrganizationAuditAction.MESSENGER_THREAD_ASSIGNED,
            "messenger_thread_assigned",
        )
        self.assertEqual(
            OrganizationAuditAction.MESSENGER_THREAD_UNASSIGNED,
            "messenger_thread_unassigned",
        )
        self.assertEqual(
            OrganizationAuditAction.MESSENGER_THREAD_RESOLVED,
            "messenger_thread_resolved",
        )
        self.assertEqual(
            OrganizationAuditAction.MESSENGER_THREAD_REOPENED,
            "messenger_thread_reopened",
        )
        self.assertEqual(
            OrganizationAuditAction.MESSENGER_THREAD_CLOSED,
            "messenger_thread_closed",
        )

    def test_participant_message_reopens_resolved_thread(self):
        status, waiting_for, reopened = participant_message_state(
            OrganizationConversationStatus.RESOLVED
        )
        self.assertEqual(status, OrganizationConversationStatus.OPEN)
        self.assertEqual(
            waiting_for,
            OrganizationConversationWaitingFor.ORGANIZATION,
        )
        self.assertTrue(reopened)

    def test_organization_reply_reopens_resolved_thread(self):
        status, waiting_for, reopened = organization_reply_state(
            OrganizationConversationStatus.RESOLVED
        )
        self.assertEqual(status, OrganizationConversationStatus.OPEN)
        self.assertEqual(
            waiting_for,
            OrganizationConversationWaitingFor.PARTICIPANT,
        )
        self.assertTrue(reopened)

    def test_open_participant_message_updates_waiting_without_reopen(self):
        status, waiting_for, reopened = participant_message_state(
            OrganizationConversationStatus.OPEN
        )
        self.assertEqual(status, OrganizationConversationStatus.OPEN)
        self.assertEqual(
            waiting_for,
            OrganizationConversationWaitingFor.ORGANIZATION,
        )
        self.assertFalse(reopened)

    def test_messenger_permission_sets_are_separated(self):
        self.assertEqual(
            VIEW_PERMISSION_KEYS,
            (
                OrganizationPermissionKey.VIEW_MESSENGER,
                OrganizationPermissionKey.MANAGE_MESSENGER,
            ),
        )
        self.assertEqual(
            REPLY_PERMISSION_KEYS,
            (
                OrganizationPermissionKey.REPLY_MESSENGER,
                OrganizationPermissionKey.MANAGE_MESSENGER,
            ),
        )
        self.assertEqual(
            ASSIGN_PERMISSION_KEYS,
            (
                OrganizationPermissionKey.ASSIGN_MESSENGER,
                OrganizationPermissionKey.MANAGE_MESSENGER,
            ),
        )
        self.assertEqual(
            MANAGE_PERMISSION_KEYS,
            (OrganizationPermissionKey.MANAGE_MESSENGER,),
        )

    @patch(
        "apps.conversation.services.organization.direct_access."
        "user_has_organization_permission_strict",
        return_value=False,
    )
    @patch(
        "apps.conversation.services.organization.direct_access."
        "organization_messenger_is_available",
        return_value=True,
    )
    def test_platform_staff_has_no_direct_inbox_bypass(
        self,
        _availability,
        strict_permission,
    ):
        user = SimpleNamespace(id=1, is_staff=True, is_authenticated=True)
        self.assertFalse(
            organization_operator_can_view(
                user=user,
                organization=self._organization(),
            )
        )
        self.assertGreaterEqual(strict_permission.call_count, 1)

    @patch(
        "apps.conversation.services.organization.direct_workflow."
        "user_has_organization_permission_strict"
    )
    def test_assignment_target_requires_reply_capability(
        self,
        strict_permission,
    ):
        strict_permission.side_effect = lambda **kwargs: (
            kwargs["permission_key"]
            == OrganizationPermissionKey.REPLY_MESSENGER
        )
        organization = self._organization()
        user = SimpleNamespace(id=7)
        membership = SimpleNamespace(
            status=OrganizationMembershipStatus.ACTIVE,
            organization=organization,
            member=SimpleNamespace(user=user),
        )

        self.assertTrue(membership_is_assignable_to_messenger(membership))
        called_keys = {
            call.kwargs["permission_key"]
            for call in strict_permission.call_args_list
        }
        self.assertIn(
            OrganizationPermissionKey.REPLY_MESSENGER,
            called_keys,
        )
        self.assertNotIn(
            OrganizationPermissionKey.VIEW_MESSENGER,
            called_keys,
        )

    @patch(
        "apps.conversation.services.organization.direct_workflow."
        "user_has_organization_permission_strict"
    )
    def test_suspended_membership_cannot_be_assigned(
        self,
        strict_permission,
    ):
        membership = SimpleNamespace(
            status=OrganizationMembershipStatus.SUSPENDED,
        )
        self.assertFalse(membership_is_assignable_to_messenger(membership))
        strict_permission.assert_not_called()

    def test_actor_display_name_snapshot_prefers_real_name(self):
        user = SimpleNamespace(
            name="Hossein",
            family="Sakkaki",
            username="hossein",
        )
        self.assertEqual(
            actor_display_name_snapshot(user),
            "Hossein Sakkaki",
        )

    def test_actor_display_name_snapshot_falls_back_to_username(self):
        user = SimpleNamespace(
            name="",
            family="",
            username="operator-1",
        )
        self.assertEqual(
            actor_display_name_snapshot(user),
            "operator-1",
        )

    @patch(
        "apps.conversation.serializers.message."
        "ConversationContextPolicy.resolve"
    )
    def test_external_message_serializer_hides_human_org_sender(
        self,
        resolve,
    ):
        resolve.return_value = self._direct_resolution()
        organization = self._organization()
        message = SimpleNamespace(
            id=10,
            sender=SimpleNamespace(id=99),
            sender_id=99,
            dialogue=SimpleNamespace(),
            organization_attribution=SimpleNamespace(
                organization=organization,
                actor_display_name_snapshot="Internal Operator",
                actor_username_snapshot="internal",
                actor_membership_public_id_snapshot=uuid4(),
            ),
        )
        serializer = MessageSerializer(context={})

        self.assertIsNone(serializer.get_sender(message))
        self.assertEqual(serializer.get_sender_type(message), "organization")
        attribution = serializer.get_organization_attribution(message)
        self.assertEqual(
            attribution["organization"]["slug"],
            "townlit-society",
        )
        self.assertIsNone(attribution["actor"])
        self.assertIsNone(attribution["actor_display_name"])
        self.assertIsNone(attribution["actor_username"])
        self.assertIsNone(attribution["actor_membership_public_id"])

    @patch(
        "apps.conversation.serializers.message."
        "ConversationContextPolicy.resolve"
    )
    def test_external_seen_state_never_exposes_operator_ids(
        self,
        resolve,
    ):
        resolve.return_value = self._direct_resolution(participant_user_id=2)
        seen_relation = _SeenRelation(organization_seen=True)
        message = SimpleNamespace(
            id=11,
            sender_id=2,
            dialogue=SimpleNamespace(),
            seen_by_users=seen_relation,
        )
        serializer = MessageSerializer(context={})

        self.assertEqual(serializer.get_seen_by_users(message), [])
        self.assertFalse(seen_relation.values_list_called)
        self.assertTrue(serializer.get_seen_by_organization(message))
        self.assertEqual(serializer.get_seen_count(message), 1)

    @patch(
        "apps.conversation.serializers.message."
        "ConversationContextPolicy.resolve"
    )
    def test_org_direct_reactions_and_pins_render_disabled_state(
        self,
        resolve,
    ):
        resolve.return_value = self._direct_resolution()
        message = SimpleNamespace(
            id=12,
            dialogue=SimpleNamespace(),
        )
        serializer = MessageSerializer(context={})

        self.assertFalse(serializer.get_is_pinned(message))
        self.assertIsNone(serializer.get_pinned_position(message))
        self.assertEqual(
            serializer.get_reaction_summary(message),
            {
                "message_id": 12,
                "total_count": 0,
                "counts": {
                    "like": 0,
                    "dislike": 0,
                    "gratitude": 0,
                    "heart": 0,
                    "encouragement": 0,
                },
                "items": [],
                "my_reaction": None,
            },
        )

    @patch(
        "apps.conversation.services.message_creation."
        "create_backend_managed_text_message"
    )
    @patch(
        "apps.conversation.services.message_creation."
        "ConversationSecurityPolicy.resolve"
    )
    @patch(
        "apps.conversation.services.message_creation."
        "check_private_dialogue_boundary"
    )
    @patch(
        "apps.conversation.services.message_creation."
        "ConversationAccessPolicy.can_send_as_self"
    )
    @patch(
        "apps.conversation.services.message_creation."
        "ConversationContextPolicy.resolve"
    )
    def test_org_direct_text_routes_to_backend_managed_creation(
        self,
        resolve_context,
        can_send,
        boundary,
        resolve_security,
        backend_create,
    ):
        resolve_context.return_value = SimpleNamespace(is_organization=True)
        can_send.return_value = SimpleNamespace(allowed=True)
        boundary.return_value = SimpleNamespace(allowed=True)
        resolve_security.return_value = SimpleNamespace(
            mode=ConversationSecurityMode.BACKEND_MANAGED,
        )
        backend_create.return_value = {
            "ok": True,
            "payload": {"message": object()},
        }
        dialogue = SimpleNamespace(slug="d-org", is_group=False)
        sender = SimpleNamespace(id=2)

        result = create_text_message(
            dialogue=dialogue,
            sender=sender,
            is_encrypted=False,
            content="Hello Organization",
            encrypted_contents=[],
        )

        self.assertTrue(result["ok"])
        backend_create.assert_called_once_with(
            dialogue=dialogue,
            sender=sender,
            content="Hello Organization",
            reply_to_message_id=None,
        )

    @patch(
        "apps.conversation.services.message_creation."
        "ConversationSecurityPolicy.resolve"
    )
    @patch(
        "apps.conversation.services.message_creation."
        "check_private_dialogue_boundary"
    )
    @patch(
        "apps.conversation.services.message_creation."
        "ConversationContextPolicy.resolve"
    )
    def test_personal_direct_plaintext_is_still_rejected(
        self,
        resolve_context,
        boundary,
        resolve_security,
    ):
        resolve_context.return_value = SimpleNamespace(is_organization=False)
        boundary.return_value = SimpleNamespace(allowed=True)
        resolve_security.return_value = SimpleNamespace(
            mode=ConversationSecurityMode.END_TO_END_ENCRYPTED,
        )

        result = create_text_message(
            dialogue=SimpleNamespace(is_group=False),
            sender=SimpleNamespace(id=1),
            is_encrypted=False,
            content="plaintext",
            encrypted_contents=[],
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "BAD_REQUEST")
        self.assertIn("encrypted", result["message"].lower())

    @patch(
        "apps.conversation.services.message_creation."
        "ConversationSecurityPolicy.resolve"
    )
    @patch(
        "apps.conversation.services.message_creation."
        "check_private_dialogue_boundary"
    )
    @patch(
        "apps.conversation.services.message_creation."
        "ConversationContextPolicy.resolve"
    )
    def test_personal_group_encrypted_error_contract_is_preserved(
        self,
        resolve_context,
        boundary,
        resolve_security,
    ):
        resolve_context.return_value = SimpleNamespace(
            is_organization=False,
            kind=ConversationContextKind.PERSONAL_GROUP,
        )
        boundary.return_value = SimpleNamespace(allowed=True)
        resolve_security.return_value = SimpleNamespace(
            mode=ConversationSecurityMode.BACKEND_MANAGED,
        )

        result = create_text_message(
            dialogue=SimpleNamespace(is_group=True),
            sender=SimpleNamespace(id=1),
            is_encrypted=True,
            content="hello",
            encrypted_contents=[],
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "BAD_REQUEST")
        self.assertEqual(
            result["message"],
            "Group messages should not be encrypted.",
        )

    @patch(
        "apps.conversation.services.message_creation."
        "ConversationSecurityPolicy.resolve"
    )
    @patch(
        "apps.conversation.services.message_creation."
        "check_private_dialogue_boundary"
    )
    @patch(
        "apps.conversation.services.message_creation."
        "ConversationContextPolicy.resolve"
    )
    def test_personal_group_empty_content_error_contract_is_preserved(
        self,
        resolve_context,
        boundary,
        resolve_security,
    ):
        resolve_context.return_value = SimpleNamespace(
            is_organization=False,
            kind=ConversationContextKind.PERSONAL_GROUP,
        )
        boundary.return_value = SimpleNamespace(allowed=True)
        resolve_security.return_value = SimpleNamespace(
            mode=ConversationSecurityMode.BACKEND_MANAGED,
        )

        result = create_text_message(
            dialogue=SimpleNamespace(is_group=True),
            sender=SimpleNamespace(id=1),
            is_encrypted=False,
            content="",
            encrypted_contents=[],
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "BAD_REQUEST")
        self.assertEqual(
            result["message"],
            "Message content is required for group chat.",
        )

    def test_inbox_unread_annotation_avoids_per_thread_count_query(self):
        serializer = OrganizationDirectThreadSerializer(context={})
        context = SimpleNamespace(operator_unread_count=7)
        self.assertEqual(serializer.get_unread_count(context), 7)

    def test_stale_assignee_is_not_exposed_by_thread_serializer(self):
        serializer = OrganizationDirectThreadSerializer(context={})
        context = SimpleNamespace(
            assigned_to_membership=SimpleNamespace(id=77),
            has_effective_assignee=False,
        )
        self.assertIsNone(serializer.get_assigned_to(context))

    @patch(
        "apps.conversation.services.message_pins."
        "ConversationContextPolicy.resolve"
    )
    @patch(
        "apps.conversation.services.message_reactions."
        "ConversationContextPolicy.resolve"
    )
    def test_org_direct_pin_and_reaction_feature_guards(
        self,
        reaction_resolve,
        pin_resolve,
    ):
        resolution = self._direct_resolution()
        reaction_resolve.return_value = resolution
        pin_resolve.return_value = resolution
        dialogue = SimpleNamespace()

        self.assertTrue(reactions_unavailable(dialogue))
        self.assertTrue(pins_unavailable(dialogue))

    @patch(
        "apps.conversation.views.mixins.message_state."
        "ConversationContextPolicy.resolve"
    )
    def test_seen_by_endpoint_helper_returns_aggregate_only(
        self,
        resolve,
    ):
        resolve.return_value = self._direct_resolution(participant_user_id=2)
        seen_relation = _SeenRelation(organization_seen=True)
        message = SimpleNamespace(
            sender_id=2,
            dialogue=SimpleNamespace(),
            seen_by_users=seen_relation,
        )

        payload = _external_organization_direct_seen_payload(
            message=message,
            user=SimpleNamespace(id=2),
        )

        self.assertEqual(payload, {"seen_by_organization": True})
        self.assertFalse(seen_relation.values_list_called)

    @patch(
        "apps.conversation.services.message_mutations."
        "ConversationContextPolicy.resolve"
    )
    def test_org_direct_edit_and_permanent_delete_guard_is_active(
        self,
        resolve,
    ):
        resolve.return_value = self._direct_resolution()
        self.assertTrue(
            _organization_direct_message_mutation_unavailable(
                SimpleNamespace()
            )
        )

    def test_org_direct_websocket_creation_is_context_aware_in_8f5(self):
        source = inspect.getsource(MessageMixin.handle_message)
        self.assertIn("send_organization_direct_participant_message", source)
        self.assertIn("send_organization_direct_reply", source)
        self.assertNotIn("ORGANIZATION_DIRECT_REST_REQUIRED", source)

    def test_personal_websocket_creation_remains_available(self):
        source = inspect.getsource(MessageMixin.handle_message)
        self.assertIn("is_sender_device_verified", source)
        self.assertIn("create_text_message", source)
        self.assertIn("_broadcast_dm_message", source)

    def test_organization_direct_routes_are_declared(self):
        route_names = {
            pattern.name
            for pattern in urlpatterns
            if getattr(pattern, "name", None)
        }
        expected = {
            "organization-direct-participant-conversation",
            "organization-direct-participant-message",
            "organization-direct-participant-read",
            "organization-direct-inbox",
            "organization-direct-inbox-unread-count",
            "organization-direct-operator-conversation",
            "organization-direct-operator-reply",
            "organization-direct-operator-read",
            "organization-direct-operator-assign",
            "organization-direct-operator-resolve",
            "organization-direct-operator-reopen",
            "organization-direct-operator-close",
        }
        self.assertTrue(expected.issubset(route_names))


class OrganizationDirectInboxTestIsolationTests(SimpleTestCase):
    databases = set()

    def test_suite_is_explicitly_database_free(self):
        self.assertEqual(
            OrganizationDirectInboxContractTests.databases,
            set(),
        )

