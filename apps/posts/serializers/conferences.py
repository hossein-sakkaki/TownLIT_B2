from rest_framework import serializers
from django.apps import apps
from apps.posts.models import Conference
from apps.accounts.serializers import SimpleCustomUserSerializer 

from apps.posts.constants import REACTION_TYPE_CHOICES
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()



# CONFERENCES serializers -----------------------------------------------------------------
class ConferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conference
        fields = [
            'id', 'conference_name', 'workshops', 'conference_resources', 'description', 
            'conference_date', 'conference_time', 'conference_end_date', 
            'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'is_active','slug']


