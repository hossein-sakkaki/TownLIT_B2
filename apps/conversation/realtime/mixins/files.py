# apps/conversation/realtime/mixins/files.py
import json
from asgiref.sync import sync_to_async
from django.utils import timezone
from channels.db import database_sync_to_async
from services.redis_online_manager import get_redis_connection


from apps.conversation.models import Message, MessageEncryption, Dialogue
from apps.accounts.services.sender_verification import is_sender_device_verified



class FileEventsMixin:
    """
    Provides:
    - handle_file_message (after metadata upload)
    - real-time file_message event
    - upload cancel + status updates
    - recording status broadcasting
    """

    # ------------------------------------------------------------
    # FILE MESSAGE
    # ------------------------------------------------------------
    async def handle_file_message(self, data):
        dialogue_slug = (data.get("dialogue_slug") or "").strip()
        message_id = data.get("message_id")
        file_type = (data.get("file_type") or "").strip().lower()
        file_url = data.get("file_url")  # may be None for E2EE

        if not dialogue_slug or not message_id or file_type not in ("image", "video", "audio", "file"):
            return

        # ---------------------------------------------------------
        # Load message + dialogue
        # ---------------------------------------------------------
        try:
            message = await sync_to_async(
                Message.objects.select_related("dialogue", "sender").get
            )(id=message_id, dialogue__slug=dialogue_slug)
        except Message.DoesNotExist:
            return

        dialogue = message.dialogue
        is_group = bool(dialogue.is_group)

        # ---------------------------------------------------------
        # PoP (sender device verification)
        # ---------------------------------------------------------
        verified = await database_sync_to_async(is_sender_device_verified)(
            self.user,
            self.device_id,
            dialogue_is_group=is_group,
        )
        if not verified:
            return

        # ---------------------------------------------------------
        # Encryption flags
        # ---------------------------------------------------------
        is_encrypted_file = bool(getattr(message, "is_encrypted_file", False))
        is_encrypted = (not is_group)  # DM encrypted, group not

        # ---------------------------------------------------------
        # Group files MUST have URL
        # ---------------------------------------------------------
        if not is_encrypted_file:
            if not file_url:
                try:
                    model_file = getattr(message, file_type, None)
                    if model_file and hasattr(model_file, "url"):
                        file_url = model_file.url
                except Exception:
                    file_url = None

            if not file_url:
                return
        else:
            file_url = None  # E2EE file -> receiver uses accessMedia

        payload = {
            "message_id": message.id,
            "dialogue_slug": dialogue_slug,
            "file_type": file_type,
            "sender": {
                "id": message.sender.id,
                "username": message.sender.username,
                "email": message.sender.email,
            },
            "timestamp": message.timestamp.isoformat(),

            "is_encrypted_file": is_encrypted_file,
            "is_encrypted": is_encrypted,

            # ✅ semantic flags only
            "has_file": True,
        }


        # ✅ Broadcast via dialogue group
        await self.channel_layer.group_send(
            f"dialogue_{dialogue_slug}",
            {
                "type": "dispatch_event",
                "app": "conversation",
                "event": "file_message",
                "data": payload,
            }
        )


    # ------------------------------------------------------------
    # FILE UPLOAD CANCEL
    # ------------------------------------------------------------
    async def handle_upload_canceled(self, data):
        dialogue_slug = data.get("dialogue_slug")
        file_type = data.get("file_type")

        if not dialogue_slug or not file_type:
            return

        # ensure dialogue exists
        try:
            await sync_to_async(Dialogue.objects.get)(
                slug=dialogue_slug,
                participants=self.user
            )
        except Dialogue.DoesNotExist:
            return

        # broadcast cancel
        await self.channel_layer.group_send(
            f"dialogue_{dialogue_slug}",
            {
                "type": "dispatch_event",
                "app": "conversation",
                "event": "file_upload_status",
                "data": {
                    "dialogue_slug": dialogue_slug,
                    "file_type": file_type,
                    "status": "cancelled",
                    "progress": 0,
                }
            }
        )

        # confirm to sender (unified)
        await self.consumer.safe_send_json({
            "type": "event",
            "app": "conversation",
            "event": "upload_canceled",
            "data": {
                "dialogue_slug": dialogue_slug,
                "file_type": file_type,
                "status": "cancelled",
            }
        })


    # ------------------------------------------------------------
    # UPLOAD STATUS (progress, processing, ready) 
    # ------------------------------------------------------------

    async def send_file_status(self, dialogue_slug, file_type, status, progress=None):
        """Broadcast upload status to all participants of the dialogue."""
        try:
            await sync_to_async(Dialogue.objects.get)(
                slug=dialogue_slug,
                participants=self.user
            )
        except Dialogue.DoesNotExist:
            return

        await self.channel_layer.group_send(
            f"dialogue_{dialogue_slug}",
            {
                "type": "dispatch_event",
                "app": "conversation",
                "event": "file_upload_status",
                "data": {
                    "dialogue_slug": dialogue_slug,
                    "sender": {
                        "id": self.user.id,
                        "username": self.user.username,
                        "email": self.user.email,
                    },
                    "file_type": file_type,
                    "status": status,
                    "progress": progress,
                }
            }
        )


    async def handle_file_upload_status(self, data):
        dialogue_slug = data.get("dialogue_slug")
        file_type = data.get("file_type")
        status = data.get("status")
        progress = data.get("progress", None)

        if not dialogue_slug or not file_type or not status:
            return

        await self.send_file_status(dialogue_slug, file_type, status, progress)


    # ------------------------------------------------------------
    # RECORDING STATUS (audio/video live recording indicator)
    # ------------------------------------------------------------

    async def handle_recording_status(self, data):
        dialogue_slug = data.get("dialogue_slug")
        is_recording = data.get("is_recording", False)
        file_type = data.get("file_type")  # audio / video

        if not dialogue_slug or not file_type:
            return

        # Ensure dialogue exists
        try:
            await sync_to_async(Dialogue.objects.get)(
                slug=dialogue_slug,
                participants=self.user
            )
        except Dialogue.DoesNotExist:
            return

        await self.channel_layer.group_send(
            f"dialogue_{dialogue_slug}",
            {
                "type": "dispatch_event",
                "app": "conversation",
                "event": "recording_status",
                "data": {
                    "dialogue_slug": dialogue_slug,
                    "sender": {
                        "id": self.user.id,
                        "username": self.user.username,
                        "email": self.user.email,
                    },
                    "is_recording": is_recording,
                    "file_type": file_type,
                }
            }
        )


