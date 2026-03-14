# apps/profiles/serializers_min.py

from rest_framework import serializers
from apps.accounts.serializers.user_serializers import UserMiniSerializer

from .models import Member


# SIMPLE MEMBER Serializers ------------------------------------------------------------------------    
class SimpleMemberSerializer(serializers.ModelSerializer):
    profile_image = serializers.SerializerMethodField()
    class Meta:
        model = Member
        fields = ['id', 'profile_image','slug']
        read_only_fields = ['id', 'slug']
        
    def get_profile_image(self, obj):
        request = self.context.get('request')
        if obj.id.image_name:
            return request.build_absolute_uri(obj.id.image_name.url) if request else obj.id.image_name.url
        return None


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