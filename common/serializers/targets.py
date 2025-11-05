# common/serializers/targets.py
from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
import traceback, logging
logger = logging.getLogger(__name__)

class InstanceTargetMixin(serializers.Serializer):
    """Builds per-item targets for comments/reactions."""
    comment_target = serializers.SerializerMethodField(read_only=True)
    reaction_target = serializers.SerializerMethodField(read_only=True)

    def _build_instance_target(self, obj):
        try:
            ct = ContentType.objects.get_for_model(obj.__class__, for_concrete_model=False)
            return {
                "content_type": f"{ct.app_label}.{ct.model}",
                "content_type_id": ct.id,
                "object_id": obj.pk,
            }
        except Exception:
            logger.error("build_instance_target failed id=%s\n%s", getattr(obj, "id", None), traceback.format_exc())
            return None

    def get_comment_target(self, obj):
        return self._build_instance_target(obj)

    def get_reaction_target(self, obj):
        return self._build_instance_target(obj)
