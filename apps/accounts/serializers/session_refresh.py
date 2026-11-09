# apps/accounts/serializers/session_refresh.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-05.
# Last Update by Hossein Sakkaki on 2026-11-09.
#

"""Validate the signed refresh identity and current session before rotation."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db import InterfaceError, OperationalError
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    PermissionDenied,
)
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken, Token

from apps.accounts.services.session_generation_policy import (
    session_generation_enforced,
    session_generation_from_payload,
    session_generation_matches,
)

# CustomUser.id is a BigAutoField: positive, signed 64-bit on MySQL/SQLite.
_MAX_REFRESH_USER_ID = 2**63 - 1


class RefreshServiceUnavailable(APIException):
    status_code = 503
    default_code = "refresh_unavailable"
    default_detail = {
        "detail": "Session validation temporarily unavailable. Please try again later.",
        "code": default_code,
    }


class RefreshServiceFailure(APIException):
    status_code = 500
    default_code = "refresh_failed"
    default_detail = {
        "detail": "Session validation failed.",
        "code": default_code,
    }


class _RefreshTokenPreflight(RefreshToken):
    def verify(self):
        # Token.__init__ has already verified the signature. Check expiry,
        # required claims and refresh type before any DB operation. Upstream's
        # BlacklistMixin.verify does these checks AFTER its blacklist query.
        # validate() explicitly checks the blacklist before any authorization.
        Token.verify(self)


def _verified_refresh_user_id(claim) -> int:
    """Normalize only a previously signature-verified refresh claim.

    SimpleJWT 5.3.1 emits integers; 5.5.1 emits decimal strings. This is a
    local refresh adapter, never a general identity/session validator. Bound
    strings before int() and accept no aliases, Unicode digits or overflow.
    """
    if (
        type(claim) is str
        and 1 <= len(claim) <= 19
        and claim.isascii()
        and claim.isdecimal()
        and claim[0] != "0"
    ):
        claim = int(claim)
    if type(claim) is not int or not 1 <= claim <= _MAX_REFRESH_USER_ID:
        raise InvalidToken("Token contained no valid user identification.")
    return claim


class SessionGenerationTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        try:
            # Reject deterministically invalid input even during a DB outage.
            # Normalize only the signature/expiry/type-verified refresh claim;
            # never rewrite the signed wire payload.
            refresh = _RefreshTokenPreflight(attrs["refresh"])
            user_id = _verified_refresh_user_id(
                refresh.payload.get(api_settings.USER_ID_CLAIM)
            )
            generation = session_generation_from_payload(refresh.payload)
            enforce = session_generation_enforced()
            if (
                enforce
                and generation is not None
                and (type(generation) is not int or generation < 0)
            ):
                raise InvalidToken("Session has expired. Please sign in again.")
            # No credential issuance or account/session authorization precedes this
            # authoritative check. The parent rechecks it before rotation too.
            refresh.check_blacklist()
            User = get_user_model()
            user = User.objects.get(**{api_settings.USER_ID_FIELD: user_id})
            # 5.3.1 lacks the parent's current-user check. Require an available,
            # active account in both profiles, including with enforcement off.
            # AUTH-01 remains an OPEN release-policy decision; this integration
            # preserves PR #7 behavior without approving it or changing flags.
            # Soft deletion/reactivation, suspension/logout and restricted-owner
            # access remain governed by their existing action/account gates.
            # Refresh identity alone does not authorize a protected API/WS action.
            if not user.is_active or not api_settings.USER_AUTHENTICATION_RULE(user):
                raise InvalidToken("Account access is unavailable.")
            if enforce and not session_generation_matches(user.pk, generation):
                raise InvalidToken("Session has expired. Please sign in again.")
            # Keep upstream user checks, rotation, outstanding and blacklist
            # semantics intact. The normalized ID above is local only.
            return super().validate(attrs)
        except (InvalidToken, TokenError):
            raise
        except ObjectDoesNotExist as exc:
            # Includes deletion between our check and the parent's user lookup.
            raise InvalidToken("Account access is unavailable.") from exc
        except AuthenticationFailed as exc:
            raise InvalidToken("Account access is unavailable.") from exc
        except PermissionDenied as exc:
            raise PermissionDenied("Account access is unavailable.") from exc
        except (OperationalError, InterfaceError, ConnectionError, TimeoutError) as exc:
            # Dependency unavailability is not proof of invalid credentials.
            # Never retry/undo parent rotation here: it may already have consumed
            # the submitted token. Deny without credentials and retain DB state.
            raise RefreshServiceUnavailable() from exc
        except Exception as exc:
            # Programming/schema/integrity failures are not retryable auth errors.
            # Expose no exception text, payload, database detail or credentials.
            raise RefreshServiceFailure() from exc
