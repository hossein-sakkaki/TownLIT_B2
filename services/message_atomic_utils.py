from django.db import transaction
from asgiref.sync import sync_to_async
from apps.conversation.models import Message


@sync_to_async
def mark_message_as_delivered_atomic(message):
    with transaction.atomic():
        if not message.is_delivered:
            message.is_delivered = True
            message.save(update_fields=["is_delivered"])

@sync_to_async
def mark_message_as_read_atomic(message, user):
    with transaction.atomic():
        if user != message.sender and user not in message.seen_by_users.all():
            message.seen_by_users.add(user)
            message.save()
            

@transaction.atomic
def save_message_atomic(dialogue, sender, content, is_encrypted=False):
    content_to_store = content.encode()
    
    message = Message.objects.create(
        dialogue=dialogue,
        sender=sender,
        content_encrypted=content_to_store,
        is_encrypted=is_encrypted
    )

    dialogue.last_message = message
    dialogue.save(update_fields=['last_message'])

    return message