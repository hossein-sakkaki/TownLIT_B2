from rest_framework import serializers
from django.apps import apps
from apps.posts.models import FutureConference
from apps.accounts.serializers import SimpleCustomUserSerializer 
from apps.profilesOrg.serializers_min import SimpleOrganizationSerializer

from apps.posts.constants import REACTION_TYPE_CHOICES
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


# FUTURE CONFERENCES serializers -----------------------------------------------------------------
class FutureConferenceSerializer(serializers.ModelSerializer):
    in_town_speakers = SimpleCustomUserSerializer(many=True, read_only=True)
    sponsors = SimpleOrganizationSerializer(many=True, read_only=True)

    class Meta:
        model = FutureConference
        fields = [
            'id', 'conference_name', 'registration_required', 'delivery_type', 'conference_location', 
            'registration_link', 'conference_description', 'in_town_speakers', 'out_town_speakers', 
            'sponsors', 'conference_date', 'conference_time', 'conference_end_date', 
            'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'is_active', 'slug']

