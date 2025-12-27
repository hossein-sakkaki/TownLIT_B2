from rest_framework import serializers
from django.apps import apps
from apps.posts.models.worship import Worship
from apps.accounts.serializers import SimpleCustomUserSerializer 


from apps.posts.constants import REACTION_TYPE_CHOICES
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()





# WORSHIP serializers -----------------------------------------------------------------
class WorshipSerializer(serializers.ModelSerializer):
    in_town_leaders = SimpleCustomUserSerializer(many=True, read_only=True)
    sub_worship = serializers.SerializerMethodField()

    class Meta:
        model = Worship
        fields = [
            'id', 'title', 'season', 'episode', 'sermon', 'hymn_lyrics', 
            'in_town_leaders', 'out_town_leaders', 'worship_resources', 
            'image', 'audio', 'video', 'parent', 'sub_worship', 'view', 
            'published_at', 'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'view', 'published_at', 'is_active', 'slug']

    def get_sub_worship(self, obj):
        # Fetch and serialize sub-worships
        if obj.sub_worship.exists():
            return WorshipSerializer(obj.sub_worship.all(), many=True).data
        return None