# apps/profiles/serializers/friendships.py

from rest_framework import serializers
from django.contrib.auth import get_user_model

from apps.profiles.models.relationships import Friendship
from apps.profiles.constants.friendship import FRIENDSHIP_STATUS_CHOICES
from apps.accounts.serializers.user_serializers import SimpleCustomUserSerializer, UserMiniSerializer

CustomUser = get_user_model()



# FRIENDSHIP Serializer ---------------------------------------------------------------
class FriendshipSerializer(serializers.ModelSerializer):
    from_user = SimpleCustomUserSerializer(read_only=True)
    to_user = SimpleCustomUserSerializer(read_only=True)
    to_user_id = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all(), write_only=True)

    class Meta:
        model = Friendship
        fields = ['id', 'from_user', 'to_user', 'to_user_id', 'created_at', 'status', 'deleted_at', 'is_active']
        read_only_fields = ['from_user', 'to_user', 'created_at', 'deleted_at']

    def validate_to_user_id(self, value):
        # Ensures that a user cannot send a friend request to themselves
        if self.context['request'].user == value:
            raise serializers.ValidationError("You cannot send a friend request to yourself.")
        return value

    def validate_status(self, value):
        # Checks if the status is valid
        valid_statuses = [choice[0] for choice in FRIENDSHIP_STATUS_CHOICES]
        if value not in valid_statuses:
            raise serializers.ValidationError("Invalid status for friendship.")
        return value

    def create(self, validated_data):
        from_user = self.context['request'].user
        to_user = validated_data.pop('to_user_id')

        # Check for existing active requests
        existing_request = Friendship.objects.filter(
            from_user=from_user,
            to_user=to_user,
            is_active=True
        ).exclude(status='declined')

        if existing_request.exists():
            raise serializers.ValidationError("Friendship request already exists.")

        validated_data.pop('from_user', None)
        validated_data.pop('to_user', None)
        return Friendship.objects.create(
            from_user=from_user,
            to_user=to_user,
            **validated_data
        )

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # hard guard: if any side is deleted, suppress this record
        try:
            if instance.from_user.is_deleted or instance.to_user.is_deleted:
                return None
        except Exception:
            pass
        return rep


# PEOPLE SUGGESTION Serializer ------------------------------------------------------------------------
class PeopleSuggestionSerializer(UserMiniSerializer):
    """
    Same as UserMiniSerializer + adds:

      - mutual_friends_count
      - mutual_friends (preview avatars)
      - connection hints used in ranking
    """

    mutual_friends_count = serializers.IntegerField(source="mutual_friends", read_only=True)
    mutual_friends = serializers.SerializerMethodField()

    # connection hints
    same_country = serializers.IntegerField(read_only=True)
    same_language = serializers.IntegerField(read_only=True)
    same_branch = serializers.IntegerField(read_only=True)
    same_family = serializers.IntegerField(read_only=True)

    class Meta(UserMiniSerializer.Meta):
        fields = UserMiniSerializer.Meta.fields + [
            "mutual_friends_count",
            "mutual_friends",

            # hints used by UI
            "same_country",
            "same_language",
            "same_branch",
            "same_family",
        ]

    def get_mutual_friends(self, obj):
        """
        Provided by view context:
        { candidate_user_id: [mini_user_dicts...] }
        """
        mp = (self.context or {}).get("mutual_preview_map", {}) or {}
        return mp.get(obj.id, [])