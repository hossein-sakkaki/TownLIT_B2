# apps/ai_gateway/service_tokens.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Isolated synthetic ES256 profile; never an HTTP authenticator or identity.

Requires the separate B1.1A environment. No settings, database, key discovery,
network, issuance, certificate validation or authorization lives here.
"""

import base64
import json
import re
import time
from dataclasses import dataclass
from importlib.metadata import version
from types import MappingProxyType
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric import ec
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import ECKey

_REQUIRED = frozenset(
    {
        "iss",
        "aud",
        "sub",
        "exp",
        "iat",
        "nbf",
        "jti",
        "agent_id",
        "organization_id",
        "scopes",
        "environment",
    }
)
_LABEL = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}\Z", re.ASCII)


class InvalidServiceToken(ValueError):
    """Fixed error; do not expose tokens, claims or library exception messages."""

    def __init__(self):
        super().__init__("invalid_service_token")


@dataclass(frozen=True)
class ServiceTokenClaims:
    """Signature-checked assertions, NOT trusted principal or domain permissions.

    Deliberately incompatible with security.VerifiedIdentity. Future principal,
    certificate, policy and current-grant checks must precede usable identity.
    """

    principal_reference: str
    agent_id: str
    organization_reference: UUID
    scopes: frozenset[str]
    environment: str
    token_id: str
    issued_at: int
    not_before: int
    expires_at: int


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidServiceToken()
        result[key] = value
    return result


def _invalid_constant(value):
    raise InvalidServiceToken()


def _segment(value):
    # Structural rejection only; JOSE performs all signature verification.
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value, re.ASCII):
        raise InvalidServiceToken()
    decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii") != value:
        raise InvalidServiceToken()
    return decoded


def _json_object(value):
    result = json.loads(
        value.decode("utf-8"),
        object_pairs_hook=_object,
        parse_constant=_invalid_constant,
    )
    if type(result) is not dict:
        raise InvalidServiceToken()
    return result


def _label(value):
    return type(value) is str and _LABEL.fullmatch(value) is not None


class SyntheticServiceTokenVerifier:
    """Explicit local public-key registry for one synthetic environment.

    Production/staging configuration is intentionally unsupported. Keys are
    supplied by trusted test code, never selected from token URLs or JWKs.
    """

    def __init__(self, *, environment, public_keys, clock_skew=30):
        if version("joserfc") != "1.8.0" or version("cryptography") != "50.0.2":
            raise ValueError("B1.1A requires its reviewed isolated dependency profile")
        if (
            type(environment) is not str
            or re.fullmatch(r"synthetic-[a-z0-9-]{1,20}", environment, re.ASCII) is None
            or type(clock_skew) is not int
            or not 0 <= clock_skew <= 30
            or not public_keys
        ):
            raise ValueError("Invalid synthetic verifier configuration")
        keys = {}
        for kid, key in public_keys.items():
            if (
                not _label(kid)
                or not isinstance(key, ec.EllipticCurvePublicKey)
                or not isinstance(key.curve, ec.SECP256R1)
            ):
                raise ValueError(
                    "Only locally registered P-256 public keys are accepted"
                )
            keys[kid] = ECKey.import_key(key)
        self._keys = MappingProxyType(keys)
        self._environment = environment
        self._issuer = f"https://issuer.{environment}.example.invalid/office"
        self._audience = f"townlit-ai-gateway:{environment}"
        self._skew = clock_skew

    def verify(self, token, *, now=None):
        """Return assertions only. A reusable jti is not request replay protection."""
        try:
            return self._verify(token, int(time.time()) if now is None else now)
        except (
            InvalidServiceToken,
            JoseError,
            ValueError,
            TypeError,
            KeyError,
            UnicodeError,
            RecursionError,
            OverflowError,
        ):
            raise InvalidServiceToken() from None

    def _verify(self, token, now):
        if type(token) is not str or len(token) > 8192 or type(now) is not int:
            raise InvalidServiceToken()
        parts = token.split(".")
        if len(parts) != 3:
            raise InvalidServiceToken()
        header_raw, payload_raw, signature = map(_segment, parts)
        if len(header_raw) > 512 or len(payload_raw) > 4096 or len(signature) != 64:
            raise InvalidServiceToken()
        header = _json_object(header_raw)
        if (
            set(header) != {"alg", "typ", "kid"}
            or header["alg"] != "ES256"
            or header["typ"] != "at+jwt"
            or not _label(header["kid"])
        ):
            raise InvalidServiceToken()
        key = self._keys[header["kid"]]
        # Preflight disallows duplicate/ambiguous JSON before the JOSE parser.
        claims = _json_object(payload_raw)
        verified = jwt.decode(token, key, algorithms=["ES256"])
        if verified.header != header or verified.claims != claims:
            raise InvalidServiceToken()
        if set(claims) != _REQUIRED:
            raise InvalidServiceToken()
        if (
            type(claims["iss"]) is not str
            or claims["iss"] != self._issuer
            or type(claims["aud"]) is not str
            or claims["aud"] != self._audience
            or type(claims["environment"]) is not str
            or claims["environment"] != self._environment
            or not _label(claims["sub"])
            or not _label(claims["jti"])
            or claims["agent_id"] not in ("phoebe", "silas", "micah")
            or type(claims["agent_id"]) is not str
        ):
            raise InvalidServiceToken()
        if any(
            type(claims[name]) is not int or not 0 <= claims[name] <= 2**53 - 1
            for name in ("exp", "iat", "nbf")
        ):
            raise InvalidServiceToken()
        if not claims["iat"] <= claims["nbf"] < claims["exp"] <= claims["iat"] + 300:
            raise InvalidServiceToken()
        jwt.JWTClaimsRegistry(now=now, leeway=self._skew).validate(claims)
        organization = claims["organization_id"]
        if type(organization) is not str or str(UUID(organization)) != organization:
            raise InvalidServiceToken()
        scopes = claims["scopes"]
        if (
            type(scopes) is not list
            or not 1 <= len(scopes) <= 16
            or not all(_label(scope) for scope in scopes)
            or len(set(scopes)) != len(scopes)
        ):
            raise InvalidServiceToken()
        return ServiceTokenClaims(
            claims["sub"],
            claims["agent_id"],
            UUID(organization),
            frozenset(scopes),
            self._environment,
            claims["jti"],
            claims["iat"],
            claims["nbf"],
            claims["exp"],
        )
