# apps/conversation/tests/test_realtime_push_backend_regression.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-16.
#

import inspect
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase

from apps.conversation.apps import ConversationConfig
from apps.conversation.models import (
    OrganizationDialogueContext,
    OrganizationMessageAttribution,
)
from apps.conversation.realtime.handler import ConversationHandler
from apps.conversation.realtime.mixins.delivery import DeliveryMixin
from apps.conversation.realtime.mixins.edits import EditDeleteMixin
from apps.conversation.realtime.mixins.files import FileEventsMixin
from apps.conversation.realtime.mixins.message import MessageMixin
from apps.conversation.realtime.mixins.read import ReadMixin
from apps.conversation.realtime.mixins.typing import TypingMixin
from apps.conversation.services.organization import direct_notifications, direct_realtime
from apps.conversation.services.organization.direct_messages import (
    mark_organization_direct_read_for_operator,
    send_organization_direct_participant_message,
    send_organization_direct_reply,
)
from apps.conversation.services.organization.direct_workflow import (
    assign_organization_direct_thread,
    transition_organization_direct_thread,
)
from apps.conversation.services.read_delivery import (
    mark_dialogue_read_for_user,
    mark_message_delivered_for_user,
)
from apps.conversation.tasks import delivery as delivery_tasks
from apps.notifications.signals import messages_signals
from apps.organizations.constants import OrganizationPermissionKey


class RealtimePushBackendRegressionContractTests(SimpleTestCase):
    """DB-free contracts for Phase 8F.5 backend closure."""

    databases = set()

    def _organization(self):
        return SimpleNamespace(
            id=50,
            public_id=uuid4(),
            slug="townlit-society",
            name="TownLIT Society",
            short_name="TownLIT",
            brand_color=None,
        )

    def _user(self, user_id, username):
        return SimpleNamespace(
            id=user_id,
            username=username,
            email=f"{username}@example.com",
            name=username.title(),
            family="User",
            avatar_url=None,
            avatar_cdn_url=None,
            avatar_version=1,
            is_verified_identity=False,
            is_townlit_verified=False,
        )

    def _message(self, *, attributed):
        organization = self._organization()
        participant = self._user(2, "participant")
        operator = self._user(9, "operator")
        organization_context = SimpleNamespace(
            context_type="direct",
            status="open",
            waiting_for="participant" if attributed else "organization",
            organization=organization,
            participant_user=participant,
            participant_user_id=participant.id,
        )
        dialogue = SimpleNamespace(
            slug="d-org-direct",
            organization_context=organization_context,
        )
        attribution = None
        if attributed:
            attribution = SimpleNamespace(
                organization=organization,
                actor_display_name_snapshot="Operator User",
                actor_username_snapshot="operator",
                actor_membership_public_id_snapshot=uuid4(),
            )
        return SimpleNamespace(
            id=101,
            dialogue=dialogue,
            sender=operator if attributed else participant,
            sender_id=operator.id if attributed else participant.id,
            content_encrypted="SGVsbG8=",
            timestamp=datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc),
            is_delivered=False,
            is_system=False,
            system_event=None,
            reply_to_id=None,
            organization_attribution=attribution,
        )

    def test_conversation_ready_registers_organization_integration(self):
        source = inspect.getsource(ConversationConfig.ready)
        self.assertIn("apps.conversation.signals", source)
        self.assertIn("apps.conversation.integrations.organization", source)

    def test_org_direct_websocket_text_is_enabled(self):
        source = inspect.getsource(MessageMixin.handle_message)
        self.assertIn("send_organization_direct_participant_message", source)
        self.assertIn("send_organization_direct_reply", source)
        self.assertNotIn("ORGANIZATION_DIRECT_REST_REQUIRED", source)

    def test_org_direct_websocket_rejects_personal_dm_envelopes(self):
        source = inspect.getsource(MessageMixin.handle_message)
        self.assertIn("ORGANIZATION_DIRECT_BACKEND_MANAGED", source)
        self.assertIn("is_encrypted", source)

    def test_personal_dm_pop_and_e2ee_path_remain_present(self):
        source = inspect.getsource(MessageMixin.handle_message)
        self.assertIn("is_sender_device_verified", source)
        self.assertIn("create_text_message", source)
        self.assertIn("_broadcast_dm_message", source)

    def test_context_aware_realtime_access_is_used_for_websocket_send(self):
        source = inspect.getsource(MessageMixin.handle_message)
        self.assertIn("get_dialogue_for_user", source)
        self.assertNotIn("participants=self.user", source)

    @patch(
        "apps.conversation.services.organization.direct_realtime.build_reply_preview",
        return_value=None,
    )
    def test_external_realtime_payload_redacts_human_operator(self, _preview):
        message = self._message(attributed=True)
        payload = direct_realtime.build_organization_direct_message_payload(
            message=message,
            viewer=message.dialogue.organization_context.participant_user,
            operator_view=False,
        )
        self.assertEqual(payload["sender_type"], "organization")
        self.assertIsNone(payload["sender"])
        self.assertIsNone(payload["organization_attribution"]["actor"])
        self.assertIsNone(
            payload["organization_attribution"]["actor_display_name"]
        )
        self.assertEqual(
            payload["organization_attribution"]["organization"]["slug"],
            "townlit-society",
        )

    @patch(
        "apps.conversation.services.organization.direct_realtime.build_reply_preview",
        return_value=None,
    )
    def test_operator_realtime_payload_keeps_internal_attribution(self, _preview):
        message = self._message(attributed=True)
        payload = direct_realtime.build_organization_direct_message_payload(
            message=message,
            viewer=message.sender,
            operator_view=True,
        )
        attribution = payload["organization_attribution"]
        self.assertEqual(attribution["actor"]["id"], message.sender.id)
        self.assertEqual(attribution["actor_display_name"], "Operator User")
        self.assertEqual(attribution["actor_username"], "operator")

    @patch(
        "apps.conversation.services.organization.direct_realtime.build_reply_preview",
        return_value=None,
    )
    def test_participant_origin_realtime_payload_keeps_participant_identity(self, _preview):
        message = self._message(attributed=False)
        payload = direct_realtime.build_organization_direct_message_payload(
            message=message,
            viewer=message.sender,
            operator_view=True,
        )
        self.assertEqual(payload["sender_type"], "user")
        self.assertEqual(payload["sender"]["id"], message.sender.id)
        self.assertIsNone(payload["organization_attribution"])

    def test_operator_fanout_is_user_targeted_not_dialogue_membership(self):
        source = inspect.getsource(
            direct_realtime.dispatch_organization_direct_message_realtime
        )
        self.assertIn("conversation_user_group_name", source)
        self.assertIn("organization_direct_operator_user_ids", source)
        self.assertNotIn("dialogue.participants.add", source)

    def test_operator_resolution_requires_org_messenger_permissions(self):
        source = inspect.getsource(
            direct_realtime.organization_direct_operator_user_ids
        )
        self.assertIn("VIEW_MESSENGER", source)
        self.assertIn("MANAGE_MESSENGER", source)
        self.assertNotIn("is_staff", source)

    def test_push_reuses_existing_direct_message_type(self):
        source = inspect.getsource(
            direct_notifications.notify_organization_direct_message_push
        )
        self.assertIn('notif_type="new_message_direct"', source)
        self.assertNotIn("Notification.objects", source)
        self.assertIn("dispatch_push_only_notification", source)

    def test_external_push_never_uses_human_operator_as_actor(self):
        source = inspect.getsource(
            direct_notifications.notify_organization_direct_message_push
        )
        self.assertIn("actor=None", source)
        self.assertIn("replied to your message", source)
        self.assertNotIn("actor_display_name_snapshot", source)

    def test_participant_message_push_targets_dynamic_operators(self):
        source = inspect.getsource(
            direct_notifications.notify_organization_direct_message_push
        )
        self.assertIn("organization_direct_operator_users", source)
        self.assertIn("sent a message to", source)
        self.assertIn("organization_workspace", source)

    def test_generic_notification_signal_delegates_org_direct_after_commit(self):
        source = inspect.getsource(messages_signals.on_message_created)
        self.assertIn("ConversationContextKind.ORGANIZATION_DIRECT", source)
        self.assertIn("transaction.on_commit", source)
        self.assertIn("notify_organization_direct_message_push", source)

    def test_generic_notification_signal_preserves_personal_group_path(self):
        source = inspect.getsource(messages_signals.on_message_created)
        self.assertIn("dialogue.participants.exclude", source)
        self.assertIn("new_message_group", source)
        self.assertIn("new_message_direct", source)
        self.assertIn("build_messenger_message", source)

    def test_reconnect_replay_uses_privacy_safe_org_payload(self):
        source = inspect.getsource(ConversationHandler._build_replay_payload)
        self.assertIn("ConversationContextKind.ORGANIZATION_DIRECT", source)
        self.assertIn("build_organization_direct_message_payload", source)

    def test_org_operator_specific_socket_is_validated_without_group_join(self):
        source = inspect.getsource(ConversationHandler.connect)
        self.assertIn("get_dialogue_for_user", source)
        self.assertIn("ORGANIZATION_DIRECT", source)
        self.assertIn("not added to persistent dialogue groups", source)

    def test_reconnect_org_direct_replay_uses_user_group_not_dm_device_group(self):
        source = inspect.getsource(ConversationHandler._push_undelivered_messages)
        self.assertIn("ConversationContextKind.ORGANIZATION_DIRECT", source)
        self.assertIn('f"user_{self.user.id}"', source)
        self.assertIn('f"user_device_{self.user.id}_{self.device_id}"', source)

    def test_handler_forwards_all_org_direct_backend_events(self):
        source = inspect.getsource(ConversationHandler.handle_backend_event)
        for event_name in (
            "organization_messenger_unread_update",
            "organization_direct_thread_updated",
            "organization_direct_read",
            "organization_direct_seen",
            "organization_direct_delivery",
        ):
            self.assertIn(event_name, source)

    def test_reconnect_sends_authoritative_workspace_unread_snapshot(self):
        source = inspect.getsource(ReadMixin.send_unread_counts)
        self.assertIn("organization_messenger_unread_snapshot_for_user", source)
        self.assertIn("organization_messenger_unread_update", source)

    def test_operator_unread_snapshot_is_authoritative_not_increment_only(self):
        source = inspect.getsource(
            direct_realtime.organization_messenger_unread_snapshot_for_user
        )
        self.assertIn('"mode": "snapshot"', source)
        self.assertIn("organization_direct_total_unread_count", source)

    def test_external_read_receipt_is_aggregate_only(self):
        source = inspect.getsource(
            direct_realtime.dispatch_organization_direct_read_realtime
        )
        self.assertIn('"seen_by_organization": True', source)
        self.assertNotIn('"operator_user_id"', source)
        self.assertNotIn('"operator_username"', source)

    def test_delivery_ack_to_organization_does_not_expose_operator_identity(self):
        read_source = inspect.getsource(mark_message_delivered_for_user)
        mixin_source = inspect.getsource(DeliveryMixin.handle_mark_as_delivered)
        self.assertIn('"delivered_to_organization": acting_is_operator', read_source)
        self.assertIn("organization_direct_delivery", mixin_source)
        self.assertNotIn('"operator_user_id"', mixin_source)

    def test_legacy_offline_dm_task_skips_organization_direct(self):
        deliver_source = inspect.getsource(delivery_tasks.deliver_offline_message)
        retry_source = inspect.getsource(delivery_tasks.retry_undelivered_messages)
        self.assertIn("ConversationContextKind.ORGANIZATION_DIRECT", deliver_source)
        self.assertIn("Context-aware realtime owns delivery", deliver_source)
        self.assertIn("ConversationContextKind.ORGANIZATION_DIRECT", retry_source)

    def test_org_direct_typing_is_fail_closed_to_protect_operator_identity(self):
        source = inspect.getsource(TypingMixin.handle_typing_status)
        self.assertIn("get_dialogue_for_user", source)
        self.assertIn("ConversationContextKind.ORGANIZATION_DIRECT", source)
        self.assertIn("internal identity", source)

    def test_org_direct_media_uses_rest_finalization_and_hides_transient_identity(self):
        helper_source = inspect.getsource(FileEventsMixin._is_organization_direct)
        file_source = inspect.getsource(FileEventsMixin.handle_file_message)
        status_source = inspect.getsource(FileEventsMixin.send_file_status)
        recording_source = inspect.getsource(FileEventsMixin.handle_recording_status)

        self.assertIn("ConversationContextKind.ORGANIZATION_DIRECT", helper_source)
        self.assertIn("REST", file_source)
        self.assertIn("local-only", status_source)
        self.assertIn("intentionally hidden", recording_source)
        self.assertNotIn("ORGANIZATION_DIRECT_MEDIA_UNAVAILABLE", file_source)

    def test_org_operator_cannot_soft_delete_shared_history_over_websocket(self):
        source = inspect.getsource(EditDeleteMixin.handle_soft_delete_message)
        self.assertIn("ORGANIZATION_DIRECT_MUTATION_UNAVAILABLE", source)
        self.assertIn("participant_user_id", source)
        self.assertIn("get_dialogue_for_user", source)

    def test_rest_and_websocket_send_share_direct_services(self):
        participant_source = inspect.getsource(
            send_organization_direct_participant_message
        )
        reply_source = inspect.getsource(send_organization_direct_reply)
        ws_source = inspect.getsource(MessageMixin.handle_message)
        self.assertIn("schedule_organization_direct_message_realtime", participant_source)
        self.assertIn("schedule_organization_direct_message_realtime", reply_source)
        self.assertIn("send_organization_direct_participant_message", ws_source)
        self.assertIn("send_organization_direct_reply", ws_source)

    def test_direct_read_service_schedules_realtime_for_rest_and_ws(self):
        source = inspect.getsource(mark_dialogue_read_for_user)
        self.assertIn("schedule_organization_direct_read_realtime", source)
        self.assertIn("reader_is_operator", source)

    def test_operator_read_payload_is_json_safe(self):
        source = inspect.getsource(
            mark_organization_direct_read_for_operator
        )
        self.assertIn('"read_messages"', source)
        self.assertNotIn('"context": context', source)

    def test_assignment_and_lifecycle_schedule_thread_updates(self):
        assign_source = inspect.getsource(assign_organization_direct_thread)
        transition_source = inspect.getsource(transition_organization_direct_thread)
        self.assertIn("_schedule_thread_update", assign_source)
        self.assertIn("assignment_changed", assign_source)
        self.assertIn("_schedule_thread_update", transition_source)
        self.assertIn("lifecycle_changed", transition_source)

    def test_no_parallel_org_message_models_were_introduced(self):
        self.assertEqual(OrganizationDialogueContext._meta.app_label, "conversation")
        self.assertEqual(OrganizationMessageAttribution._meta.app_label, "conversation")
        self.assertNotEqual(
            OrganizationDialogueContext._meta.model_name,
            "organizationconversationmessage",
        )

    def test_permission_key_contract_remains_stable(self):
        self.assertEqual(
            OrganizationPermissionKey.VIEW_MESSENGER,
            "organizations.messenger.view",
        )
        self.assertEqual(
            OrganizationPermissionKey.REPLY_MESSENGER,
            "organizations.messenger.reply",
        )
        self.assertEqual(
            OrganizationPermissionKey.ASSIGN_MESSENGER,
            "organizations.messenger.assign",
        )
        self.assertEqual(
            OrganizationPermissionKey.MANAGE_MESSENGER,
            "organizations.messenger.manage",
        )


class RealtimePushBackendRegressionIsolationTests(SimpleTestCase):
    databases = set()

    def test_suite_is_explicitly_database_free(self):
        self.assertEqual(self.databases, set())

