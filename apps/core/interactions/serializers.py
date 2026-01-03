# apps/core/interactions/serializers.py

from rest_framework import serializers
from apps.posts.constants import REACTION_TYPE_CHOICES




# Reaction Summary Serializer ----------------------------------------------------------------------------
class ReactionSummarySerializer(serializers.Serializer):
    """
    Lightweight aggregation payload for hover / modal.
    """

    # totals
    reactions_count = serializers.IntegerField()

    # per-type breakdown
    reactions_breakdown = serializers.DictField(
        child=serializers.IntegerField(),
        allow_empty=True,
    )

    # current user's reaction (if any)
    my_reaction = serializers.CharField(
        allow_null=True,
        required=False,
    )


# Reaction Toggle Serializer -----------------------------------------------------------------------------
class ReactionToggleSerializer(serializers.Serializer):
    content_type = serializers.CharField()
    object_id = serializers.IntegerField()
    reaction_type = serializers.ChoiceField(choices=REACTION_TYPE_CHOICES)