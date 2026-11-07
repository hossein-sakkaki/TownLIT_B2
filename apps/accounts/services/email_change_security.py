# apps/accounts/services/email_change_security.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Email-change codes are one-way verifiers and the pending address is encrypted."""

import hmac

from django.utils.crypto import salted_hmac
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.core.crypto.field_protection import FieldProtector

EMAIL_CHANGE_MAX_ATTEMPTS = 5
_EMAIL_LABEL = "accounts.CustomUser.email_change.pending_email"


def _code_verifier(*, user_id, purpose, code):
    # Server-keyed verifier prevents offline guessing from a database-only breach.
    return salted_hmac(
        f"townlit.email_change.v2.{purpose}", f"{user_id}:{code}"
    ).hexdigest()


def new_email_change_state(*, user_id, old_code, new_code, new_email, expires_at):
    if not user_id or expires_at is None or timezone.is_naive(expires_at):
        raise ValueError("Invalid email-change request configuration.")
    return {
        "v": 2,
        "old_code_verifier": _code_verifier(user_id=user_id, purpose="old", code=old_code),
        "new_code_verifier": _code_verifier(user_id=user_id, purpose="new", code=new_code),
        "pending_email_encrypted": FieldProtector.from_environment().protect(
            new_email, field=_EMAIL_LABEL, row_id=user_id
        ),
        "expires_at": expires_at.isoformat(),
        "created_at": timezone.now().isoformat(),
        "failed_attempts": 0,
    }


def email_change_expired(state, *, legacy_expires_at=None, now=None):
    now = now or timezone.now()
    if state.get("v") == 2:
        expiry = parse_datetime(state.get("expires_at", ""))
        return expiry is None or timezone.is_naive(expiry) or now >= expiry
    return legacy_expires_at is None or now >= legacy_expires_at


def verify_email_change_codes(state, old_code, new_code, *, user_id=None):
    if not isinstance(state, dict) or not old_code or not new_code:
        return False
    if state.get("v") == 2:
        old_verifier = state.get("old_code_verifier")
        new_verifier = state.get("new_code_verifier")
        if not isinstance(old_verifier, str) or not isinstance(new_verifier, str):
            return False
        if not user_id:
            return False
        # Evaluate both checks to avoid leaking which address's code is wrong.
        old_valid = hmac.compare_digest(
            old_verifier, _code_verifier(user_id=user_id, purpose="old", code=old_code)
        )
        new_valid = hmac.compare_digest(
            new_verifier, _code_verifier(user_id=user_id, purpose="new", code=new_code)
        )
        return old_valid and new_valid
    # Read-only temporary compatibility with unexpired legacy requests.
    old_raw = state.get("old_email_code")
    new_raw = state.get("new_email_code")
    if old_raw is None or new_raw is None:
        return False
    old_valid = hmac.compare_digest(str(old_raw), str(old_code))
    new_valid = hmac.compare_digest(str(new_raw), str(new_code))
    return old_valid and new_valid


def pending_new_email(state, user_id):
    if state.get("v") == 2:
        return FieldProtector.from_environment().reveal(
            state.get("pending_email_encrypted"), field=_EMAIL_LABEL, row_id=user_id
        )
    return state.get("new_email")
