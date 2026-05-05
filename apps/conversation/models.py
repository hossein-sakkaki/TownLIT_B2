# apps/conversation/models.py

from django.db import models
from django.db.models import Q
from datetime import timedelta
from django.utils import timezone

from django.conf import settings

from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
import os
import uuid
from django.utils.crypto import get_random_string

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from apps.conversation.constants import (
    DELETE_POLICY_CHOICES,
    MESSAGE_POLICY_CHOICES,
    KEEP,
    GROUP_ROLE_CHOICES,
    PARTICIPANT,
    SYSTEM_MESSAGE_EVENT_CHOICES,
    MESSAGE_PIN_DURATION_CHOICES,
    PIN_NONE,
    MESSAGE_REACTION_TYPE_CHOICES,
)
from validators.mediaValidators.image_validators import validate_image_file, validate_image_size
from validators.security_validators import validate_no_executable_file

def get_upload_path(category, file_type, sub_folder):
    """ Import FileUpload dynamically to avoid circular import issues. """
    from utils.common.utils import FileUpload
    return FileUpload(category, file_type, sub_folder).dir_upload


# DIALOGUE Model -------------------------------------------------------------------------
class Dialogue(models.Model):
    id = models.BigAutoField(primary_key=True)
    group_name = models.CharField( max_length=255, blank=True, null=True, unique=False, verbose_name="Group Name")
    group_image = models.ImageField(upload_to=get_upload_path('conversation', 'cover', 'group'), validators=[validate_image_file, validate_image_size, validate_no_executable_file], blank=True, null=True, verbose_name="Group Image")
    group_avatar_version = models.PositiveIntegerField(default=1)
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="dialogues")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    is_group = models.BooleanField(default=False, verbose_name="Is Group")
    last_message = models.ForeignKey('Message', on_delete=models.SET_NULL, null=True, blank=True, related_name="last_message_dialogue")
    deleted_by_users = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="deleted_dialogues", blank=True)
    rsa_required = models.BooleanField(default=False, verbose_name="Requires RSA Encryption")
    
    slug = models.SlugField(max_length=255, unique=True, blank=True, null=True, verbose_name="Slug")

    @staticmethod
    def generate_dialogue_slug(usernames: list[str], group_name: str | None = None) -> str:
        random_part = get_random_string(length=10)
        timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
        return f"d-{timestamp}-{random_part}"

    @property
    def group_image_url(self):
        if self.group_image:
            return self.group_image.url
        return settings.DEFAULT_GROUP_AVATAR_URL


    def has_role(self, user, role: str) -> bool:
        return self.participants_roles.filter(user=user, role=role).exists()

    def is_founder(self, user) -> bool:
        return self.has_role(user, 'founder')

    def is_elder(self, user) -> bool:
        return self.has_role(user, 'elder')

    def has_multiple_elders(self):
        return self.participants_roles.filter(role='elder').count() > 1

    def is_group_manager(self, user) -> bool:
        return self.participants_roles.filter(user=user, role__in=['founder', 'elder']).exists()

    # Soft delete the dialogue and all its messages for one user --------------------
    def mark_as_deleted_by_user(self, user):
        """
        Hide this dialogue and all current messages for one user.
        New incoming messages are handled separately by runtime logic.
        """
        self.deleted_by_users.add(user)

        for message in self.messages.all():
            message.deleted_by_users.add(user)

    def leave_group(self, user):
        """
        Remove user from group participants and soft-delete the dialogue for them.
        """
        self.participants.remove(user)
        self.mark_as_deleted_by_user(user)
        DialogueParticipant.objects.filter(dialogue=self, user=user).delete()

    def restore_dialogue_visibility_only(self, user):
        """
        Restore only dialogue visibility.
        Old hidden messages remain hidden.
        """
        self.deleted_by_users.remove(user)

    def restore_dialogue_and_messages(self, user):
        """
        Restore dialogue visibility and all previously hidden messages for this user.
        Use only when full restore is explicitly required.
        """
        self.deleted_by_users.remove(user)

        for message in self.messages.filter(deleted_by_users=user):
            message.deleted_by_users.remove(user)

    def restore_dialogue(self, user):
        """
        Backward-compatible restore method.
        Current messenger logic expects visibility-only restore.
        """
        self.restore_dialogue_visibility_only(user)
    # Get last message ----------------------------------------------------------------------
    def get_last_message(self):
        """Return the latest message globally (not user-specific)."""
        return self.messages.order_by("-timestamp").first()

    def get_last_message_for_user(self, user):
        """
        Return the latest visible non-system message for one user.
        """
        return (
            self.visible_non_system_messages_for_user(user)
            .order_by("-timestamp")
            .first()
        )

    # Get visible messages ------------------------------------------------------------------
    def visible_messages_for_user(self, user):
        """
        Return messages visible to one user.
        """
        return self.messages.exclude(deleted_by_users=user)

    def visible_non_system_messages_for_user(self, user):
        """
        Return visible non-system messages for one user.
        """
        return self.visible_messages_for_user(user).filter(is_system=False)

    def unread_messages_for_user(self, user):
        """
        Return unread incoming visible messages for one user.
        """
        return (
            self.visible_messages_for_user(user)
            .exclude(seen_by_users=user)
            .exclude(sender=user)
        )
        
    #  Get markers -------------------------------------------------------------------------
    def get_marker_for_user(self, user):
        """Return marker for this user if it exists."""
        return self.marked_users.filter(user=user).first()

    def get_or_create_marker_for_user(self, user):
        """Get or create a marker row for internal dialogue state."""
        marker, _created = UserDialogueMarker.objects.get_or_create(
            user=user,
            dialogue=self,
            defaults={
                "is_sensitive": False,
                "delete_policy": "SOFT_DELETE",
            },
        )
        return marker

    def arm_inbound_block_until_outgoing(self, user):
        """
        Enable one-way hidden incoming mode for this user.
        Used by LITShield-like security flows.
        """
        marker = self.get_or_create_marker_for_user(user)
        marker.is_sensitive = False  # hide sensitive label from UI/privacy
        marker.inbound_blocked_until_outgoing = True
        marker.save(update_fields=["is_sensitive", "inbound_blocked_until_outgoing"])

        # Keep dialogue hidden for this user
        self.deleted_by_users.add(user)

    def release_inbound_block_on_outgoing(self, user):
        """
        Re-open the dialogue when the protected user sends the first outgoing message.
        Old messages remain hidden because message.deleted_by_users is untouched.
        """
        marker = self.get_marker_for_user(user)
        if marker and marker.inbound_blocked_until_outgoing:
            marker.inbound_blocked_until_outgoing = False
            marker.save(update_fields=["inbound_blocked_until_outgoing"])

        if self.deleted_by_users.filter(id=user.id).exists():
            self.deleted_by_users.remove(user)

    def should_hide_incoming_for_user(self, user):
        """
        Incoming messages should stay hidden when the dialogue is in
        one-way blocked mode for this user.
        """
        marker = self.get_marker_for_user(user)
        return bool(marker and marker.inbound_blocked_until_outgoing)

    def should_restore_on_incoming_for_user(self, user):
        """
        Normal soft-deleted dialogue should become visible again on incoming activity.
        Security-blocked dialogue should not.
        """
        if not self.deleted_by_users.filter(id=user.id).exists():
            return False

        return not self.should_hide_incoming_for_user(user)

    # Refresh last message cache --------------------------------------------
    def refresh_last_message_cache(self, save: bool = True):
        """
        Refresh the global last_message cache using the latest non-system message.
        This cache must stay user-agnostic.
        """
        last_msg = (
            self.messages
            .exclude(is_system=True)
            .order_by("-timestamp")
            .first()
        )
        self.last_message = last_msg if last_msg else None

        if save:
            self.save(update_fields=["last_message"])

        return self.last_message
    
    # Overriding __str__ method --------------------------------------------
    def __str__(self):
        if self.is_group:
            return f"Group: {self.group_name} with {self.participants.count()} participants"
        return f"Dialogue between: {', '.join([user.username for user in self.participants.all()])}"



# DIALOGUE PARTICIPANT Model -------------------------------------------------------------------------
class DialogueParticipant(models.Model):
    id = models.BigAutoField(primary_key=True)
    dialogue = models.ForeignKey(Dialogue, on_delete=models.CASCADE, related_name="participants_roles", verbose_name="Dialogue")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="User")
    role = models.CharField(max_length=20, choices=GROUP_ROLE_CHOICES, default=PARTICIPANT, verbose_name="Role")
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name="Joined At")

    class Meta:
        unique_together = ('dialogue', 'user')

    def __str__(self):
        return f"{self.user.username} in {self.dialogue.group_name} as {self.role}"


# MESSAGE Model -------------------------------------------------------------------------
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
    def update_is_read_bulk(cls, dialogue, user):
        """ Update read status for all unread messages in a dialogue """
        unread_messages = cls.objects.filter(dialogue=dialogue).exclude(seen_by_users=user)
        for message in unread_messages:
            message.seen_by_users.add(user)
        dialogue.save()

    def __str__(self):
        return f"Message from {self.sender.username} in {self.dialogue.id}"
    

# MESSAGE ENCRYPTION Model -------------------------------------------------------------------------
class MessageEncryption(models.Model):
    id = models.BigAutoField(primary_key=True)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='encryptions')
    device_id = models.CharField(max_length=255)
    encrypted_content = models.TextField()
    created_at = models.DateTimeField(null=True, auto_now_add=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["message", "device_id"], name="uq_message_device"),
        ]
        indexes = [
            models.Index(fields=["message", "device_id"], name="idx_message_device"),
        ]


# MESSAGE SEARCH INDEX Model -------------------------------------------------------------------------
class MessageSearchIndex(models.Model):
    message = models.OneToOneField(Message, on_delete=models.CASCADE, related_name="search_index")
    plaintext = models.TextField()

    def __str__(self):
        return f"SearchIndex for Message {self.message_id}"




# USER DIALOGUE MARKER Model -------------------------------------------------------------------------
class UserDialogueMarker(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="marked_dialogues")
    dialogue = models.ForeignKey(Dialogue, on_delete=models.CASCADE, related_name="marked_users")

    is_sensitive = models.BooleanField(default=False)
    delete_policy = models.CharField(max_length=50, choices=DELETE_POLICY_CHOICES, default='SOFT_DELETE')

    # Internal security state (not exposed to frontend)
    inbound_blocked_until_outgoing = models.BooleanField(default=False)

    last_typing_at = models.DateTimeField(null=True, blank=True, verbose_name="Last Typing At")


    class Meta:
        unique_together = ('user', 'dialogue')

    def should_soft_delete(self):
        """ Check if the chat should be soft deleted for the user """
        return self.delete_policy == 'SOFT_DELETE'

    def should_leave_group_soft_delete(self):
        """ Check if the user should leave the group and have it removed from their profile """
        return self.delete_policy == 'LEAVE_GROUP_SOFT_DELETE'

    def update_typing_status(self):
        """ Last Typing """
        self.last_typing_at = timezone.now()
        self.save()

    def __str__(self):
        return f"{self.user.username} - {self.dialogue.id} (Sensitive: {self.is_sensitive})"


# DIALOGUE PIN Model -------------------------------------------------------------------------
class DialoguePin(models.Model):
    id = models.BigAutoField(primary_key=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dialogue_pins",
        verbose_name="User",
    )
    dialogue = models.ForeignKey(
        Dialogue,
        on_delete=models.CASCADE,
        related_name="pins",
        verbose_name="Dialogue",
    )

    # Stable per-user pin order: 1..5
    position = models.PositiveSmallIntegerField(verbose_name="Pin Position")
    pinned_at = models.DateTimeField(auto_now_add=True, verbose_name="Pinned At")

    class Meta:
        ordering = ["position", "-pinned_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "dialogue"],
                name="uq_dialogue_pin_user_dialogue",
            ),
            models.UniqueConstraint(
                fields=["user", "position"],
                name="uq_dialogue_pin_user_position",
            ),
            models.CheckConstraint(
                check=Q(position__gte=1) & Q(position__lte=5),
                name="ck_dialogue_pin_position_range",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} pinned {self.dialogue.slug} at {self.position}"
    

# MESSAGE PIN Model -------------------------------------------------------------------------
class MessagePin(models.Model):
    id = models.BigAutoField(primary_key=True)

    dialogue = models.ForeignKey(
        Dialogue,
        on_delete=models.CASCADE,
        related_name="message_pins",
        verbose_name="Dialogue",
    )
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="pins",
        verbose_name="Message",
    )

    pinned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_pins_created",
        verbose_name="Pinned By",
    )

    # Stable shared pin order inside one dialogue: 1..5
    position = models.PositiveSmallIntegerField(verbose_name="Pin Position")

    # Optional expiry/reminder policy
    pin_duration = models.CharField(
        max_length=20,
        choices=MESSAGE_PIN_DURATION_CHOICES,
        default=PIN_NONE,
        verbose_name="Pin Duration",
    )
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Expires At")

    reminders_enabled = models.BooleanField(default=False, verbose_name="Reminders Enabled")
    reminder_interval_minutes = models.PositiveIntegerField(null=True, blank=True, verbose_name="Reminder Interval Minutes")
    next_reminder_at = models.DateTimeField(null=True, blank=True, verbose_name="Next Reminder At")
    last_reminded_at = models.DateTimeField(null=True, blank=True, verbose_name="Last Reminded At")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        ordering = ["position", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["dialogue", "message"],
                name="uq_message_pin_dialogue_message",
            ),
            models.UniqueConstraint(
                fields=["dialogue", "position"],
                name="uq_message_pin_dialogue_position",
            ),
            models.CheckConstraint(
                check=Q(position__gte=1) & Q(position__lte=5),
                name="ck_message_pin_position_range",
            ),
        ]

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f"Pin #{self.position} in {self.dialogue.slug} for message {self.message_id}"
    

# MESSAGE REACTION Model -------------------------------------------------------------------------
class MessageReaction(models.Model):
    id = models.BigAutoField(primary_key=True)

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="message_reactions",
        verbose_name="Message",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_reactions",
        verbose_name="User",
    )
    reaction_type = models.CharField(
        max_length=32,
        choices=MESSAGE_REACTION_TYPE_CHOICES,
        verbose_name="Reaction Type",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["message", "user"],
                name="uq_message_reaction_message_user",
            ),
        ]
        indexes = [
            models.Index(fields=["message", "reaction_type"], name="idx_msg_reaction_msg_type"),
            models.Index(fields=["user", "reaction_type"], name="idx_msg_reaction_user_type"),
        ]
        ordering = ["reaction_type", "created_at"]

    def __str__(self):
        return f"{self.user.username} reacted {self.reaction_type} to message {self.message_id}"