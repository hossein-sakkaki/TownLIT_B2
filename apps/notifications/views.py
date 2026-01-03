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
from .constants import (
    CHANNEL_EMAIL, CHANNEL_PUSH, CHANNEL_DEFAULT,
    NOTIFICATION_PREF_METADATA, NOTIFICATION_TYPES,
    NOTIFICATION_TYPES_PUSH_EMAIL_ONLY
)

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------س
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
    pagination_class = ConfigurablePagination
    pagination_page_size = 20   # 🔑 only source of truth
    page_size = 20              # backward safety
    max_page_size = 20

    # -----------------------------------------------------------------
    def get_queryset(self):
        qs = (
            Notification.objects
            .filter(user=self.request.user)
            .exclude(notification_type__in=NOTIFICATION_TYPES_PUSH_EMAIL_ONLY)
            .select_related(
                "actor",
                "actor__member_profile",
                "actor__label",
            )
            .order_by("-created_at")
        )

        # ⚠️ prune safely (bounded + no cascade)
        self._auto_prune_stale_notifications(qs)

        return qs

    # -----------------------------------------------------------------
    def _auto_prune_stale_notifications(self, qs):
        """
        Bounded safety-net cleanup.
        Does NOT affect pagination logic.
        """
        SAMPLE_LIMIT = 200

        stale_ids = [
            notif.id
            for notif in qs[:SAMPLE_LIMIT]
            if notif.is_target_unavailable()
        ]

        if stale_ids:
            logger.info(
                "[Notifications] Auto-pruning %d stale notifications for user %s",
                len(stale_ids),
                self.request.user.pk,
            )
            Notification.objects.filter(id__in=stale_ids).delete()

    # Mark read action ------------------------------------------------
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
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Ensure read_at and computed fields are fresh
        notif.refresh_from_db()

        return Response(
            NotificationSerializer(
                notif,
                context={"request": request},
            ).data
        )

    # Mark all read action ---------------------------------------------
    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        """
        Mark all unread notifications of current user as read.
        (Scoped to the same visibility rules as list view.)
        """
        qs = self.get_queryset().filter(is_read=False)

        now = timezone.now()
        updated = qs.update(
            is_read=True,
            read_at=now,
        )

        return Response({"updated": updated})

    # Unread count action ---------------------------------------------
    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        """
        Return unread notification count for current user.
        """
        count = (
            Notification.objects
            .filter(
                user=request.user,
                is_read=False,
            )
            .exclude(notification_type__in=NOTIFICATION_TYPES_PUSH_EMAIL_ONLY)
            .count()
        )

        return Response({"unread": count})



# -------------------------------------------------------------------
# User Notification Preference ViewSet  (Final Auto-Sync Version)
# -------------------------------------------------------------------

class UserNotificationPreferenceViewSet(viewsets.ModelViewSet):
    serializer_class = UserNotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return all preferences for the current user.
        - Auto-create if user has none.
        - Auto-sync missing notification types (for old accounts).
        """
        user = self.request.user

        # Fetch existing prefs
        qs = UserNotificationPreference.objects.filter(user=user)

        # ------------------------------------------------------------
        # 1) If user has zero, create ALL defaults (first-time user)
        # ------------------------------------------------------------
        if qs.count() == 0:
            objs = [
                UserNotificationPreference(
                    user=user,
                    notification_type=notif_type,
                    enabled=True,
                    channels_mask=CHANNEL_DEFAULT,
                )
                for notif_type, _ in NOTIFICATION_TYPES
            ]
            UserNotificationPreference.objects.bulk_create(objs)
            qs = UserNotificationPreference.objects.filter(user=user)

        # ------------------------------------------------------------
        # 2) Auto-sync missing types (new types added later)
        # ------------------------------------------------------------
        existing_types = set(qs.values_list("notification_type", flat=True))
        all_types = set(nt[0] for nt in NOTIFICATION_TYPES)

        missing_types = all_types - existing_types

        if missing_types:
            # Create only missing prefs
            new_objs = [
                UserNotificationPreference(
                    user=user,
                    notification_type=notif_type,
                    enabled=True,
                    channels_mask=CHANNEL_DEFAULT,
                )
                for notif_type in missing_types
            ]
            UserNotificationPreference.objects.bulk_create(new_objs)

            # Reload full queryset
            qs = UserNotificationPreference.objects.filter(user=user)

        return qs

    # ------------------------------------------------------------
    # Standard create/update behavior
    # ------------------------------------------------------------
    def perform_update(self, serializer):
        serializer.save(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    # ------------------------------------------------------------
    # Extra actions (email/push toggles)
    # ------------------------------------------------------------
    @action(detail=True, methods=["patch"])
    def enable_email(self, request, pk=None):
        pref = self.get_object()
        pref.channels_mask |= CHANNEL_EMAIL
        pref.save(update_fields=["channels_mask"])
        return Response(UserNotificationPreferenceSerializer(pref).data)

    @action(detail=True, methods=["patch"])
    def disable_email(self, request, pk=None):
        pref = self.get_object()
        pref.channels_mask &= ~CHANNEL_EMAIL
        pref.save(update_fields=["channels_mask"])
        return Response(UserNotificationPreferenceSerializer(pref).data)

    @action(detail=True, methods=["patch"])
    def enable_push(self, request, pk=None):
        pref = self.get_object()
        pref.channels_mask |= CHANNEL_PUSH
        pref.save(update_fields=["channels_mask"])
        return Response(UserNotificationPreferenceSerializer(pref).data)

    @action(detail=True, methods=["patch"])
    def disable_push(self, request, pk=None):
        pref = self.get_object()
        pref.channels_mask &= ~CHANNEL_PUSH
        pref.save(update_fields=["channels_mask"])
        return Response(UserNotificationPreferenceSerializer(pref).data)

    # ------------------------------------------------------------
    # Reset all user preferences to defaults
    # ------------------------------------------------------------
    @action(detail=False, methods=["post"])
    def reset_defaults(self, request):
        prefs = self.get_queryset()
        prefs.update(
            enabled=True,
            channels_mask=CHANNEL_DEFAULT,
        )
        return Response(
            UserNotificationPreferenceSerializer(prefs, many=True).data
        )

    # ------------------------------------------------------------
    # Metadata endpoint
    # ------------------------------------------------------------
    @action(detail=False, methods=["get"])
    def metadata(self, request):
        """Return UI-friendly metadata."""
        return Response(NOTIFICATION_PREF_METADATA)
