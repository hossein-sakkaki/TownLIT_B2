# apps/accounts/services/identity_guard.py

from datetime import timedelta
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models.identity import IdentityVerification


MAX_SESSIONS_PER_DAY = 1
RETRY_COOLDOWN_HOURS = 6


def enforce_identity_rate_limits(user):
    """
    Prevent identity verification abuse.
    """

    now = timezone.now()

    iv = IdentityVerification.objects.filter(user=user).first()

    if not iv:
        return

    # Block if session already active
    if iv.status in ["pending", "processing"]:
        raise ValidationError({
            "detail": "An identity verification session is already active."
        })

    # Limit daily attempts
    attempts_today = IdentityVerification.objects.filter(
        user=user,
        created_at__gte=now - timedelta(hours=24),
    ).count()

    if attempts_today >= MAX_SESSIONS_PER_DAY:
        raise ValidationError({
            "detail": "Verification attempts limit reached. Please try again tomorrow."
        })

    # Cooldown after rejection
    if iv.rejected_at:
        cooldown_end = iv.rejected_at + timedelta(hours=RETRY_COOLDOWN_HOURS)

        if now < cooldown_end:
            raise ValidationError({
                "detail": "Please wait before retrying identity verification."
            })