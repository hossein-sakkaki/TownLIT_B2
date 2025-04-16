# apps/conversation/signals.py

from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from apps.conversation.models import Message

@receiver(m2m_changed, sender=Message.seen_by_users.through)
def update_message_read_status(sender, instance, action, pk_set, **kwargs):
    if action == "post_add":
        print(f"✅ User(s) with IDs {pk_set} marked message {instance.id} as read.")
