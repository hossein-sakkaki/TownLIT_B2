# apps/conversation/serializers/reactions.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from rest_framework import serializers

from apps.accounts.serializers.user_serializers import SimpleCustomUserSerializer
from apps.conversation.models import MessageReaction


class MessageReactionSerializer(serializers.ModelSerializer):
    user = SimpleCustomUserSerializer(read_only=True)

    class Meta:
        model = MessageReaction
        fields = [
            "id",
            "reaction_type",
            "created_at",
            "updated_at",
            "user",
        ]
