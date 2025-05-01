# apps/conversation/signals.py

from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from apps.conversation.models import Message, Dialogue

@receiver(m2m_changed, sender=Message.seen_by_users.through)
def update_message_read_status(sender, instance, action, pk_set, **kwargs):
    if action == "post_add":
        print(f"✅ User(s) with IDs {pk_set} marked message {instance.id} as read.")


@receiver(m2m_changed, sender=Dialogue.participants.through)
def set_dialogue_slug(sender, instance: Dialogue, action, **kwargs):
    if action == "post_add" and not instance.slug:
        usernames = list(instance.participants.values_list("username", flat=True))

        if instance.is_group:
            slug = Dialogue.generate_dialogue_slug(usernames, instance.name or f"group-{instance.pk}")
        elif len(usernames) == 2:
            slug = Dialogue.generate_dialogue_slug(usernames)
        else:
            return  # Skip if not enough usernames

        instance.slug = slug
        instance.save()