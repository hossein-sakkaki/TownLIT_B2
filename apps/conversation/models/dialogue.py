# apps/conversation/models/dialogue.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string

from apps.conversation.constants import (
    DELETE_POLICY_CHOICES,
    GROUP_ROLE_CHOICES,
    PARTICIPANT,
)
from validators.mediaValidators.image_validators import (
    validate_image_file,
    validate_image_size,
)
from validators.security_validators import validate_no_executable_file

from .upload_paths import get_upload_path


class Dialogue(models.Model):
    id = models.BigAutoField(primary_key=True)
    group_name = models.CharField( max_length=255, blank=True, null=True, unique=False, verbose_name="Group Name")
    group_image = models.ImageField(upload_to=get_upload_path('conversation', 'cover', 'group'), validators=[
        validate_image_file, 
        validate_image_size, 
        validate_no_executable_file
    ], blank=True, null=True, verbose_name="Group Image")
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
        """
        Return the latest delivery-ready message globally.
        """
        return (
            self.messages
            .filter(
                is_delivery_ready=True
            )
            .order_by(
                "-timestamp",
                "-id",
            )
            .first()
        )

    def get_last_message_for_user(
        self,
        user,
    ):
        """
        Return the latest visible delivery-ready non-system message
        for one user.
        """
        return (
            self.visible_non_system_messages_for_user(
                user
            )
            .order_by(
                "-timestamp",
                "-id",
            )
            .first()
        )
    # Get visible messages ------------------------------------------------------------------

    def visible_messages_for_user(
        self,
        user,
    ):
        """
        Return delivery-ready messages visible to one user.

        Personal conversations keep their existing visibility semantics.
        Members Community history begins at the current participation start.
        """
        queryset = (
            self.messages
            .filter(
                is_delivery_ready=True
            )
            .exclude(
                deleted_by_users=user
            )
        )

        # Local import avoids a models -> policies -> models import cycle.
        from apps.conversation.policies import ConversationHistoryPolicy

        return ConversationHistoryPolicy.apply_visibility_boundary(
            dialogue=self,
            user=user,
            queryset=queryset,
        )

    def visible_non_system_messages_for_user(
        self,
        user,
    ):
        """
        Return visible delivery-ready non-system messages.
        """
        return (
            self.visible_messages_for_user(
                user
            )
            .filter(
                is_system=False
            )
        )

    def unread_messages_for_user(
        self,
        user,
    ):
        """
        Return unread incoming delivery-ready messages for one user.
        """
        return (
            self.visible_messages_for_user(
                user
            )
            .exclude(
                seen_by_users=user
            )
            .exclude(
                sender=user
            )
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

    def refresh_last_message_cache(
        self,
        save: bool = True,
    ):
        """
        Refresh the global last_message cache using the latest
        delivery-ready non-system message.

        Pending or rejected asynchronous Group Messenger video must
        never become the dialogue's canonical last message.
        """
        last_msg = (
            self.messages
            .filter(
                is_delivery_ready=True
            )
            .exclude(
                is_system=True
            )
            .order_by(
                "-timestamp",
                "-id",
            )
            .first()
        )
        self.last_message = (
            last_msg
            if last_msg
            else None
        )
        if save:
            self.save(
                update_fields=[
                    "last_message"
                ]
            )
        return self.last_message
    # Overriding __str__ method --------------------------------------------

    def __str__(self):
        if self.is_group:
            return f"Group: {self.group_name} with {self.participants.count()} participants"
        return f"Dialogue between: {', '.join([user.username for user in self.participants.all()])}"


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
