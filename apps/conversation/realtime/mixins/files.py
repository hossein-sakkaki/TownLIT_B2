# apps/conversation/realtime/mixins/files.py

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async

from apps.conversation.models import Message
from apps.accounts.services.sender_verification import is_sender_device_verified
from apps.conversation.services.realtime_access import get_dialogue_for_user
from apps.conversation.services.file_realtime import (
    build_file_message_payload,
    resolve_file_message_targets,
    build_file_upload_status_payload,
    build_recording_status_payload,
    build_upload_canceled_payload,
)


class FileEventsMixin:
    """
    Realtime orchestration for file-related conversation events.

    Notes:
    - File creation mutation is handled by service layer.
    - Payload/routing resolution is handled by file_realtime helpers.
    - This mixin is responsible for access checks, PoP checks, and dispatch only.
    """

    VALID_FILE_TYPES = {"image", "video", "audio", "file"}

    # ------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------
    async def _broadcast_unread_count_for_file_message(self, message):
        """
        Increment unread count for visible recipients of a file message.
        Mirrors text-message unread behavior.
        """
        dialogue = message.dialogue
        sender_id = message.sender.id

        participants = await sync_to_async(list)(dialogue.participants.all())

        hidden_recipient_ids = set(
            await sync_to_async(list)(
                message.deleted_by_users.values_list("id", flat=True)
            )
        )

        for participant in participants:
            if participant.id == sender_id:
                continue

            if participant.id in hidden_recipient_ids:
                continue

            await self.channel_layer.group_send(
                f"user_{participant.id}",
                {
                    "type": "dispatch_event",
                    "app": "conversation",
                    "event": "unread_count_update",
                    "data": {
                        # Keep current payload shape for frontend compatibility
                        "payload": [
                            {
                                "dialogue_slug": dialogue.slug,
                                "unread_count": 1,
                                "sender_id": sender_id,
                            }
                        ]
                    },
                },
            )

    async def _load_dialogue_for_user(self, dialogue_slug):
        return await sync_to_async(get_dialogue_for_user)(dialogue_slug, self.user)

    # ------------------------------------------------------------
    # FILE MESSAGE
    # ------------------------------------------------------------
    async def handle_file_message(self, data):
        dialogue_slug = (data.get("dialogue_slug") or "").strip()
        message_id = data.get("message_id")
        file_type = (data.get("file_type") or "").strip().lower()

        if not dialogue_slug or not message_id or file_type not in self.VALID_FILE_TYPES:
            return

        try:
            message = await sync_to_async(
                Message.objects.select_related("dialogue", "sender").get
            )(id=message_id, dialogue__slug=dialogue_slug)
        except Message.DoesNotExist:
            return

        dialogue = message.dialogue
        is_group = bool(dialogue.is_group)

        verified = await database_sync_to_async(is_sender_device_verified)(
            self.user,
            self.device_id,
            dialogue_is_group=is_group,
        )
        if not verified:
            await self._send_error(
                code="SENDER_DEVICE_UNVERIFIED",
                message="Sender device is not verified",
            )
            return

        # Build one canonical payload shape for both group and DM file messages.
        # For non-encrypted files, helper resolves a safe URL.
        payload = await database_sync_to_async(build_file_message_payload)(
            message=message,
            dialogue_slug=dialogue_slug,
            file_type=file_type,
        )

        routing = await database_sync_to_async(resolve_file_message_targets)(message)
        mode = routing.get("mode")

        if mode in ("group_broadcast", "dm_group_broadcast"):
            await self.channel_layer.group_send(
                routing["group_name"],
                {
                    "type": "dispatch_event",
                    "app": "conversation",
                    "event": "file_message",
                    "data": payload,
                },
            )

            await self._broadcast_unread_count_for_file_message(message)
            return

        if mode == "dm_device_broadcast":
            for target in routing.get("device_targets", []):
                await self.channel_layer.group_send(
                    target["group_name"],
                    {
                        "type": "dispatch_event",
                        "app": "conversation",
                        "event": "file_message",
                        "data": payload,
                    },
                )

            await self._broadcast_unread_count_for_file_message(message)
            return

        await self._send_error(
            code="FILE_ROUTING_FAILED",
            message="Unsupported file routing mode",
            details={"mode": mode},
        )

    # ------------------------------------------------------------
    # FILE UPLOAD CANCEL
    # ------------------------------------------------------------
    async def handle_upload_canceled(self, data):
        dialogue_slug = (data.get("dialogue_slug") or "").strip()
        file_type = (data.get("file_type") or "").strip().lower()

        if not dialogue_slug or file_type not in self.VALID_FILE_TYPES:
            return

        dialogue = await self._load_dialogue_for_user(dialogue_slug)
        if not dialogue:
            return

        payload = build_upload_canceled_payload(
            dialogue_slug=dialogue_slug,
            file_type=file_type,
        )

        # Broadcast upload status update to dialogue participants
        await self.channel_layer.group_send(
            f"dialogue_{dialogue_slug}",
            {
                "type": "dispatch_event",
                "app": "conversation",
                "event": "file_upload_status",
                "data": payload,
            },
        )

        # Confirm cancel to sender session
        await self.consumer.send_app_event(
            app="conversation",
            event="upload_canceled",
            data={
                "dialogue_slug": dialogue_slug,
                "file_type": file_type,
                "status": "cancelled",
            },
        )

    # ------------------------------------------------------------
    # FILE UPLOAD STATUS
    # ------------------------------------------------------------
    async def send_file_status(self, dialogue_slug, file_type, status, progress=None):
        """
        Broadcast upload status to all participants of the dialogue.
        """
        dialogue = await self._load_dialogue_for_user(dialogue_slug)
        if not dialogue:
            return

        payload = build_file_upload_status_payload(
            dialogue_slug=dialogue_slug,
            sender=self.user,
            file_type=file_type,
            status=status,
            progress=progress,
        )

        await self.channel_layer.group_send(
            f"dialogue_{dialogue_slug}",
            {
                "type": "dispatch_event",
                "app": "conversation",
                "event": "file_upload_status",
                "data": payload,
            },
        )

    async def handle_file_upload_status(self, data):
        dialogue_slug = (data.get("dialogue_slug") or "").strip()
        file_type = (data.get("file_type") or "").strip().lower()
        status = (data.get("status") or "").strip().lower()
        progress = data.get("progress", None)

        if not dialogue_slug or file_type not in self.VALID_FILE_TYPES or not status:
            return

        await self.send_file_status(dialogue_slug, file_type, status, progress)

    # ------------------------------------------------------------
    # RECORDING STATUS
    # ------------------------------------------------------------
    async def handle_recording_status(self, data):
        dialogue_slug = (data.get("dialogue_slug") or "").strip()
        is_recording = bool(data.get("is_recording", False))
        file_type = (data.get("file_type") or "").strip().lower()

        if not dialogue_slug or file_type not in {"audio", "video"}:
            return

        dialogue = await self._load_dialogue_for_user(dialogue_slug)
        if not dialogue:
            return

        payload = build_recording_status_payload(
            dialogue_slug=dialogue_slug,
            sender=self.user,
            file_type=file_type,
            is_recording=is_recording,
        )

        await self.channel_layer.group_send(
            f"dialogue_{dialogue_slug}",
            {
                "type": "dispatch_event",
                "app": "conversation",
                "event": "recording_status",
                "data": payload,
            },
        )