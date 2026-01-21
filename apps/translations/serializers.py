# apps/translations/serializers.py

from rest_framework import serializers


class TranslationRequestSerializer(serializers.Serializer):
    """Translation request payload."""
    target_language = serializers.CharField(
        max_length=5,
        required=False,
        help_text="Optional target language override.",
    )
