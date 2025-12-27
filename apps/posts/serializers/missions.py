from rest_framework import serializers
from django.apps import apps
from apps.posts.models.mission import Mission
from apps.accounts.serializers import SimpleCustomUserSerializer 


from apps.posts.constants import REACTION_TYPE_CHOICES
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


# MISSION serializers -----------------------------------------------------------------
class MissionSerializer(serializers.ModelSerializer):
    contact_persons = SimpleCustomUserSerializer(many=True, read_only=True)
    
    class Meta:
        model = Mission
        fields = [
            'id', 'image_or_video', 'mission_name', 'description', 'start_date', 'end_date', 
            'is_ongoing', 'location', 'contact_persons', 'funding_goal', 'raised_funds', 'funding_link', 
            'volunteer_opportunities', 'mission_report', 'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'is_active', 'is_ongoing', 'slug']

    def get_image_or_video_url(self, obj):
        """Returns full URL of the image or video file."""
        request = self.context.get('request')
        if obj.image_or_video:
            return request.build_absolute_uri(obj.image_or_video.url) if request else obj.image_or_video.url
        return None