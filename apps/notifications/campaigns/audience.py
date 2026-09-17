# apps/notifications/campaigns/audience.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-04.
# Last Update by Hossein Sakkaki on 2026-09-04.
#

from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.accounts.models.devices import UserDeviceKey
from apps.notifications.models import NotificationCampaign


User = get_user_model()


def resolve_campaign_audience(campaign: NotificationCampaign):
    """Build the canonical campaign audience queryset."""
    users = User.objects.filter(
        is_active=True,
        is_deleted=False,
        is_suspended=False,
    )

    if campaign.audience_type == NotificationCampaign.Audience.MEMBERS:
        users = users.filter(is_member=True)

    elif campaign.audience_type == NotificationCampaign.Audience.GUESTS:
        users = users.filter(is_member=False)

    elif campaign.audience_type == NotificationCampaign.Audience.STAFF:
        users = users.filter(
            Q(is_admin=True) | Q(is_superuser=True)
        )

    elif campaign.audience_type == NotificationCampaign.Audience.SELECTED:
        users = users.filter(
            pk__in=campaign.selected_users.values("pk")
        )

    if campaign.platform_scope == NotificationCampaign.Platform.ALL:
        return users.distinct()

    devices = UserDeviceKey.objects.filter(
        is_active=True,
    )

    if campaign.platform_scope == NotificationCampaign.Platform.IOS:
        devices = devices.filter(
            platform__iexact="ios",
            is_verified=True,
        )

    elif campaign.platform_scope == NotificationCampaign.Platform.ANDROID:
        devices = devices.filter(
            platform__iexact="android",
            is_verified=True,
        )

    elif campaign.platform_scope == NotificationCampaign.Platform.WEB:
        devices = devices.filter(
            platform__iexact="web",
        )

    elif campaign.platform_scope == NotificationCampaign.Platform.MOBILE:
        devices = devices.filter(
            platform__in=[
                "ios",
                "android",
            ],
            is_verified=True,
        )

    return users.filter(
        pk__in=devices.values("user_id")
    ).distinct()


def estimate_campaign_audience(campaign: NotificationCampaign) -> int:
    """Return the current estimated audience size."""
    if not campaign.pk:
        return 0

    return resolve_campaign_audience(
        campaign
    ).count()


def push_platforms_for_campaign(
    campaign: NotificationCampaign,
) -> set[str]:
    """Return the allowed Push platforms."""
    mapping = {
        NotificationCampaign.Platform.ALL: {
            "ios",
            "android",
            "web",
        },
        NotificationCampaign.Platform.IOS: {
            "ios",
        },
        NotificationCampaign.Platform.ANDROID: {
            "android",
        },
        NotificationCampaign.Platform.WEB: {
            "web",
        },
        NotificationCampaign.Platform.MOBILE: {
            "ios",
            "android",
        },
    }

    return mapping.get(
        campaign.platform_scope,
        {
            "ios",
            "android",
            "web",
        },
    )