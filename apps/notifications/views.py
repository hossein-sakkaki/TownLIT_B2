# apps/notifications/views.py

import logging

from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.pagination import ConfigurablePagination
from apps.notifications.constants import (
    CHANNEL_EMAIL,
    CHANNEL_PUSH,
    NOTIFICATION_PREF_METADATA,
    NOTIFICATION_TYPES_EXCLUDED_FROM_GENERAL_UNREAD,
    NOTIFICATION_TYPES_EXCLUDED_FROM_NOTIFICATION_CENTER,
    NOTIFICATION_TYPES_FORCE_ENABLED,
    notification_default_channels,
    notification_supports_email,
    notification_supports_push,
    sanitize_notification_channels,
)
from apps.notifications.models import (
    UserNotificationPreference,
    Notification,
)
from apps.notifications.serializers import (
    UserNotificationPreferenceSerializer,
    NotificationSerializer,
    NotificationMarkReadSerializer,
)
from apps.notifications.utils import get_allowed_notification_types_for_user

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Pagination for notifications
# -------------------------------------------------------------------
class NotificationPagination(ConfigurablePagination):
    """
    Pagination for notifications.

    Rules:
    - default page size: 20
    - max page size: 20
    """
    page_size = 20
    max_page_size = 20


# -------------------------------------------------------------------
# Notification ViewSet
# -------------------------------------------------------------------
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List and read user notifications.

    Messenger notifications are intentionally excluded from this center.
    Messenger has its own inbox, unread counter, realtime flow, and push flow.
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NotificationPagination

    pagination_page_size = 20
    page_size = 20
    max_page_size = 20

    def get_queryset(self):
        """
        Return visible general notifications for the current user.

        Message notification records are excluded even if old records exist
        in the database from previous versions.
        """
        qs = (
            Notification.objects
            .filter(user=self.request.user)
            .exclude(
                notification_type__in=NOTIFICATION_TYPES_EXCLUDED_FROM_NOTIFICATION_CENTER
            )
            .select_related(
                "actor",
                "actor__member_profile",
                "actor__label",
            )
            .order_by("-created_at")
        )

        self._auto_prune_stale_notifications(qs)

        return qs

    def _auto_prune_stale_notifications(self, qs):
        """
        Bounded safety-net cleanup.

        This only checks visible notification-center records.
        It does not touch push-only messenger behavior.
        """
        sample_limit = 200

        stale_ids = [
            notif.id
            for notif in qs[:sample_limit]
            if notif.is_target_unavailable()
        ]

        if stale_ids:
            logger.info(
                "[Notifications] Auto-pruning %d stale notifications for user %s",
                len(stale_ids),
                self.request.user.pk,
            )
            Notification.objects.filter(id__in=stale_ids).delete()

    @action(detail=True, methods=["patch"])
    def mark_read(self, request, pk=None):
        """
        Mark a single visible notification as read.

        Because get_queryset excludes messenger notification records,
        old messenger notification rows cannot be marked through this endpoint.
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

        notif.refresh_from_db()

        return Response(
            NotificationSerializer(
                notif,
                context={"request": request},
            ).data
        )

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        """
        Mark all visible general notifications as read.

        Messenger messages are not included here because Messenger read state
        is controlled by the conversation read/delivery system.
        """
        qs = self.get_queryset().filter(is_read=False)

        now = timezone.now()
        updated = qs.update(
            is_read=True,
            read_at=now,
        )

        return Response({"updated": updated})

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        """
        Return unread general notification count for current user.

        Messenger notifications are excluded because Messenger has its own
        unread source from Dialogue unread messages.
        """
        count = (
            Notification.objects
            .filter(
                user=request.user,
                is_read=False,
            )
            .exclude(
                notification_type__in=NOTIFICATION_TYPES_EXCLUDED_FROM_GENERAL_UNREAD
            )
            .count()
        )

        return Response({"unread": count})


# -------------------------------------------------------------------
# User Notification Preference ViewSet
# -------------------------------------------------------------------
class UserNotificationPreferenceViewSet(viewsets.ModelViewSet):
    """
    Manage general notification preferences.

    Messenger notification types are intentionally excluded from this endpoint.
    Messenger should later use conversation-level mute/silence settings instead.

    Email policy:
    - Frequent interaction/feed/friendship notifications still appear as
      configurable notification types.
    - Their email channel is unsupported and stripped.
    - Frontend should hide email toggles when email_supported=false.
    """
    serializer_class = UserNotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]

    def _allowed_preference_types_for_user(self, user) -> set[str]:
        """
        Return notification types that are actually user-configurable.

        Message notification types are force-enabled/push-only and should not
        appear in general preference settings.
        """
        allowed_types = get_allowed_notification_types_for_user(user)

        return set(allowed_types) - set(NOTIFICATION_TYPES_FORCE_ENABLED)

    def get_queryset(self):
        """
        Return only valid general notification preferences for current user.

        Rules:
        - Member users can have general notification preference types.
        - Guest users can only have guest-safe general types.
        - Messenger preference rows are excluded and pruned.
        - Missing valid preferences are auto-created.
        - Unsupported email bits are stripped from existing rows.
        """
        user = self.request.user
        allowed_types = self._allowed_preference_types_for_user(user)

        qs = UserNotificationPreference.objects.filter(
            user=user,
            notification_type__in=allowed_types,
        )

        existing_types = set(
            qs.values_list("notification_type", flat=True)
        )
        missing_types = allowed_types - existing_types

        if missing_types:
            objs = [
                UserNotificationPreference(
                    user=user,
                    notification_type=notif_type,
                    enabled=True,
                    channels_mask=notification_default_channels(notif_type),
                )
                for notif_type in missing_types
            ]
            UserNotificationPreference.objects.bulk_create(objs)

        # Prune invalid or no-longer-user-configurable preference rows.
        # This removes old message preference rows too.
        UserNotificationPreference.objects.filter(user=user).exclude(
            notification_type__in=allowed_types
        ).delete()

        # Strip unsupported channels from old rows.
        valid_qs = UserNotificationPreference.objects.filter(
            user=user,
            notification_type__in=allowed_types,
        )

        dirty_ids = []

        for pref in valid_qs:
            sanitized = sanitize_notification_channels(
                pref.notification_type,
                pref.channels_mask,
            )

            if sanitized != pref.channels_mask:
                pref.channels_mask = sanitized
                dirty_ids.append(pref.id)
                pref.save(update_fields=["channels_mask"])

        if dirty_ids:
            logger.info(
                "[Notifications] Sanitized unsupported channels user=%s preference_ids=%s",
                getattr(user, "id", None),
                dirty_ids,
            )

        return UserNotificationPreference.objects.filter(
            user=user,
            notification_type__in=allowed_types,
        ).order_by("notification_type")

    def perform_update(self, serializer):
        serializer.save(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["patch"])
    def enable_email(self, request, pk=None):
        pref = self.get_object()

        if notification_supports_email(pref.notification_type):
            pref.channels_mask |= CHANNEL_EMAIL
        else:
            pref.channels_mask &= ~CHANNEL_EMAIL

        pref.channels_mask = sanitize_notification_channels(
            pref.notification_type,
            pref.channels_mask,
        )
        pref.save(update_fields=["channels_mask"])

        return Response(
            UserNotificationPreferenceSerializer(
                pref,
                context={"request": request},
            ).data
        )

    @action(detail=True, methods=["patch"])
    def disable_email(self, request, pk=None):
        pref = self.get_object()
        pref.channels_mask &= ~CHANNEL_EMAIL
        pref.save(update_fields=["channels_mask"])

        return Response(
            UserNotificationPreferenceSerializer(
                pref,
                context={"request": request},
            ).data
        )

    @action(detail=True, methods=["patch"])
    def enable_push(self, request, pk=None):
        pref = self.get_object()

        if notification_supports_push(pref.notification_type):
            pref.channels_mask |= CHANNEL_PUSH

        pref.channels_mask = sanitize_notification_channels(
            pref.notification_type,
            pref.channels_mask,
        )
        pref.save(update_fields=["channels_mask"])

        return Response(
            UserNotificationPreferenceSerializer(
                pref,
                context={"request": request},
            ).data
        )

    @action(detail=True, methods=["patch"])
    def disable_push(self, request, pk=None):
        pref = self.get_object()
        pref.channels_mask &= ~CHANNEL_PUSH

        pref.channels_mask = sanitize_notification_channels(
            pref.notification_type,
            pref.channels_mask,
        )
        pref.save(update_fields=["channels_mask"])

        return Response(
            UserNotificationPreferenceSerializer(
                pref,
                context={"request": request},
            ).data
        )

    @action(detail=False, methods=["post"])
    def reset_defaults(self, request):
        prefs = self.get_queryset()

        for pref in prefs:
            pref.enabled = True
            pref.channels_mask = notification_default_channels(
                pref.notification_type
            )
            pref.save(update_fields=["enabled", "channels_mask"])

        refreshed = self.get_queryset()

        return Response(
            UserNotificationPreferenceSerializer(
                refreshed,
                many=True,
                context={"request": request},
            ).data
        )

    @action(detail=False, methods=["get"])
    def metadata(self, request):
        """
        Return metadata for user-configurable general notification preferences.

        Messenger is excluded because it is controlled by Messenger-specific
        read/unread and future mute settings.

        Email support is exposed per notification type so frontend can hide
        email toggles where email is no longer a supported channel.
        """
        allowed_types = self._allowed_preference_types_for_user(request.user)

        filtered = {}

        for notif_type, meta in NOTIFICATION_PREF_METADATA.items():
            if notif_type not in allowed_types:
                continue

            supports_email = notification_supports_email(notif_type)
            supports_push = notification_supports_push(notif_type)

            supported_channels = []

            if supports_push:
                supported_channels.append("push")

            if supports_email:
                supported_channels.append("email")

            filtered[notif_type] = {
                **meta,
                "email_supported": supports_email,
                "push_supported": supports_push,
                "supported_channels": supported_channels,
                "default_channels_mask": notification_default_channels(notif_type),
            }

        return Response(filtered)