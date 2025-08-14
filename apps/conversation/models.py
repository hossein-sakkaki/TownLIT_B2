from django.db import models
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
    DELETE_POLICY_CHOICES, MESSAGE_POLICY_CHOICES, KEEP, 
    GROUP_ROLE_CHOICES, PARTICIPANT, SYSTEM_MESSAGE_EVENT_CHOICES,
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


    # ✅ بررسی اینکه آیا کاربر نقش خاصی دارد
    def has_role(self, user, role: str) -> bool:
        return self.participants_roles.filter(user=user, role=role).exists()

    # ✅ بررسی اینکه آیا کاربر founder است
    def is_founder(self, user) -> bool:
        return self.has_role(user, 'founder')

    # ✅ بررسی اینکه آیا کاربر elder است
    def is_elder(self, user) -> bool:
        return self.has_role(user, 'elder')

    # ✅ بررسی اینکه آیا گروه حداقل دو elder دارد (برای انتقال اختیارات در آینده)
    def has_multiple_elders(self):
        return self.participants_roles.filter(role='elder').count() > 1

    # ✅ بررسی اینکه آیا کاربر عضو تیم مدیریت است (founder یا elder)
    def is_group_manager(self, user) -> bool:
        return self.participants_roles.filter(user=user, role__in=['founder', 'elder']).exists()


    # Soft delete the dialogue and Messages from the user's profile
    def mark_as_deleted_by_user(self, user):
        self.deleted_by_users.add(user)
        self.messages.all().update()
        
        for message in self.messages.all():
            message.deleted_by_users.add(user)

    def leave_group(self, user):
        """Remove user from group participants and delete their participation record."""
        self.participants.remove(user)  # Remove from ManyToManyField
        self.mark_as_deleted_by_user(user)  # Soft delete
        DialogueParticipant.objects.filter(dialogue=self, user=user).delete()

        
    def restore_dialogue(self, user):
        """ 🔹 اگر کاربر چت را حذف کرده بود، مجدداً به لیستش اضافه شود """
        self.deleted_by_users.remove(user)

    def get_last_message(self):
        """ 🔹 آخرین پیام قابل مشاهده را بازمی‌گرداند (با در نظر گرفتن حذف نرم) """
        return self.messages.exclude(id__in=self.deleted_by_users.values_list("id", flat=True)).last()

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
            self.encrypted_for_device = receiver_device_id  # 🟢 اضافه شد
        else:
            self.content_encrypted = new_content.encode()
            self.encrypted_for_device = None  # اگر رمزنگاری نشده باشد
        
        self.edited_at = timezone.now()
        self.is_edited = True
        self.save()

        
    def can_edit(self):
        return timezone.now() <= self.timestamp + timedelta(hours=12)

    def mark_as_deleted_by_user(self, user):
        self.deleted_by_users.add(user)
        self.save()
        last_message = self.dialogue.messages.exclude(deleted_by_users=user).order_by('-timestamp').first()
        self.dialogue.last_message = last_message if last_message else None
        self.dialogue.save()

    def can_be_fully_deleted(self, user):
        if user == self.sender:
            return self.seen_by_users.count() == 0

        if self.dialogue.is_group and self.dialogue.is_founder(user):
            return True

        return False


    def delete_message_completely(self):
        if self.can_be_fully_deleted():
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
