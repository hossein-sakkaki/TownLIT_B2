# apps/ai_gateway/security.py
# TownLIT-Backend
# Created by Codex on 2026-11-06.
# Last Update by Codex on 2026-11-06.

"""Security seams only. No credentials, tokens or certificates are verified in B1."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from .errors import GatewayDenied


@dataclass(frozen=True)
class VerifiedIdentity:
    """Internal policy input; never construct from HTTP headers or decoded claims."""

    principal_id: UUID
    agent_id: str
    office_organization_id: UUID
    backend_organization_id: UUID
    scopes: frozenset[str]


class CredentialVerifier(Protocol):
    def verify(self, request) -> VerifiedIdentity: ...


class AccessTokenVerifier(Protocol):
    def verify(self, token: str, *, audience: str) -> VerifiedIdentity: ...


class RequestProofVerifier(Protocol):
    def verify(self, request, identity: VerifiedIdentity) -> None: ...


class CertificateVerifier(Protocol):
    def verify(self, request, identity: VerifiedIdentity) -> None: ...


class UnavailableSecurity:
    """No injectable setting/plugin can turn this boundary into a bypass."""

    def verify(self, *args, **kwargs):
        raise GatewayDenied("security_unavailable")

    def issue(self, *args, **kwargs):
        raise GatewayDenied("security_unavailable")
