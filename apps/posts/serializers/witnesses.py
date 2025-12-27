from rest_framework import serializers
from django.apps import apps
from apps.posts.models.witness import Witness
            

from apps.posts.constants import REACTION_TYPE_CHOICES
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()




# WITNESS serializers -----------------------------------------------------------------
class WitnessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Witness
        fields = [
            'id', 'title', 'testimony', 're_published_at',
            'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['re_published_at', 'is_active', 'slug']
