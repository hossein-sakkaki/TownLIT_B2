from rest_framework import serializers
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from apps.posts.models.reaction import Reaction

from apps.posts.constants import REACTION_TYPE_CHOICES
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


# BASE REACTION Serializer ---------------------------------------------------------------------
class ReactionSerializer(serializers.ModelSerializer):
    """
    Serializer for Reaction model.
    Supports flexible content_type input: "testimony", "posts.testimony", or numeric id.
    """

    # write-only input fields
    content_type = serializers.CharField(write_only=True)
    object_id = serializers.IntegerField()
    reaction_type = serializers.ChoiceField(choices=[c[0] for c in REACTION_TYPE_CHOICES])
    message = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=80)

    # read-only output fields
    id = serializers.IntegerField(read_only=True)
    timestamp = serializers.DateTimeField(read_only=True)
    name = serializers.SerializerMethodField(read_only=True)
    content_type_label = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Reaction
        fields = [
            'id',
            'name',
            'reaction_type',
            'message',
            'content_type',
            'object_id',
            'timestamp',
            'content_type_label',
        ]
        read_only_fields = ['id', 'name', 'timestamp', 'content_type_label']

    # --- READ helpers ---
    def get_name(self, obj):
        """Return minimal user info for front-end."""
        u = obj.name
        return {'id': u.id, 'username': getattr(u, 'username', None)}

    def get_content_type_label(self, obj):
        """Return lowercased model name for readability."""
        return obj.content_type.model

    # --- INTERNAL helper: resolve CT string to object ---
    def _resolve_content_type(self, raw: str) -> ContentType:
        """
        Supports:
        - numeric id
        - 'app_label.model'
        - plain model name (scans installed apps)
        """
        raw = str(raw).strip()

        # numeric id
        if raw.isdigit():
            return ContentType.objects.get(pk=int(raw))

        # 'app_label.model'
        if '.' in raw:
            app_label, model = raw.split('.', 1)
            return ContentType.objects.get(app_label=app_label, model=model)

        # bare model name
        ct = ContentType.objects.filter(model=raw).first()
        if ct:
            return ct

        # fallback: brute-force scan across all installed apps
        for m in apps.get_models():
            if m._meta.model_name == raw:
                return ContentType.objects.get_for_model(m)

        raise serializers.ValidationError({'content_type': 'Invalid content type'})

    # --- VALIDATION ---
    def validate(self, attrs):
        # resolve ContentType
        ct = self._resolve_content_type(attrs['content_type'])
        attrs['content_type'] = ct

        # ensure target object exists
        model_class = ct.model_class()
        if not model_class.objects.filter(pk=attrs['object_id']).exists():
            raise serializers.ValidationError({'object_id': 'Target object not found'})

        # normalize empty message to None
        msg = attrs.get('message')
        if msg is not None and msg.strip() == '':
            attrs['message'] = None

        return attrs

    # --- CREATE ---
    def create(self, validated_data):
        """Assign current user as `name` (actor) automatically."""
        user = self.context['request'].user
        validated_data['name'] = user
        return Reaction.objects.create(**validated_data)