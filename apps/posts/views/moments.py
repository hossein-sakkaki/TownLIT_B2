# apps/posts/views/missions.py

from django.utils import timezone
from django.contrib.contenttypes.models import ContentType 
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets

from apps.posts.models.moment import Moment
from apps.posts.serializers.moments import MomentSerializer



# Moment ViewSet ---------------------------------------------------------------------------------------------------
# apps/posts/views/moments.py
class MomentViewSet(viewsets.ModelViewSet):
    serializer_class = MomentSerializer
    permission_classes = [IsAuthenticated]
    queryset = Moment.objects.filter(is_active=True).select_related("content_type")
    lookup_field = "slug"

    def perform_create(self, serializer):
        owner = getattr(self.request.user, "member", None)
        serializer.save(
            content_type=ContentType.objects.get_for_model(owner.__class__),
            object_id=owner.id,
        )