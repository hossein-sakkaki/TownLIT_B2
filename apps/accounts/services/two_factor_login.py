# apps/accounts/services/two_factor_login.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-05.
# Last Update by Hossein Sakkaki on 2026-11-05.
#

"""Atomic, single-use email OTP consumption for the login 2FA flow."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.accounts.models.user import CustomUser


def consume_login_two_factor_code(
    *,
    user_id: int,
    otp_code: str,
) -> tuple[str, CustomUser]:
    """Consume a valid login OTP once, preserving existing account gates.

    The lock serializes verification and clearing for concurrent requests.
    No code, hash, or credential is included in log output.
    """
    with transaction.atomic():
        user = (
            CustomUser.objects
            .select_for_update()
            .select_related("label")
            .get(pk=user_id)
        )

        if user.is_suspended:
            return "suspended", user

        # Keep the existing account-deletion recovery behavior separate.
        if not user.is_active and not user.is_deleted:
            return "inactive", user

        if not user.two_factor_enabled:
            return "disabled", user

        token_status = user.validate_two_factor_token(otp_code)
        if token_status != "valid":
            return token_status, user

        user.two_factor_token = None
        user.two_factor_token_expiry = None
        user.last_login = timezone.now()
        user.save(update_fields=[
            "two_factor_token",
            "two_factor_token_expiry",
            "last_login",
        ])

        return "valid", user
