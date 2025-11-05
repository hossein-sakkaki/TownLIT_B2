from rest_framework import serializers
from django.apps import apps
from apps.posts.models import MediaContent
from apps.accounts.serializers import SimpleCustomUserSerializer 


from apps.posts.constants import REACTION_TYPE_CHOICES
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


# MEDIA CONTENT serializers -----------------------------------------------------------------

class MediaContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MediaContent
        fields = [
            'id', 'content_type', 'title', 'description', 'file', 'link', 
            'published_at', 'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'published_at', 'is_active', 'slug']
    
    def get_file_url(self, obj):
        """Returns full URL of media file."""
        request = self.context.get('request')
        if obj.file:
            return request.build_absolute_uri(obj.file.url) if request else obj.file.url
        return None
