# apps/conversation/models/message.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-18.
#

from datetime import timedelta
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from apps.content_safety.enums import SafetyContext, SafetyInputType
from apps.conversation.constants import SYSTEM_MESSAGE_EVENT_CHOICES
from validators.mediaValidators.image_validators import (
    validate_image_file,
    validate_image_size,
)
from validators.security_validators import validate_no_executable_file

from .dialogue import Dialogue
from .upload_paths import get_upload_path


class Message(models.Model):
    id = models.BigAutoField(primary_key=True)
    dialogue = models.ForeignKey(Dialogue, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Timestamp")
    edited_at = models.DateTimeField(null=True, blank=True, verbose_name="Edited At")
    is_edited = models.BooleanField(default=False)
    is_delivered = models.BooleanField(default=False, verbose_name="Is Delivered")
    seen_by_users = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="seen_messages", blank=True, verbose_name="Seen By")
    # Reply relation
    reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
        verbose_name="Reply To",
    )
    # Forward relation
    is_forwarded = models.BooleanField(default=False)
    forwarded_from = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="forwarded_copies",
        verbose_name="Forwarded From",
    )
    # Encrypted message content
    content_encrypted = models.BinaryField(blank=True, null=True)
    aes_key_encrypted = models.BinaryField(blank=True, null=True)  # AES key encrypted with RSA
    encrypted_for_device = models.CharField(max_length=100, null=True, blank=True)
    is_encrypted_file = models.BooleanField(default=False, verbose_name="Is File Encrypted")
    is_delivery_ready = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Is Delivery Ready",
        help_text=(
            "False while backend-readable Group Messenger media "
            "is waiting for asynchronous safety approval."
        ),
    )
    image = models.ImageField(upload_to=get_upload_path('conversation', 'image', 'message'), blank=True, null=True, verbose_name="Image")
    video = models.FileField(upload_to=get_upload_path('conversation', 'video', 'message'), blank=True, null=True, verbose_name="Video")
    file = models.FileField(upload_to=get_upload_path('conversation', 'file', 'message'), blank=True, null=True, verbose_name="File")
    audio = models.FileField(upload_to=get_upload_path('conversation', 'audio', 'message'), blank=True, null=True, verbose_name="Audio")
    # Soft delete messages for specific users
    deleted_by_users = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="deleted_messages", blank=True)
    # Self-destruct time for messages
    self_destruct_at = models.DateTimeField(null=True, blank=True, verbose_name="Self-destruct At")
    is_system = models.BooleanField(default=False)
    system_event = models.CharField(max_length=50, choices=SYSTEM_MESSAGE_EVENT_CHOICES, null=True, blank=True)
    client_request_id = models.UUIDField(
        null=True,
        blank=True,
        editable=False,
        verbose_name="Client Request ID",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("dialogue", "sender", "client_request_id"),
                name="conversation_unique_message_client_request",
            ),
        ]

    @property
    def is_encrypted(self):
        return self.encryptions.exists()

    def set_self_destruct(self, duration_minutes):
        """ Set the message to self-destruct after a specified duration """
        self.self_destruct_at = timezone.now() + timedelta(minutes=duration_minutes)
        self.save()

    def should_self_destruct(self):
        """ Check if the message should be deleted """
        return self.self_destruct_at and timezone.now() >= self.self_destruct_at

    def encrypt_message(self, content, receiver_public_key):
        aes_key = os.urandom(32)  # 256-bit AES key
        nonce = os.urandom(12)    # 96-bit nonce for AES-GCM
        aesgcm = AESGCM(aes_key)
        encrypted_content = aesgcm.encrypt(nonce, content.encode(), None)
        # Combine key and nonce and encrypt with RSA
        encrypted_aes_key = receiver_public_key.encrypt(
            aes_key + nonce,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        self.content_encrypted = encrypted_content
        self.aes_key_encrypted = encrypted_aes_key
        self.is_encrypted = True
        self.save()

    def decrypt_message(self, receiver_private_key):
        if not self.is_encrypted:
            return self.content_encrypted.decode() if self.content_encrypted else ""
        decrypted_key = receiver_private_key.decrypt(
            self.aes_key_encrypted,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        aes_key = decrypted_key[:32]
        nonce = decrypted_key[32:]
        aesgcm = AESGCM(aes_key)
        decrypted_content = aesgcm.decrypt(nonce, self.content_encrypted, None)
        return decrypted_content.decode()
    # For Admin And Debuging ------------------------------

    def decrypt_file(self, media_type, private_key):
        ffield = getattr(self, media_type, None)
        if not ffield:
            return None
        storage = ffield.storage
        name = ffield.name
        if not name or not storage.exists(name):
            return None
        with storage.open(name, 'rb') as f:
            encrypted_bytes = f.read()
        decrypted_key = private_key.decrypt(
            self.aes_key_encrypted,
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(), label=None)
        )
        aes_key, nonce = decrypted_key[:32], decrypted_key[32:]
        aesgcm = AESGCM(aes_key)
        decrypted_bytes = aesgcm.decrypt(nonce, encrypted_bytes, None)
        import tempfile, uuid
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uuid.uuid4().hex}.bin") as tmp:
            tmp.write(decrypted_bytes)
            return tmp.name

    def get_content_safety_media_config(
        self,
    ) -> dict:
        """
        Configure asynchronous Content Safety only for
        backend-readable Messenger video.

        Messenger media is already prepared by the client.
        It must never enter the server Media Conversion pipeline.
        """
        if not self.dialogue_id:
            return {}
        if self.is_encrypted_file:
            return {}
        dialogue = getattr(
            self,
            "dialogue",
            None,
        )
        if dialogue is None:
            return {}

        from apps.conversation.policies import (
            ConversationSecurityMode,
            ConversationSecurityPolicy,
        )

        security = ConversationSecurityPolicy.resolve(dialogue)
        if security.mode != ConversationSecurityMode.BACKEND_MANAGED:
            return {}
        video = getattr(
            self,
            "video",
            None,
        )
        video_path = str(
            getattr(
                video,
                "name",
                "",
            )
            or ""
        ).strip()
        if not video_path:
            return {}
        return {
            "video": {
                "input_type": (
                    SafetyInputType.VIDEO
                ),
                "context": (
                    SafetyContext.GROUP_MESSAGE_MEDIA
                ),
                "conversion_kind": "video",
                "handoff_to_conversion": False,
            },
        }

    def on_content_safety_media_approved(
        self,
        *,
        field_name: str,
        source_path: str,
    ) -> None:
        """
        Finalize one safety-approved backend-readable Messenger video.

        This is a delivery-readiness transition only.
        Messenger media must never enter Media Conversion here.
        """
        normalized_field = str(
            field_name
            or ""
        ).strip()
        expected_source = str(
            source_path
            or ""
        ).strip().lstrip(
            "/"
        )
        if normalized_field != "video":
            raise ValueError(
                "Only Messenger video uses asynchronous media safety."
            )
        if self.is_encrypted_file:
            raise ValueError(
                "Encrypted Messenger media cannot use backend Content Safety."
            )
        if not self.pk:
            raise ValueError(
                "Messenger message must be persisted before safety finalization."
            )
        with transaction.atomic():
            locked = (
                type(self).objects
                .select_for_update()
                .select_related(
                    "dialogue"
                )
                .get(
                    pk=self.pk
                )
            )
            from apps.conversation.policies import (
                ConversationContextKind,
                ConversationContextPolicy,
                ConversationSecurityMode,
                ConversationSecurityPolicy,
            )

            security = ConversationSecurityPolicy.resolve(locked.dialogue)
            if (
                security.mode != ConversationSecurityMode.BACKEND_MANAGED
                or locked.is_encrypted_file
            ):
                raise ValueError(
                    "Only backend-readable Messenger video can be finalized."
                )
            current_source = str(
                getattr(
                    locked.video,
                    "name",
                    "",
                )
                or ""
            ).strip().lstrip(
                "/"
            )
            if (
                not current_source
                or current_source
                != expected_source
            ):
                raise ValueError(
                    "The Messenger video source has changed."
                )
            transitioned_to_ready = not locked.is_delivery_ready
            if transitioned_to_ready:
                locked.is_delivery_ready = True
                locked.save(
                    update_fields=[
                        "is_delivery_ready",
                    ]
                )
            # Lock the dialogue before rebuilding the global cache.
            #
            # Important:
            # If a newer delivery-ready message arrived while this video
            # was under Safety, the older approved video must not overwrite
            # that newer message as dialogue.last_message.
            dialogue = (
                Dialogue.objects
                .select_for_update()
                .get(
                    pk=locked.dialogue_id
                )
            )
            dialogue.refresh_last_message_cache(
                save=True
            )

            if transitioned_to_ready:
                context = ConversationContextPolicy.resolve(locked.dialogue)
                if context.kind == ConversationContextKind.ORGANIZATION_DIRECT:
                    from apps.conversation.services.organization.direct_media import (
                        finalize_organization_direct_media_delivery,
                    )
                    from apps.conversation.services.organization.direct_notifications import (
                        notify_organization_direct_message_push,
                    )

                    finalize_organization_direct_media_delivery(
                        message=locked
                    )
                    transaction.on_commit(
                        lambda mid=locked.id: (
                            notify_organization_direct_message_push(mid)
                        )
                    )

            self.is_delivery_ready = True

    def edit_message(self, new_content, receiver_public_key=None, receiver_device_id=None):
        if self.is_encrypted and receiver_public_key:
            self.encrypt_message(new_content, receiver_public_key)
            self.encrypted_for_device = receiver_device_id
        else:
            self.content_encrypted = new_content.encode()
            self.encrypted_for_device = None
        self.edited_at = timezone.now()
        self.is_edited = True
        self.save()

    def can_edit(self):
        return timezone.now() <= self.timestamp + timedelta(hours=12)

    def mark_as_deleted_by_user(self, user):
        """
        Soft delete is a per-user visibility action.
        It must not mutate the global dialogue last_message cache.
        """
        self.deleted_by_users.add(user)
        self.save()

    def can_hard_delete_for_user(self, user):
        """Return True if this user can hard delete this message for everyone."""
        if not user or not getattr(user, "is_authenticated", False):
            return False
        # Group managers can hard delete any group message
        if self.dialogue.is_group and self.dialogue.is_group_manager(user):
            return True
        # Only sender can hard delete own message outside manager privileges
        if user != self.sender:
            return False
        # Sender can hard delete only if nobody else has seen it
        others_have_seen = self.seen_by_users.exclude(id=self.sender_id).exists()
        return not others_have_seen
    # Backward-compatible alias

    def can_be_fully_deleted(self, user):
        """Compatibility wrapper for old code paths."""
        return self.can_hard_delete_for_user(user)

    def delete_message_completely(self, user):
        """Hard delete message if the given user is allowed."""
        if self.can_hard_delete_for_user(user):
            self.delete()
            return True
        return False

    def update_is_read(self, user):
        if user == self.sender:
            return
        if not self.seen_by_users.filter(id=user.id).exists():
            self.seen_by_users.add(user)
            self.save()

    def get_seen_by_users(self):
        return list(self.seen_by_users.values_list("id", flat=True))

    @classmethod
    def update_is_read_bulk(
        cls,
        dialogue,
        user,
    ):
        """
        Update read state only for delivery-ready messages.

        Pending asynchronous Group Messenger video must not enter
        read/unread accounting before Safety approval.
        """
        unread_messages = (
            cls.objects
            .filter(
                dialogue=dialogue,
                is_delivery_ready=True,
            )
            .exclude(
                seen_by_users=user
            )
        )
        for message in unread_messages:
            message.seen_by_users.add(
                user
            )
        dialogue.save()

    def __str__(self):
        return f"Message from {self.sender.username} in {self.dialogue.id}"

