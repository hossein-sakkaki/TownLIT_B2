# apps/conversation/models/search.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from django.db import models

from .message import Message


class MessageSearchIndex(models.Model):
    message = models.OneToOneField(Message, on_delete=models.CASCADE, related_name="search_index")
    plaintext = models.TextField()

    def __str__(self):
        return f"SearchIndex for Message {self.message_id}"
