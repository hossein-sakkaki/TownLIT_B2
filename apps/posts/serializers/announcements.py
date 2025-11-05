from rest_framework import serializers
from django.apps import apps
from apps.posts.models import Announcement
from apps.accounts.serializers import SimpleCustomUserSerializer 
from apps.profilesOrg.serializers_min import SimpleOrganizationSerializer

from apps.posts.constants import REACTION_TYPE_CHOICES
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()



# ANNOUNCEMENT serializers -----------------------------------------------------------------
class AnnouncementSerializer(serializers.ModelSerializer):
    # location = serializers.SlugRelatedField(slug_field='address', read_only=True)
    
    class Meta:
        model = Announcement
        fields = [
            'id', 'title', 'description', 'image', 'meeting_type', 'url_link', 'link_sticker_text', 
            'location', 'to_date', 'created_at', 'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['created_at', 'is_active', 'slug']

    def validate(self, data):
        # Custom validation for date fields
        if data['to_date'] and data['created_at'] and data['to_date'] <= data['created_at']:
            raise serializers.ValidationError("Date of Announcement must be after Created Date")
        return data

