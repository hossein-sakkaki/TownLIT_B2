
# apps/conversation/tests/test_organization_messenger_production.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-17.
# Last Update by Hossein Sakkaki on 2026-10-19.
#

from __future__ import annotations

import base64
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.core.cache import caches
from django.test import SimpleTestCase, override_settings

from apps.conversation.policies import ConversationSecurityMode
from apps.conversation.services.message_creation import (
    create_backend_managed_text_message,
    create_file_message,
    validate_upload_input,
)
from apps.conversation.services.message_idempotency import (
    normalize_client_request_id,
)
from apps.conversation.services.organization.direct_messages import (
    send_organization_direct_participant_message,
    send_organization_direct_reply,
)
from apps.conversation.services.rate_limits import (
    MessengerSendRateThrottle,
    check_messenger_rate_limit,
)
from validators.mediaValidators.conversation_upload_limits import (
    validate_conversation_media_size,
)


TEXT_SERVICE = "apps.conversation.services.message_creation"
PARTICIPANT_SERVICE = "apps.conversation.services.organization.direct_messages"


class OrganizationMessengerProductionContractTests(SimpleTestCase):
    """Database-free contracts. ORM and workflow mutations are mocked."""

    databases = set()

    @staticmethod
    def _dialogue():
        return SimpleNamespace(slug="org-test-dialogue", is_group=False)

    @staticmethod
    def _actor():
        return SimpleNamespace(pk=42, id=42, is_authenticated=True)

    @staticmethod
    def _message(*, content="Hello Organization", reply_to_id=None):
        return SimpleNamespace(
            id=101,
            content_encrypted=base64.b64encode(content.encode("utf-8")),
            reply_to_id=reply_to_id,
            is_system=False,
            image=None,
            video=None,
            audio=None,
            file=None,
        )

    def test_client_request_id_normalization(self):
        request_id = uuid4()
        self.assertEqual(normalize_client_request_id(str(request_id)), request_id)
        self.assertEqual(normalize_client_request_id(request_id), request_id)
        self.assertIsNone(normalize_client_request_id(None))
        self.assertIsNone(normalize_client_request_id("  "))
        with self.assertRaises(ValueError):
            normalize_client_request_id("not-a-uuid")

    def test_server_media_size_limits_and_boundaries(self):
        limits = {
            "image": ("CONVERSATION_MEDIA_IMAGE_MAX_BYTES", 20),
            "video": ("CONVERSATION_MEDIA_VIDEO_MAX_BYTES", 250),
            "audio": ("CONVERSATION_MEDIA_AUDIO_MAX_BYTES", 35),
            "file": ("CONVERSATION_MEDIA_FILE_MAX_BYTES", 50),
        }
        for kind, (setting, megabytes) in limits.items():
            maximum = megabytes * 1024 * 1024
            with self.subTest(kind=kind), override_settings(**{setting: maximum}):
                allowed = validate_conversation_media_size(
                    uploaded_file=SimpleNamespace(size=maximum),
                    field_name=kind,
                )
                rejected = validate_conversation_media_size(
                    uploaded_file=SimpleNamespace(size=maximum + 1),
                    field_name=kind,
                )
                empty = validate_conversation_media_size(
                    uploaded_file=SimpleNamespace(size=0),
                    field_name=kind,
                )
                self.assertTrue(allowed["ok"])
                self.assertFalse(rejected["ok"])
                self.assertEqual(rejected["code"], "FILE_TOO_LARGE")
                self.assertEqual(rejected["status"], 413)
                self.assertFalse(empty["ok"])
                self.assertEqual(empty["code"], "EMPTY_FILE")

    @override_settings(CONVERSATION_MEDIA_IMAGE_MAX_BYTES=20 * 1024 * 1024)
    def test_upload_api_reuses_shared_mime_and_size_validation(self):
        uploaded = SimpleNamespace(
            name="photo.jpg",
            content_type="image/jpeg",
            size=20 * 1024 * 1024 + 1,
        )
        with (
            patch(f"{TEXT_SERVICE}.is_unsafe_file", return_value=False),
            patch(f"{TEXT_SERVICE}.validate_file_type", return_value="image") as mime,
        ):
            result = validate_upload_input(uploaded_file=uploaded)
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "FILE_TOO_LARGE")
        self.assertEqual(result["status"], 413)
        mime.assert_called_once_with("photo.jpg", "image/jpeg")

    def test_backend_text_replay_returns_same_message_without_new_write(self):
        dialogue = self._dialogue()
        sender = self._actor()
        existing = self._message()
        with (
            patch(
                f"{TEXT_SERVICE}.ConversationSecurityPolicy.resolve",
                return_value=SimpleNamespace(mode=ConversationSecurityMode.BACKEND_MANAGED),
            ),
            patch(f"{TEXT_SERVICE}.existing_message_for_client_request", return_value=existing),
            patch(f"{TEXT_SERVICE}.Message.objects.create") as create,
            patch(f"{TEXT_SERVICE}.enforce_backend_readable_message_content_safety") as safety,
            patch(f"{TEXT_SERVICE}.validate_reply_target") as reply_validator,
        ):
            result = create_backend_managed_text_message(
                dialogue=dialogue,
                sender=sender,
                content="Hello Organization",
                client_request_id=uuid4(),
            )
        self.assertTrue(result["ok"])
        self.assertIs(result["payload"]["message"], existing)
        self.assertFalse(result["payload"]["created"])
        self.assertTrue(result["payload"]["idempotent_replay"])
        create.assert_not_called()
        safety.assert_not_called()
        reply_validator.assert_not_called()

    def test_request_id_reuse_with_different_text_is_rejected(self):
        with (
            patch(
                f"{TEXT_SERVICE}.ConversationSecurityPolicy.resolve",
                return_value=SimpleNamespace(mode=ConversationSecurityMode.BACKEND_MANAGED),
            ),
            patch(
                f"{TEXT_SERVICE}.existing_message_for_client_request",
                return_value=self._message(content="Original text"),
            ),
            patch(f"{TEXT_SERVICE}.Message.objects.create") as create,
        ):
            result = create_backend_managed_text_message(
                dialogue=self._dialogue(),
                sender=self._actor(),
                content="Different text",
                client_request_id=uuid4(),
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "IDEMPOTENCY_KEY_REUSED")
        self.assertEqual(result["status"], 409)
        create.assert_not_called()

    def test_backend_media_replay_avoids_duplicate_safety_and_creation(self):
        existing = self._message()
        existing.image = "messages/original.jpg"
        existing.is_forwarded = False
        existing.forwarded_from_id = None
        with (
            patch(
                f"{TEXT_SERVICE}.ConversationSecurityPolicy.resolve",
                return_value=SimpleNamespace(mode=ConversationSecurityMode.BACKEND_MANAGED),
            ),
            patch(
                f"{TEXT_SERVICE}.validate_reply_target",
                return_value={"ok": True, "message_obj": None},
            ),
            patch(f"{TEXT_SERVICE}.existing_message_for_client_request", return_value=existing),
            patch(f"{TEXT_SERVICE}.current_content_safety_jobs", return_value=[]),
            patch(f"{TEXT_SERVICE}.Message.objects.create") as create,
            patch(f"{TEXT_SERVICE}.enforce_backend_readable_message_media_content_safety") as safety,
        ):
            result = create_file_message(
                dialogue=self._dialogue(),
                sender=self._actor(),
                uploaded_file=SimpleNamespace(size=1024, content_type="image/jpeg"),
                field_name="image",
                is_encrypted_file=False,
                client_request_id=uuid4(),
            )
        self.assertTrue(result["ok"])
        self.assertFalse(result["payload"]["created"])
        self.assertTrue(result["payload"]["idempotent_replay"])
        self.assertIs(result["payload"]["message"], existing)
        create.assert_not_called()
        safety.assert_not_called()

    def test_media_request_id_reuse_for_other_media_type_is_rejected(self):
        existing = self._message()
        existing.image = "messages/original.jpg"
        with (
            patch(
                f"{TEXT_SERVICE}.ConversationSecurityPolicy.resolve",
                return_value=SimpleNamespace(mode=ConversationSecurityMode.BACKEND_MANAGED),
            ),
            patch(
                f"{TEXT_SERVICE}.validate_reply_target",
                return_value={"ok": True, "message_obj": None},
            ),
            patch(f"{TEXT_SERVICE}.existing_message_for_client_request", return_value=existing),
            patch(f"{TEXT_SERVICE}.Message.objects.create") as create,
        ):
            result = create_file_message(
                dialogue=self._dialogue(),
                sender=self._actor(),
                uploaded_file=SimpleNamespace(size=1024, content_type="video/mp4"),
                field_name="video",
                is_encrypted_file=False,
                client_request_id=uuid4(),
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "IDEMPOTENCY_KEY_REUSED")
        create.assert_not_called()

    def test_participant_replay_does_not_repeat_workflow_or_realtime(self):
        dialogue = MagicMock()
        context = SimpleNamespace(
            pk=7,
            dialogue=dialogue,
            organization=SimpleNamespace(pk=3),
            participant_user=self._actor(),
        )
        existing = self._message()
        with (
            patch(
                f"{PARTICIPANT_SERVICE}.ensure_organization_direct_context",
                return_value=SimpleNamespace(ok=True, created=False, context=context),
            ),
            patch(f"{PARTICIPANT_SERVICE}.OrganizationDialogueContext.objects") as manager,
            patch(
                f"{PARTICIPANT_SERVICE}.ConversationAccessPolicy.can_send_as_self",
                return_value=SimpleNamespace(allowed=True),
            ),
            patch(
                f"{PARTICIPANT_SERVICE}.create_backend_managed_text_message",
                return_value={
                    "ok": True,
                    "payload": {
                        "message": existing,
                        "created": False,
                        "idempotent_replay": True,
                    },
                },
            ),
            patch(f"{PARTICIPANT_SERVICE}.mark_after_participant_message") as workflow,
            patch(f"{PARTICIPANT_SERVICE}.schedule_organization_direct_message_realtime") as realtime,
        ):
            manager.select_for_update.return_value.select_related.return_value.get.return_value = context
            # Bypass only Django's atomic decorator; every ORM access is mocked.
            result = send_organization_direct_participant_message.__wrapped__(
                organization=context.organization,
                participant_user=context.participant_user,
                content="Hello Organization",
                client_request_id=uuid4(),
            )
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], 200)
        self.assertFalse(result["payload"]["message_created"])
        workflow.assert_not_called()
        realtime.assert_not_called()
        dialogue.deleted_by_users.remove.assert_not_called()

    def test_operator_replay_does_not_repeat_attribution_or_workflow(self):
        dialogue = MagicMock()
        organization = SimpleNamespace(pk=3)
        context = SimpleNamespace(
            pk=7,
            dialogue=dialogue,
            organization=organization,
            participant_user=self._actor(),
        )
        existing = self._message()
        attribution = SimpleNamespace(id=29)
        existing.organization_attribution = attribution
        actor = SimpleNamespace(pk=15, id=15, is_authenticated=True)
        with (
            patch(f"{PARTICIPANT_SERVICE}.OrganizationDialogueContext.objects") as manager,
            patch(f"{PARTICIPANT_SERVICE}.organization_operator_can_reply", return_value=True),
            patch(
                f"{PARTICIPANT_SERVICE}.ConversationAccessPolicy.can_send_as_organization",
                return_value=SimpleNamespace(allowed=True),
            ),
            patch(
                f"{PARTICIPANT_SERVICE}.get_current_membership_for_user",
                return_value=SimpleNamespace(pk=24),
            ),
            patch(
                f"{PARTICIPANT_SERVICE}.create_backend_managed_text_message",
                return_value={
                    "ok": True,
                    "payload": {
                        "message": existing,
                        "created": False,
                        "idempotent_replay": True,
                    },
                },
            ),
            patch(f"{PARTICIPANT_SERVICE}.create_organization_message_attribution") as attribute,
            patch(f"{PARTICIPANT_SERVICE}.mark_after_organization_reply") as workflow,
            patch(f"{PARTICIPANT_SERVICE}.schedule_organization_direct_message_realtime") as realtime,
        ):
            manager.select_for_update.return_value.select_related.return_value.get.return_value = context
            result = send_organization_direct_reply.__wrapped__(
                context=context,
                acting_user=actor,
                content="Hello Organization",
                client_request_id=uuid4(),
            )
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], 200)
        self.assertIs(result["payload"]["attribution"], attribution)
        attribute.assert_not_called()
        workflow.assert_not_called()
        realtime.assert_not_called()
        dialogue.deleted_by_users.remove.assert_not_called()

    @override_settings(
        MESSENGER_SEND_THROTTLE_RATE="2/min",
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "messenger-production-contract-default",
            },
            "messenger_throttle": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "messenger-production-contract-throttle",
            },
        },
    )
    def test_http_and_realtime_share_same_throttle_state(self):
        actor = SimpleNamespace(pk=f"test-{uuid4()}", is_authenticated=True)
        request = SimpleNamespace(user=actor, META={})
        cache = caches["messenger_throttle"]
        cache.clear()
        try:
            self.assertTrue(MessengerSendRateThrottle().allow_request(request, None))
            second = check_messenger_rate_limit(
                user=actor,
                throttle_class=MessengerSendRateThrottle,
            )
            third = check_messenger_rate_limit(
                user=actor,
                throttle_class=MessengerSendRateThrottle,
            )
            self.assertTrue(second.allowed)
            self.assertFalse(third.allowed)
            self.assertGreaterEqual(third.retry_after_seconds or 0, 1)
        finally:
            cache.clear()
