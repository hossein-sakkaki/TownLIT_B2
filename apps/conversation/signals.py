# apps/conversation/signals.py

from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver
import base64
from apps.conversation.models import Message, MessageSearchIndex


@receiver(m2m_changed, sender=Message.seen_by_users.through)
def update_message_read_status(sender, instance, action, pk_set, **kwargs):
    if action == "post_add":
        print(f"✅ User(s) with IDs {pk_set} marked message {instance.id} as read.")


@receiver(post_save, sender=Message)
def create_or_update_search_index(sender, instance, created, **kwargs):
    # Just Groups Messages
    if not instance.encryptions.exists():
        try:
            decoded = base64.b64decode(instance.content_encrypted).decode("utf-8")
        except Exception:
            decoded = ""

        MessageSearchIndex.objects.update_or_create(
            message=instance,
            defaults={"plaintext": decoded}
        )
    else:
        MessageSearchIndex.objects.filter(message=instance).delete()