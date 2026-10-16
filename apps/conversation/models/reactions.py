# apps/conversation/models/reactions.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from django.conf import settings
from django.db import models

from apps.conversation.constants import MESSAGE_REACTION_TYPE_CHOICES

from .message import Message


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
