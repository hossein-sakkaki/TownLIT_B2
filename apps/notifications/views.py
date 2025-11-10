from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone

from .models import UserNotificationPreference, Notification
from .serializers import UserNotificationPreferenceSerializer, NotificationSerializer




# Notification ViewSet ---------------------------------------------------------------
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).select_related(
            'actor', 'target_content_type', 'action_content_type'
        ).order_by('-created_at')

    @action(detail=True, methods=['patch'])
    def mark_read(self, request, pk=None):
        notif = self.get_object()
        ser = NotificationMarkReadSerializer(notif, data={'is_read': True}, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(NotificationSerializer(notif).data)

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        qs = self.get_queryset().filter(is_read=False)
        now = timezone.now()
        qs.update(is_read=True, read_at=now)
        return Response({"updated": qs.count()})

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        cnt = self.get_queryset().filter(is_read=False).count()
        return Response({"unread": cnt})


# User Notification Preference ViewSet -----------------------------------------------
class UserNotificationPreferenceViewSet(viewsets.ModelViewSet):
    serializer_class = UserNotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserNotificationPreference.objects.filter(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

