from rest_framework import serializers
from django.apps import apps
from apps.posts.models import Library
from apps.accounts.serializers import SimpleCustomUserSerializer 


from apps.posts.constants import REACTION_TYPE_CHOICES
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

# LIBRARY serializers -----------------------------------------------------------------
class LibrarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Library
        fields = [
            'id', 'book_name', 'author', 'publisher_name', 'language', 'translation_language', 'translator', 
            'genre_type', 'image', 'pdf_file', 'license_type', 'sale_status', 'license_document',
            'is_upcoming', 'is_downloadable', 'has_print_version', 'downloaded', 'published_date', 
            'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'downloaded', 'published_date', 'is_active', 'slug']

    def get_file_url(self, obj):
        """Returns full URL of the PDF file."""
        request = self.context.get('request')
        if obj.pdf_file:
            return request.build_absolute_uri(obj.pdf_file.url) if request else obj.pdf_file.url
        return None
