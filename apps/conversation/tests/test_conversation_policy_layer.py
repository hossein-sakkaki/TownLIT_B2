# apps/conversation/tests/test_conversation_policy_layer.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.conversation.constants import (
    OrganizationConversationContextType,
    OrganizationConversationStatus,
)
from apps.conversation.policies import (
    ConversationAccessPolicy,
    ConversationAudienceKind,
    ConversationAudiencePolicy,
    ConversationContextKind,
    ConversationContextPolicy,
    ConversationContextResolutionError,
    ConversationHistoryMode,
    ConversationHistoryPolicy,
    ConversationMutationAction,
    ConversationMutationPolicy,
    ConversationSecurityMode,
    ConversationSecurityPolicy,
)
from apps.organizations.constants import (
    OrganizationMembershipStatus,
    OrganizationPermissionKey,
    OrganizationStatus,
)
from apps.organizations.services.access import (
    user_has_organization_permission,
    user_has_organization_permission_strict,
)


class _ExistsResult:
    def __init__(self, exists):
        self._exists = bool(exists)

    def exists(self):
        return self._exists


class _Participants:
    def __init__(self, user_ids):
        self._user_ids = set(user_ids)

    def filter(self, **kwargs):
        user_id = kwargs.get("id")
        return _ExistsResult(user_id in self._user_ids)


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


class ConversationPolicyLayerTests(SimpleTestCase):
    databases = set()

    def _user(self, user_id=1, *, staff=False, authenticated=True):
        return SimpleNamespace(
            id=user_id,
            is_staff=staff,
            is_authenticated=authenticated,
        )

    def _personal_dialogue(self, *, is_group, participant_ids=(1, 2)):
        return SimpleNamespace(
            is_group=is_group,
            participants=_Participants(participant_ids),
        )

    def _organization(self, *, status=OrganizationStatus.ACTIVE):
        return SimpleNamespace(
            id=50,
            status=status,
        )

    def _organization_dialogue(
        self,
        *,
        context_type,
        is_group,
        participant_user_id=None,
        participant_ids=(),
        status=OrganizationConversationStatus.OPEN,
    ):
        organization = self._organization()
        organization_context = SimpleNamespace(
            context_type=context_type,
            organization=organization,
            organization_id=organization.id,
            participant_user_id=participant_user_id,
            status=status,
        )
        return SimpleNamespace(
            is_group=is_group,
            organization_context=organization_context,
            participants=_Participants(participant_ids),
        )

    def test_context_resolves_personal_direct_without_org_context(self):
        dialogue = self._personal_dialogue(is_group=False)
        resolved = ConversationContextPolicy.resolve(dialogue)
        self.assertEqual(
            resolved.kind,
            ConversationContextKind.PERSONAL_DIRECT,
        )

    def test_context_resolves_personal_group_without_org_context(self):
        dialogue = self._personal_dialogue(is_group=True)
        resolved = ConversationContextPolicy.resolve(dialogue)
        self.assertEqual(
            resolved.kind,
            ConversationContextKind.PERSONAL_GROUP,
        )

    def test_context_resolves_organization_direct(self):
        dialogue = self._organization_dialogue(
            context_type=OrganizationConversationContextType.DIRECT,
            is_group=False,
            participant_user_id=2,
            participant_ids=(2,),
        )
        resolved = ConversationContextPolicy.resolve(dialogue)
        self.assertEqual(
            resolved.kind,
            ConversationContextKind.ORGANIZATION_DIRECT,
        )

    def test_context_resolves_members_community(self):
        dialogue = self._organization_dialogue(
            context_type=(
                OrganizationConversationContextType.MEMBERS_COMMUNITY
            ),
            is_group=True,
            participant_ids=(1, 2),
        )
        resolved = ConversationContextPolicy.resolve(dialogue)
        self.assertEqual(
            resolved.kind,
            ConversationContextKind.ORGANIZATION_MEMBERS_COMMUNITY,
        )

    def test_context_fails_closed_on_invalid_topology(self):
        dialogue = self._organization_dialogue(
            context_type=OrganizationConversationContextType.DIRECT,
            is_group=True,
            participant_user_id=2,
        )
        with self.assertRaises(ConversationContextResolutionError):
            ConversationContextPolicy.resolve(dialogue)

    def test_personal_direct_security_remains_e2ee(self):
        dialogue = self._personal_dialogue(is_group=False)
        security = ConversationSecurityPolicy.resolve(dialogue)
        self.assertEqual(
            security.mode,
            ConversationSecurityMode.END_TO_END_ENCRYPTED,
        )
        self.assertTrue(security.uses_personal_message_encryption)
        self.assertTrue(security.requires_personal_e2ee_keys)
        self.assertFalse(security.backend_readable)
        self.assertFalse(security.content_safety_eligible)

    def test_personal_group_security_remains_backend_managed(self):
        dialogue = self._personal_dialogue(is_group=True)
        security = ConversationSecurityPolicy.resolve(dialogue)
        self.assertEqual(
            security.mode,
            ConversationSecurityMode.BACKEND_MANAGED,
        )
        self.assertTrue(security.backend_readable)
        self.assertFalse(security.uses_personal_message_encryption)

    def test_organization_direct_is_not_personal_e2ee(self):
        dialogue = self._organization_dialogue(
            context_type=OrganizationConversationContextType.DIRECT,
            is_group=False,
            participant_user_id=2,
        )
        security = ConversationSecurityPolicy.resolve(dialogue)
        self.assertEqual(
            security.mode,
            ConversationSecurityMode.BACKEND_MANAGED,
        )
        self.assertTrue(security.backend_readable)
        self.assertFalse(security.uses_personal_message_encryption)
        self.assertFalse(security.requires_personal_e2ee_keys)
        self.assertTrue(security.content_safety_eligible)

    def test_personal_access_still_requires_dialogue_participation(self):
        dialogue = self._personal_dialogue(
            is_group=False,
            participant_ids=(1, 2),
        )
        self.assertTrue(
            ConversationAccessPolicy.can_view(
                dialogue=dialogue,
                user=self._user(1),
            ).allowed
        )
        self.assertFalse(
            ConversationAccessPolicy.can_view(
                dialogue=dialogue,
                user=self._user(3),
            ).allowed
        )

    @patch(
        "apps.conversation.policies.access.is_organization_verified",
        return_value=False,
    )
    def test_org_direct_participant_keeps_read_history_when_unavailable(
        self,
        _verified,
    ):
        dialogue = self._organization_dialogue(
            context_type=OrganizationConversationContextType.DIRECT,
            is_group=False,
            participant_user_id=2,
            participant_ids=(2,),
        )
        decision = ConversationAccessPolicy.can_view(
            dialogue=dialogue,
            user=self._user(2),
        )
        self.assertTrue(decision.allowed)

    @patch(
        "apps.conversation.policies.access.is_organization_verified",
        return_value=False,
    )
    def test_org_direct_participant_cannot_send_when_unavailable(
        self,
        _verified,
    ):
        dialogue = self._organization_dialogue(
            context_type=OrganizationConversationContextType.DIRECT,
            is_group=False,
            participant_user_id=2,
            participant_ids=(2,),
        )
        decision = ConversationAccessPolicy.can_send_as_self(
            dialogue=dialogue,
            user=self._user(2),
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(
            decision.code,
            "organization_messenger_unavailable",
        )

    @patch(
        "apps.conversation.policies.access.user_has_organization_permission_strict",
        return_value=True,
    )
    @patch(
        "apps.conversation.policies.access.is_organization_verified",
        return_value=True,
    )
    def test_authorized_operator_can_view_org_direct(
        self,
        _verified,
        _permission,
    ):
        dialogue = self._organization_dialogue(
            context_type=OrganizationConversationContextType.DIRECT,
            is_group=False,
            participant_user_id=2,
            participant_ids=(2,),
        )
        decision = ConversationAccessPolicy.can_view(
            dialogue=dialogue,
            user=self._user(9, staff=True),
        )
        self.assertTrue(decision.allowed)

    @patch(
        "apps.organizations.services.access.get_current_membership_for_user",
        return_value=None,
    )
    def test_strict_org_permission_does_not_grant_staff_bypass(
        self,
        _membership,
    ):
        allowed = user_has_organization_permission_strict(
            user=self._user(9, staff=True),
            organization=self._organization(),
            permission_key=OrganizationPermissionKey.VIEW_MESSENGER,
        )
        self.assertFalse(allowed)

    def test_existing_generic_org_permission_keeps_staff_behavior(self):
        allowed = user_has_organization_permission(
            user=self._user(9, staff=True),
            organization=self._organization(),
            permission_key=OrganizationPermissionKey.VIEW_ADMIN,
        )
        self.assertTrue(allowed)

    @patch(
        "apps.conversation.policies.access.user_has_organization_permission_strict",
        return_value=True,
    )
    @patch(
        "apps.conversation.policies.access.is_organization_verified",
        return_value=True,
    )
    def test_operator_reply_as_org_uses_reply_permission_path(
        self,
        _verified,
        permission_mock,
    ):
        dialogue = self._organization_dialogue(
            context_type=OrganizationConversationContextType.DIRECT,
            is_group=False,
            participant_user_id=2,
        )
        decision = ConversationAccessPolicy.can_send_as_organization(
            dialogue=dialogue,
            user=self._user(9),
        )
        self.assertTrue(decision.allowed)
        permission_keys = {
            call.kwargs["permission_key"]
            for call in permission_mock.call_args_list
        }
        self.assertIn(
            OrganizationPermissionKey.REPLY_MESSENGER,
            permission_keys,
        )

    def test_org_direct_external_message_targets_dynamic_operators(self):
        dialogue = self._organization_dialogue(
            context_type=OrganizationConversationContextType.DIRECT,
            is_group=False,
            participant_user_id=2,
        )
        audience = ConversationAudiencePolicy.for_message(
            dialogue=dialogue,
            actor=self._user(2),
            sent_as_organization=False,
        )
        self.assertEqual(
            audience.kind,
            ConversationAudienceKind.ORGANIZATION_OPERATORS,
        )
        self.assertEqual(
            audience.required_permission_key,
            OrganizationPermissionKey.VIEW_MESSENGER,
        )

    def test_org_direct_org_reply_targets_external_participant(self):
        dialogue = self._organization_dialogue(
            context_type=OrganizationConversationContextType.DIRECT,
            is_group=False,
            participant_user_id=2,
        )
        audience = ConversationAudiencePolicy.for_message(
            dialogue=dialogue,
            actor=self._user(9),
            sent_as_organization=True,
        )
        self.assertEqual(
            audience.kind,
            ConversationAudienceKind.ORGANIZATION_DIRECT_PARTICIPANT,
        )
        self.assertEqual(audience.participant_user_id, 2)

    def test_personal_audience_remains_other_participants(self):
        for is_group in (False, True):
            dialogue = self._personal_dialogue(is_group=is_group)
            audience = ConversationAudiencePolicy.for_message(
                dialogue=dialogue,
                actor=self._user(1),
            )
            self.assertEqual(
                audience.kind,
                ConversationAudienceKind.OTHER_DIALOGUE_PARTICIPANTS,
            )

    def test_only_members_community_has_join_history_boundary(self):
        personal = self._personal_dialogue(is_group=True)
        community = self._organization_dialogue(
            context_type=(
                OrganizationConversationContextType.MEMBERS_COMMUNITY
            ),
            is_group=True,
        )
        self.assertEqual(
            ConversationHistoryPolicy.mode(personal),
            ConversationHistoryMode.EXISTING_VISIBILITY,
        )
        self.assertEqual(
            ConversationHistoryPolicy.mode(community),
            ConversationHistoryMode.FROM_CURRENT_PARTICIPATION,
        )

    @patch(
        "apps.conversation.policies.history.DialogueParticipant.objects.filter"
    )
    def test_community_history_filters_from_current_joined_at(
        self,
        filter_mock,
    ):
        joined_at = object()
        filter_mock.return_value.only.return_value.first.return_value = (
            SimpleNamespace(joined_at=joined_at)
        )
        dialogue = self._organization_dialogue(
            context_type=(
                OrganizationConversationContextType.MEMBERS_COMMUNITY
            ),
            is_group=True,
            participant_ids=(1,),
        )
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

    @patch(
        "apps.conversation.policies.history.DialogueParticipant.objects.filter"
    )
    def test_community_history_is_denied_without_runtime_participation(
        self,
        filter_mock,
    ):
        dialogue = self._organization_dialogue(
            context_type=(
                OrganizationConversationContextType.MEMBERS_COMMUNITY
            ),
            is_group=True,
            participant_ids=(),
        )
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

    def test_personal_group_mutations_remain_policy_allowed(self):
        dialogue = self._personal_dialogue(is_group=True)
        for action in ConversationMutationAction:
            decision = ConversationMutationPolicy.check(
                dialogue=dialogue,
                action=action,
            )
            self.assertTrue(decision.allowed)

    def test_members_community_manual_mutations_are_policy_denied(self):
        dialogue = self._organization_dialogue(
            context_type=(
                OrganizationConversationContextType.MEMBERS_COMMUNITY
            ),
            is_group=True,
        )
        for action in ConversationMutationAction:
            decision = ConversationMutationPolicy.check(
                dialogue=dialogue,
                action=action,
            )
            self.assertFalse(decision.allowed)
            self.assertEqual(
                decision.code,
                "organization_community_system_managed",
            )

    @patch(
        "apps.conversation.policies.access.get_current_membership_for_user"
    )
    @patch(
        "apps.conversation.policies.access.is_organization_verified",
        return_value=True,
    )
    def test_community_self_send_requires_active_membership(
        self,
        _verified,
        membership_mock,
    ):
        dialogue = self._organization_dialogue(
            context_type=(
                OrganizationConversationContextType.MEMBERS_COMMUNITY
            ),
            is_group=True,
            participant_ids=(1,),
        )
        membership_mock.return_value = SimpleNamespace(
            status=OrganizationMembershipStatus.ACTIVE,
        )
        self.assertTrue(
            ConversationAccessPolicy.can_send_as_self(
                dialogue=dialogue,
                user=self._user(1),
            ).allowed
        )
        membership_mock.return_value = SimpleNamespace(
            status=OrganizationMembershipStatus.SUSPENDED,
        )
        self.assertFalse(
            ConversationAccessPolicy.can_send_as_self(
                dialogue=dialogue,
                user=self._user(1),
            ).allowed
        )
