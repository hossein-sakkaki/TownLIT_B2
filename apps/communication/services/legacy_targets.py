# apps/communication/services/legacy_targets.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from django.contrib.auth import get_user_model
from django.db.models import QuerySet

from apps.communication.constants import (
    ACCESS_REQUESTS,
    ADMINS,
    ALL_ACTIVE,
    BELIEVER,
    DELETED_MEMBERS,
    DELETED_NON_MEMBERS,
    PREFER_NOT,
    PRIVACY_ENABLED,
    RE_ENGAGEMENT,
    SANCTUARY_PARTICIPANTS,
    SEEKER,
    SEEKER_AND_PREFER_NOT,
    SUSPENDED_USERS,
    TOWNLIT_NOT_VERIFIED,
    TOWNLIT_VERIFIED,
    UNVERIFIED_IDENTITY,
    UNUSED_INVITE_ACCESS,
)
from apps.communication.models import UnsubscribedUser
from apps.moderation.models import AccessRequest


CustomUser = get_user_model()


def resolve_preset_objects(preset_key):
    """
    Resolve a built-in or legacy audience preset.

    Legacy AccessRequest targeting lives only in this module.
    """

    users = CustomUser.objects.all()

    if preset_key == ALL_ACTIVE:
        return users.filter(is_active=True)

    if preset_key == BELIEVER:
        return users.filter(
            is_active=True,
            label__name="believer",
        ).distinct()

    if preset_key == SEEKER:
        return users.filter(
            is_active=True,
            label__name="seeker",
        ).distinct()

    if preset_key == PREFER_NOT:
        return users.filter(
            is_active=True,
            label__name="prefer_not_to_say",
        ).distinct()

    if preset_key == SEEKER_AND_PREFER_NOT:
        return users.filter(
            is_active=True,
            label__name__in=[
                "seeker",
                "prefer_not_to_say",
            ],
        ).distinct()

    if preset_key == ADMINS:
        return users.filter(
            is_active=True,
            is_admin=True,
        )

    if preset_key == DELETED_MEMBERS:
        return users.filter(
            is_active=False,
            member_profile__isnull=False,
        )

    if preset_key == DELETED_NON_MEMBERS:
        return users.filter(
            is_active=False,
            member_profile__isnull=True,
        )

    if preset_key == SUSPENDED_USERS:
        return users.filter(
            is_active=True,
            is_suspended=True,
        )

    if preset_key == SANCTUARY_PARTICIPANTS:
        queryset = users.filter(
            is_active=True,
            member_profile__isnull=False,
            member_profile__is_townlit_verified=True,
            sanctuary_participant__is_participant=True,
            sanctuary_participant__is_eligible=True,
        ).distinct()

        # is_verified_identity is a Python property.
        return [
            user
            for user in queryset
            if bool(getattr(user, "is_verified_identity", False))
        ]

    if preset_key == PRIVACY_ENABLED:
        return users.filter(
            is_active=True,
            member_profile__isnull=False,
            member_profile__is_privacy=True,
        )

    if preset_key == UNVERIFIED_IDENTITY:
        queryset = users.filter(is_active=True)

        return [
            user
            for user in queryset
            if not bool(getattr(user, "is_verified_identity", False))
        ]

    if preset_key == TOWNLIT_NOT_VERIFIED:
        queryset = users.filter(
            is_active=True,
            member_profile__isnull=False,
            member_profile__is_townlit_verified=False,
        )

        return [
            user
            for user in queryset
            if bool(getattr(user, "is_verified_identity", False))
        ]

    if preset_key == TOWNLIT_VERIFIED:
        return users.filter(
            is_active=True,
            member_profile__isnull=False,
            member_profile__is_townlit_verified=True,
        )

    if preset_key == RE_ENGAGEMENT:
        user_ids = UnsubscribedUser.objects.exclude(
            user_id__isnull=True
        ).values_list(
            "user_id",
            flat=True,
        )

        return users.filter(
            id__in=user_ids,
            is_active=True,
        )

    if preset_key == ACCESS_REQUESTS:
        return AccessRequest.objects.filter(
            is_active=True,
        ).exclude(
            email__isnull=True,
        ).exclude(
            email__exact="",
        )

    if preset_key == UNUSED_INVITE_ACCESS:
        from apps.accounts.models.invite import InviteCode

        unused_emails = InviteCode.objects.filter(
            is_used=False,
        ).values_list(
            "email",
            flat=True,
        )

        return AccessRequest.objects.filter(
            is_active=True,
            email__in=unused_emails,
        ).exclude(
            email__isnull=True,
        ).exclude(
            email__exact="",
        )

    return users.filter(is_active=True)


def get_users_for_campaign(campaign):
    """
    Backward-compatible target resolver for old admin/forms.
    """

    if campaign.recipients.exists():
        return campaign.recipients.filter(is_active=True)

    objects = resolve_preset_objects(
        campaign.target_group
    )

    if (
        campaign.ignore_unsubscribe
        or campaign.target_group == RE_ENGAGEMENT
    ):
        return objects

    unsubscribed_user_ids = set(
        UnsubscribedUser.objects.exclude(
            user_id__isnull=True
        ).values_list(
            "user_id",
            flat=True,
        )
    )

    unsubscribed_emails = {
        email.strip().lower()
        for email in UnsubscribedUser.objects.values_list(
            "email",
            flat=True,
        )
        if email
    }

    if isinstance(objects, QuerySet):
        if objects.model is CustomUser:
            return objects.exclude(
                id__in=unsubscribed_user_ids
            )

        if objects.model is AccessRequest:
            return objects.exclude(
                email__in=unsubscribed_emails
            )

    result = []

    for obj in objects:
        email = (getattr(obj, "email", "") or "").strip().lower()

        if isinstance(obj, CustomUser):
            if obj.id in unsubscribed_user_ids:
                continue
        elif email in unsubscribed_emails:
            continue

        result.append(obj)

    return result