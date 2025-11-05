from rest_framework import serializers
from django.apps import apps
from apps.posts.models import Pray
            
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model
CustomUser = get_user_model()



# PRAY serializers -----------------------------------------------------------------
class PraySerializer(serializers.ModelSerializer):
    sub_prays = serializers.SerializerMethodField()

    class Meta:
        model = Pray
        fields = [
            'id', 'title', 'content', 'image', 'parent', 'sub_prays',
            'published_at', 'updated_at', 'is_accepted', 'is_rejected',
            'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['published_at', 'updated_at', 'is_active', 'slug']

    def get_sub_prays(self, obj):
        # Fetch and serialize sub-prays
        if obj.sub_prays.exists():
            return PraySerializer(obj.sub_prays.all(), many=True).data
        return None

