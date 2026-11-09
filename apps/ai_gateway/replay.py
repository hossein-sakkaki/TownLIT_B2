# apps/ai_gateway/replay.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Internal nonce reservation primitive; never a substitute for verified proof."""

import hashlib
import re
from datetime import datetime, timedelta

from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

from .errors import GatewayDenied
from .models import RequestNonce
from .policy import require_metadata_permission
from .security import VerifiedIdentity


def reserve_nonce(identity, *, nonce, timestamp, purpose="request"):
    if not isinstance(identity, VerifiedIdentity):
        raise GatewayDenied()
    now = timezone.now()
    if (
        not isinstance(nonce, str)
        or not re.fullmatch(r"[0-9a-f]{32,128}", nonce)
        or type(purpose) is not str
        or purpose not in {"request", "assertion"}
        or type(timestamp) is not datetime
        or not timezone.is_aware(timestamp)
        or abs((now - timestamp).total_seconds()) > 60
    ):
        raise GatewayDenied("invalid_request")
    try:
        with transaction.atomic():
            principal, _, _ = require_metadata_permission(
                identity,
                "gateway.capabilities",
                1,
                identity.principal_id,
                lock=True,
            )
            RequestNonce.objects.create(
                principal=principal,
                purpose=purpose,
                digest=hashlib.sha256(nonce.encode("ascii")).hexdigest(),
                expires_at=now + timedelta(minutes=10),
            )
    except IntegrityError:
        raise GatewayDenied("nonce_reused") from None
    except DatabaseError:
        raise GatewayDenied("security_unavailable") from None
