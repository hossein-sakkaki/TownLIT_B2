# apps/conversation/tests/test_managed_members_community.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-16.
#

import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.conversation.constants import (
    PARTICIPANT,
    OrganizationConversationContextType,
)
from apps.conversation.integrations.organization import (
    _schedule_membership_reconciliation,
    _schedule_organization_reconciliation,
)
from apps.conversation.policies import ConversationHistoryPolicy
from apps.conversation.services.group_domain import add_group_participant
from apps.conversation.services.message_creation import create_file_message
from apps.conversation.services.message_forward import (
    _organization_forwarding_not_available,
)
from apps.conversation.services.organization.availability import (
    organization_messenger_is_available,
)
from apps.conversation.services.organization.members_community import (
    MembersCommunityReconciliationResult,
    members_community_fallback_name,
)
from apps.conversation.services.organization.membership_sync import (
    CommunityMembershipSyncResult,
    _ensure_history_participant,
    _grant_runtime_access,
    _remove_membership_state,
    _suspend_runtime_access,
)
from apps.organizations.constants import OrganizationStatus


class _ExistsResult:
    def __init__(self, exists):
        self._exists = bool(exists)

    def exists(self):
        return self._exists


class _UserRelation:
    def __init__(self, user_ids=()):
        self.user_ids = set(user_ids)
        self.added = []
        self.removed = []

    def filter(self, **kwargs):
        return _ExistsResult(kwargs.get("id") in self.user_ids)

    def add(self, user):
        self.user_ids.add(user.id)
        self.added.append(user.id)

    def remove(self, user):
        self.user_ids.discard(user.id)
        self.removed.append(user.id)


class _DeletedRelation:
    def __init__(self):
        self.removed = []

    def remove(self, user):
        self.removed.append(user.id)


class _FakeQuerySet:
    def __init__(self):
        self.filters = []
        self.none_called = False

    def filter(self, **kwargs):
        self.filters.append(kwargs)
        return self

    def none(self):
        self.none_called = True
        return self


class ManagedMembersCommunityContractTests(SimpleTestCase):
    """DB-free contract tests for Phase 8F.3."""

    databases = set()

    def _user(self, user_id=1):
        return SimpleNamespace(id=user_id)

    def _organization(self, *, status=OrganizationStatus.ACTIVE, name="TownLIT Society"):
        return SimpleNamespace(
            id=50,
            status=status,
            name=name,
        )

    def _community_dialogue(self, *, runtime_user_ids=()):
        organization = self._organization()
        return SimpleNamespace(
            id=70,
            is_group=True,
            organization_context=SimpleNamespace(
                context_type=(
                    OrganizationConversationContextType.MEMBERS_COMMUNITY
                ),
                organization=organization,
                organization_id=organization.id,
                participant_user_id=None,
            ),
            participants=_UserRelation(runtime_user_ids),
            deleted_by_users=_DeletedRelation(),
        )

    @patch(
        "apps.conversation.services.organization.availability."
        "is_organization_verified",
        return_value=True,
    )
    def test_active_verified_organization_is_messenger_available(
        self,
        verified_mock,
    ):
        organization = self._organization()

        self.assertTrue(
            organization_messenger_is_available(organization)
        )
        verified_mock.assert_called_once_with(
            organization=organization,
            now=None,
        )

    @patch(
        "apps.conversation.services.organization.availability."
        "is_organization_verified"
    )
    def test_inactive_organization_is_not_messenger_available(
        self,
        verified_mock,
    ):
        organization = self._organization(status="suspended")

        self.assertFalse(
            organization_messenger_is_available(organization)
        )
        verified_mock.assert_not_called()

    def test_members_community_fallback_name_is_stable(self):
        organization = self._organization(
            name="  TownLIT   Society  ",
        )

        self.assertEqual(
            members_community_fallback_name(organization),
            "TownLIT Society · Members",
        )
        self.assertEqual(
            members_community_fallback_name(
                SimpleNamespace(name="")
            ),
            "Organization · Members",
        )

    def test_reconciliation_result_defaults_are_safe(self):
        result = MembersCommunityReconciliationResult(
            context=None,
            available=False,
        )

        self.assertFalse(result.available)
        self.assertFalse(result.created)
        self.assertEqual(result.added_count, 0)
        self.assertEqual(result.removed_count, 0)
        self.assertEqual(result.updated_count, 0)
        self.assertEqual(result.member_count, 0)

    @patch(
        "apps.conversation.policies.history."
        "DialogueParticipant.objects.filter"
    )
    def test_history_boundary_starts_at_current_participation(
        self,
        filter_mock,
    ):
        joined_at = object()
        filter_mock.return_value.only.return_value.first.return_value = (
            SimpleNamespace(joined_at=joined_at)
        )
        dialogue = self._community_dialogue(runtime_user_ids=(1,))
        queryset = _FakeQuerySet()

        result = ConversationHistoryPolicy.apply_visibility_boundary(
            dialogue=dialogue,
            user=self._user(1),
            queryset=queryset,
        )

        self.assertIs(result, queryset)
        self.assertIn(
            {"timestamp__gte": joined_at},
            queryset.filters,
        )
        self.assertFalse(queryset.none_called)

    @patch(
        "apps.conversation.policies.history."
        "DialogueParticipant.objects.filter"
    )
    def test_suspended_runtime_access_cannot_read_community_history(
        self,
        filter_mock,
    ):
        dialogue = self._community_dialogue(runtime_user_ids=())
        queryset = _FakeQuerySet()

        result = ConversationHistoryPolicy.apply_visibility_boundary(
            dialogue=dialogue,
            user=self._user(1),
            queryset=queryset,
        )

        self.assertIs(result, queryset)
        self.assertTrue(queryset.none_called)
        self.assertEqual(queryset.filters, [])
        filter_mock.assert_not_called()

    @patch(
        "apps.conversation.services.organization.membership_sync."
        "_dispatch_membership_event_after_commit"
    )
    def test_grant_runtime_access_does_not_replace_history_boundary(
        self,
        dispatch_mock,
    ):
        user = self._user(1)
        dialogue = self._community_dialogue(runtime_user_ids=())

        added = _grant_runtime_access(
            dialogue=dialogue,
            user=user,
            emit_event=True,
        )

        self.assertTrue(added)
        self.assertEqual(dialogue.participants.added, [1])
        self.assertEqual(dialogue.deleted_by_users.removed, [1])
        dispatch_mock.assert_called_once_with(
            dialogue=dialogue,
            user_id=1,
            added=True,
        )

    @patch(
        "apps.conversation.services.organization.membership_sync."
        "_dispatch_membership_event_after_commit"
    )
    def test_grant_runtime_access_is_idempotent(
        self,
        dispatch_mock,
    ):
        user = self._user(1)
        dialogue = self._community_dialogue(runtime_user_ids=(1,))

        added = _grant_runtime_access(
            dialogue=dialogue,
            user=user,
            emit_event=True,
        )

        self.assertFalse(added)
        self.assertEqual(dialogue.participants.added, [])
        dispatch_mock.assert_not_called()

    @patch(
        "apps.conversation.services.organization.membership_sync."
        "_dispatch_membership_event_after_commit"
    )
    def test_verification_suspension_removes_only_runtime_access(
        self,
        dispatch_mock,
    ):
        user = self._user(1)
        dialogue = self._community_dialogue(runtime_user_ids=(1,))

        removed = _suspend_runtime_access(
            dialogue=dialogue,
            user=user,
            emit_event=True,
        )

        self.assertTrue(removed)
        self.assertEqual(dialogue.participants.removed, [1])
        dispatch_mock.assert_called_once_with(
            dialogue=dialogue,
            user_id=1,
            added=False,
        )

    @patch(
        "apps.conversation.services.organization.membership_sync."
        "DialogueParticipant.objects.get_or_create"
    )
    def test_history_participant_is_canonical_normal_member_role(
        self,
        get_or_create_mock,
    ):
        participant = SimpleNamespace(
            role="elder",
            save=MagicMock(),
        )
        get_or_create_mock.return_value = (participant, False)
        user = self._user(1)
        membership = SimpleNamespace(
            member=SimpleNamespace(user=user),
        )
        dialogue = self._community_dialogue()

        returned, created, role_updated = _ensure_history_participant(
            dialogue=dialogue,
            membership=membership,
        )

        self.assertIs(returned, participant)
        self.assertFalse(created)
        self.assertTrue(role_updated)
        self.assertEqual(participant.role, PARTICIPANT)
        participant.save.assert_called_once_with(
            update_fields=["role"],
        )

    @patch(
        "apps.conversation.services.organization.membership_sync."
        "_dispatch_membership_event_after_commit"
    )
    @patch(
        "apps.conversation.services.organization.membership_sync."
        "UserDialogueMarker.objects.filter"
    )
    @patch(
        "apps.conversation.services.organization.membership_sync."
        "DialoguePin.objects.filter"
    )
    @patch(
        "apps.conversation.services.organization.membership_sync."
        "DialogueParticipant.objects.filter"
    )
    def test_membership_loss_resets_history_and_user_scoped_state(
        self,
        participant_filter_mock,
        pin_filter_mock,
        marker_filter_mock,
        dispatch_mock,
    ):
        participant_qs = MagicMock()
        participant_qs.delete.return_value = (1, {})
        participant_filter_mock.return_value = participant_qs

        pin_qs = MagicMock()
        pin_filter_mock.return_value = pin_qs

        marker_qs = MagicMock()
        marker_filter_mock.return_value = marker_qs

        user = self._user(1)
        dialogue = self._community_dialogue(runtime_user_ids=(1,))

        result = _remove_membership_state(
            dialogue=dialogue,
            user=user,
            emit_event=True,
        )

        self.assertIsInstance(result, CommunityMembershipSyncResult)
        self.assertTrue(result.removed)
        self.assertTrue(result.participant_removed)
        participant_qs.delete.assert_called_once_with()
        pin_qs.delete.assert_called_once_with()
        marker_qs.delete.assert_called_once_with()
        self.assertEqual(dialogue.participants.removed, [1])
        self.assertEqual(dialogue.deleted_by_users.removed, [1])
        dispatch_mock.assert_called_once_with(
            dialogue=dialogue,
            user_id=1,
            added=False,
        )

    def test_normal_group_member_management_is_denied_for_community(self):
        dialogue = self._community_dialogue(runtime_user_ids=(1,))

        result = add_group_participant(
            dialogue=dialogue,
            acting_user=self._user(1),
            target_user=self._user(2),
        )

        self.assertFalse(result["ok"])
        self.assertEqual(
            result["code"],
            "organization_community_system_managed",
        )
        self.assertEqual(result["status"], 403)

    def test_organization_community_uses_shared_backend_managed_media_path(self):
        source = inspect.getsource(create_file_message)
        self.assertIn("ConversationSecurityMode.BACKEND_MANAGED", source)
        self.assertIn("enforce_backend_readable_message_media_content_safety", source)
        self.assertNotIn("ORGANIZATION_MEDIA_NOT_AVAILABLE", source)

    def test_forwarding_touching_organization_context_is_blocked(self):
        community = self._community_dialogue(runtime_user_ids=(1,))
        personal_group = SimpleNamespace(
            is_group=True,
            participants=_UserRelation((1, 2)),
        )
        source_message = SimpleNamespace(dialogue=community)

        self.assertTrue(
            _organization_forwarding_not_available(
                source_message=source_message,
                target_dialogue=personal_group,
            )
        )
        self.assertTrue(
            _organization_forwarding_not_available(
                source_message=SimpleNamespace(
                    dialogue=personal_group,
                ),
                target_dialogue=community,
            )
        )

    @patch(
        "apps.conversation.integrations.organization.transaction.on_commit"
    )
    @patch(
        "apps.conversation.integrations.organization._reconcile_organization"
    )
    def test_organization_lifecycle_reconciliation_is_on_commit(
        self,
        reconcile_mock,
        on_commit_mock,
    ):
        _schedule_organization_reconciliation(
            50,
            emit_visibility_event=True,
        )

        on_commit_mock.assert_called_once()
        callback = on_commit_mock.call_args.args[0]
        callback()
        reconcile_mock.assert_called_once_with(
            50,
            emit_visibility_event=True,
        )

    @patch(
        "apps.conversation.integrations.organization.transaction.on_commit"
    )
    @patch(
        "apps.conversation.integrations.organization._reconcile_organization_user"
    )
    def test_membership_reconciliation_is_on_commit(
        self,
        reconcile_mock,
        on_commit_mock,
    ):
        _schedule_membership_reconciliation(50, 7)

        on_commit_mock.assert_called_once()
        callback = on_commit_mock.call_args.args[0]
        callback()
        reconcile_mock.assert_called_once_with(50, 7)

    @patch(
        "apps.conversation.integrations.organization.transaction.on_commit"
    )
    def test_missing_lifecycle_identity_does_not_schedule_work(
        self,
        on_commit_mock,
    ):
        _schedule_organization_reconciliation(None)
        _schedule_membership_reconciliation(50, None)
        _schedule_membership_reconciliation(None, 7)

        on_commit_mock.assert_not_called()

