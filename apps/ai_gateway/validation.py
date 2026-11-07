# apps/ai_gateway/validation.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""B1 metadata envelope v1 only. No domain payload schema is accepted."""

import hashlib
import json
from uuid import UUID

from .errors import GatewayDenied


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate key")
        obj[key] = value
    return obj


def metadata_envelope(body):
    """Return an exact validated envelope and a versioned canonical digest."""
    try:
        if not isinstance(body, bytes) or len(body) > 1024:
            raise ValueError()
        value = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object)
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "purpose",
            "correlation_id",
        }:
            raise ValueError()
        if type(value["schema_version"]) is not int or value["schema_version"] != 1:
            raise ValueError()
        if value["purpose"] != "gateway_metadata":
            raise ValueError()
        if not isinstance(value["correlation_id"], str):
            raise ValueError()
        correlation = UUID(value["correlation_id"])
        if str(correlation) != value["correlation_id"]:
            raise ValueError()
        canonical = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
        return value, hashlib.sha256(
            b"townlit-gateway-metadata-v1\x00" + canonical
        ).hexdigest()
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise GatewayDenied("invalid_request") from None
