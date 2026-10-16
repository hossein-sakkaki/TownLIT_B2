# apps/conversation/models/encryption.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from django.db import models

from .message import Message


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
