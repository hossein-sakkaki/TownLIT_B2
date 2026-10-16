# apps/conversation/serializers/marker.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from rest_framework import serializers

from apps.conversation.models import UserDialogueMarker


class UserDialogueMarkerSerializer(serializers.ModelSerializer):
    dialogue_id = serializers.IntegerField(source='dialogue.id', read_only=True)
    dialogue_slug = serializers.CharField(source='dialogue.slug', read_only=True)

    class Meta:
        model = UserDialogueMarker
        fields = ['id', 'user', 'dialogue_id', 'dialogue_slug', 'is_sensitive', 'delete_policy']
