# apps/conversation/serializers/participant.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from rest_framework import serializers

from apps.accounts.serializers.user_serializers import SimpleCustomUserSerializer
from apps.conversation.models import DialogueParticipant


class DialogueParticipantSerializer(serializers.ModelSerializer):
    user = SimpleCustomUserSerializer(read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = DialogueParticipant
        fields = ['user', 'role', 'role_display']
        read_only_fields = ['role_display']
