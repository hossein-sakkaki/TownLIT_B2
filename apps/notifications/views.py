# apps/notifications/views.py

import logging
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import UserNotificationPreference, Notification
from .serializers import (
    UserNotificationPreferenceSerializer,
    NotificationSerializer,
    NotificationMarkReadSerializer,
)
from apps.core.pagination import ConfigurablePagination  # ✅ your shared pagination

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Pagination for notifications: 20 per page, up to last 200 records
# -------------------------------------------------------------------
class NotificationPagination(ConfigurablePagination):
    """
    Pagination for notifications:
    - default page size: 20
    - max page size: 20 (no huge pages)
    """
    page_size = 20
    max_page_size = 20  # keep small and predictable


# -------------------------------------------------------------------
# Notification ViewSet  (read-only + mark_read helpers)
# -------------------------------------------------------------------
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List and read user notifications.
    - Uses pagination (20 per page).
    - Only the last ~200 notifications are exposed.
    - Auto-prunes stale notifications whose targets are gone/hidden.
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NotificationPagination  # ✅ enable pagination

    def get_queryset(self):
        """
        Base queryset for current user.
        Additionally:
        - auto-remove stale notifications (defense-in-depth).
        """
        qs = (
            Notification.objects.filter(user=self.request.user)
            .select_related(
                "actor",
                "actor__member_profile",
                "actor__label",
            )
            .order_by("-created_at")
        )

        # ❌ این خط را حذف کن
        # qs = qs[:200]

        # 🔹 Optional safety net: remove any stale notifications on-the-fly
        self._auto_prune_stale_notifications(qs)

        return qs


    def _auto_prune_stale_notifications(self, qs):
        """
        Auto-delete notifications whose targets are no longer available.
        This is a safety net on top of signals. Limit to first N rows
        so that the cost remains small.
        """
        sample_size = 200  # small bounded scan
        stale_ids = []

        for notif in qs[:sample_size]:
            # `is_target_unavailable` is defined on Notification model
            if notif.is_target_unavailable():
                stale_ids.append(notif.id)

        if stale_ids:
            logger.info(
                "[Notifications] Auto-pruning %d stale notifications for user %s",
                len(stale_ids),
                getattr(self.request.user, "pk", None),
            )
            Notification.objects.filter(id__in=stale_ids).delete()

    # ---------------------- Actions ----------------------

    @action(detail=True, methods=["patch"])
    def mark_read(self, request, pk=None):
        """
        Mark a single notification as read.
        """
        notif = self.get_object()

        serializer = NotificationMarkReadSerializer(
            notif,
            data={"is_read": True},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Refresh from DB to ensure read_at and other fields are correct
        notif.refresh_from_db()

        # Serialize with full serializer, fallback on error
        try:
            data = NotificationSerializer(notif).data
        except Exception as exc:
            logger.warning(
                "[Notif] Fallback serialization for %s: %s",
                notif.id,
                exc,
            )
            data = {
                "id": notif.id,
                "message": notif.message,
                "is_read": notif.is_read,
                "read_at": notif.read_at,
                "notification_type": notif.notification_type,
            }

        return Response(data)

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        """
        Mark all unread notifications of current user as read.
        (Only within the visible subset from get_queryset.)
        """
        qs = self.get_queryset().filter(is_read=False)
        now = timezone.now()
        updated = qs.update(is_read=True, read_at=now)
        return Response({"updated": updated})

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        qs = (
            Notification.objects
            .filter(user=request.user, is_read=False)
            .order_by("-created_at")[:200]
        )
        return Response({"unread": qs.count()})



# -------------------------------------------------------------------
# User Notification Preference ViewSet
# -------------------------------------------------------------------
class UserNotificationPreferenceViewSet(viewsets.ModelViewSet):
    """
    CRUD for user's notification preferences (per user).
    """
    serializer_class = UserNotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only preferences of current user
        return UserNotificationPreference.objects.filter(user=self.request.user)

    def perform_update(self, serializer):
        # Force user to be current user
        serializer.save(user=self.request.user)

    def perform_create(self, serializer):
        # Force user to be current user
        serializer.save(user=self.request.user)
