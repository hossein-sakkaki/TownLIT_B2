#
#  apps/accounts/account_deletion/service.py
#  TownLIT
#
#  Created by Hossein Sakkaki on 2026-08-04.
#  Last Update by Hossein Sakkaki on 2026-08-04.
#

import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from apps.accounts.account_deletion.context import (
    AccountDeletionContext,
)
from apps.accounts.account_deletion.exceptions import (
    AccountDeletionConfigurationError,
    AccountDeletionDeadlinePassed,
    AccountDeletionNotPending,
)
from apps.accounts.account_deletion.registry import (
    account_deletion_registry,
)


CustomUser = get_user_model()
logger = logging.getLogger(__name__)


def account_deletion_grace_days() -> int:
    raw = getattr(
        settings,
        "ACCOUNT_DELETION_GRACE_DAYS",
        30,
    )

    try:
        return max(
            1,
            int(raw),
        )
    except (TypeError, ValueError):
        return 30


def scheduled_deletion_date():
    return (
        timezone.now()
        + timedelta(
            days=account_deletion_grace_days(),
        )
    )


def _blacklist_user_refresh_tokens(
    user,
) -> None:
    for token in OutstandingToken.objects.filter(
        user=user,
    ).iterator():
        BlacklistedToken.objects.get_or_create(
            token=token,
        )


def _validate_registered_handlers() -> None:
    required = {
        str(key).strip().lower()
        for key in getattr(
            settings,
            "ACCOUNT_DELETION_REQUIRED_HANDLERS",
            [],
        )
        if str(key).strip()
    }

    registered = (
        account_deletion_registry
        .registered_keys()
    )

    missing = required - registered

    if missing:
        raise AccountDeletionConfigurationError(
            "Missing account deletion handlers: "
            + ", ".join(
                sorted(missing)
            ),
            code="missing_account_deletion_handlers",
        )


def schedule_account_deletion(
    *,
    user,
):
    """
    Schedule permanent deletion and hide profiles immediately.
    """
    with transaction.atomic():
        locked_user = (
            CustomUser.objects
            .select_for_update()
            .get(pk=user.pk)
        )

        if locked_user.deletion_completed_at:
            raise AccountDeletionDeadlinePassed(
                "This account has already been permanently deleted.",
                code="account_deletion_completed",
            )

        now = timezone.now()
        scheduled_for = (
            now
            + timedelta(
                days=account_deletion_grace_days(),
            )
        )

        locked_user.is_deleted = True
        locked_user.deletion_requested_at = now
        locked_user.deletion_scheduled_for = scheduled_for
        locked_user.deletion_canceled_at = None
        locked_user.reactivated_at = None
        locked_user.user_active_code = None
        locked_user.user_active_code_expiry = None

        locked_user.save(
            update_fields=[
                "is_deleted",
                "deletion_requested_at",
                "deletion_scheduled_for",
                "deletion_canceled_at",
                "reactivated_at",
                "user_active_code",
                "user_active_code_expiry",
            ],
        )

        try:
            member = locked_user.member_profile
        except Exception:
            member = None

        if member is not None:
            member.is_active = False
            member.save(
                update_fields=[
                    "is_active",
                ],
            )

        try:
            guest = locked_user.guest_profile
        except Exception:
            guest = None

        if guest is not None:
            guest.is_active = False
            guest.save(
                update_fields=[
                    "is_active",
                ],
            )

        _blacklist_user_refresh_tokens(
            locked_user
        )

    return locked_user


def cancel_account_deletion(
    *,
    user,
):
    """
    Cancel deletion before the scheduled deadline.
    """
    with transaction.atomic():
        locked_user = (
            CustomUser.objects
            .select_for_update()
            .get(pk=user.pk)
        )

        if not locked_user.is_deleted:
            raise AccountDeletionNotPending(
                "This account is not scheduled for deletion.",
                code="account_deletion_not_pending",
            )

        if locked_user.deletion_completed_at:
            raise AccountDeletionDeadlinePassed(
                "This account has already been permanently deleted.",
                code="account_deletion_completed",
            )

        if (
            not locked_user.deletion_scheduled_for
            or timezone.now()
            >= locked_user.deletion_scheduled_for
        ):
            raise AccountDeletionDeadlinePassed(
                "The account recovery period has ended.",
                code="account_deletion_deadline_passed",
            )

        now = timezone.now()

        locked_user.is_deleted = False
        locked_user.deletion_requested_at = None
        locked_user.deletion_scheduled_for = None
        locked_user.deletion_canceled_at = now
        locked_user.reactivated_at = now
        locked_user.user_active_code = None
        locked_user.user_active_code_expiry = None

        locked_user.save(
            update_fields=[
                "is_deleted",
                "deletion_requested_at",
                "deletion_scheduled_for",
                "deletion_canceled_at",
                "reactivated_at",
                "user_active_code",
                "user_active_code_expiry",
            ],
        )

        try:
            member = locked_user.member_profile
        except Exception:
            member = None

        if member is not None:
            member.is_active = True
            member.save(
                update_fields=[
                    "is_active",
                ],
            )

        try:
            guest = locked_user.guest_profile
        except Exception:
            guest = None

        if guest is not None:
            guest.is_active = True
            guest.save(
                update_fields=[
                    "is_active",
                ],
            )

    return locked_user


def permanently_delete_account(
    *,
    user_id: int,
) -> bool:
    """
    Run every registered handler and anonymize the account.
    """
    _validate_registered_handlers()

    with transaction.atomic():
        user = (
            CustomUser.objects
            .select_for_update()
            .filter(
                pk=user_id,
                is_deleted=True,
                deletion_completed_at__isnull=True,
                deletion_scheduled_for__isnull=False,
                deletion_scheduled_for__lte=timezone.now(),
            )
            .first()
        )

        if user is None:
            return False

        original_email = user.email
        original_username = user.username

        random_suffix = secrets.token_hex(
            8
        )

        anonymized_email = (
            f"deleted+{user.id}+{random_suffix}"
            "@deleted.townlit.invalid"
        )

        anonymized_username = (
            f"deleted_{user.id}_{random_suffix[:6]}"
        )[:20]

        context = AccountDeletionContext(
            user=user,
            original_email=original_email,
            original_username=original_username,
            anonymized_email=anonymized_email,
            anonymized_username=anonymized_username,
        )

        for registered in (
            account_deletion_registry
            .handlers()
        ):
            logger.info(
                "[AccountDeletion] Running handler "
                "user_id=%s handler=%s",
                user.id,
                registered.key,
            )

            registered.handler(
                context
            )

        if user.image_name:
            try:
                user.image_name.delete(
                    save=False,
                )
            except Exception:
                logger.exception(
                    "Unable to delete account avatar "
                    "user_id=%s",
                    user.id,
                )

        user.set_unusable_password()

        user.email = anonymized_email
        user.username = anonymized_username
        user.mobile_number = None
        user.name = ""
        user.family = ""
        user.birthday = None
        user.gender = None
        user.label = None
        user.country = None
        user.city = None
        user.primary_language = None
        user.secondary_language = None
        user.language_onboarding_completed = False
        user.image_name = None
        user.show_email = False
        user.show_phone_number = False
        user.show_country = False
        user.show_city = False
        user.is_active = False
        user.is_member = False
        user.is_account_paused = False
        user.two_factor_enabled = False
        user.two_factor_token = None
        user.two_factor_token_expiry = None
        user.pin_security_enabled = False
        user.access_pin = None
        user.delete_pin = None
        user.registration_id = None
        user.reset_token = None
        user.reset_token_expiration = None
        user.user_active_code = None
        user.user_active_code_expiry = None
        user.deletion_completed_at = timezone.now()

        user.save(
            update_fields=[
                "password",
                "email",
                "username",
                "mobile_number",
                "name",
                "family",
                "birthday",
                "gender",
                "label",
                "country",
                "city",
                "primary_language",
                "secondary_language",
                "language_onboarding_completed",
                "image_name",
                "show_email",
                "show_phone_number",
                "show_country",
                "show_city",
                "is_active",
                "is_member",
                "is_account_paused",
                "two_factor_enabled",
                "two_factor_token",
                "two_factor_token_expiry",
                "pin_security_enabled",
                "access_pin",
                "delete_pin",
                "registration_id",
                "reset_token",
                "reset_token_expiration",
                "user_active_code",
                "user_active_code_expiry",
                "deletion_completed_at",
            ],
        )

        _blacklist_user_refresh_tokens(
            user
        )

        logger.info(
            "[AccountDeletion] Completed user_id=%s",
            user.id,
        )

        return True