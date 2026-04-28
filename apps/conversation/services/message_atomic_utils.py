# apps/conversation/services/message_atomic_utils.py

from django.db import transaction
from asgiref.sync import sync_to_async


@sync_to_async
def mark_message_as_delivered_atomic(message):
    """
    Persist delivered state atomically.

    Notes:
    - Mutation only
    - No realtime dispatch here
    - Used by conversation delivery flow
    """
    with transaction.atomic():
        if not message.is_delivered:
            message.is_delivered = True
            message.save(update_fields=["is_delivered"])