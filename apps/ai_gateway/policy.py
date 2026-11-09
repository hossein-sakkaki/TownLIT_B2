# apps/ai_gateway/policy.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Current metadata policy, not domain authorization or a dispatch service."""

from uuid import UUID

from django.conf import settings
from django.db import DatabaseError
from django.utils import timezone

from .errors import GatewayDenied
from .models import OfficeOrganizationBinding, OperationGrant, ServicePrincipal
from .registry import OPERATIONS
from .security import VerifiedIdentity


def require_metadata_permission(identity, operation, version, scope_ref, *, lock=False):
    if getattr(settings, "AI_GATEWAY_ENABLED", False) is not True:
        raise GatewayDenied("gateway_disabled")
    environment = getattr(settings, "AI_GATEWAY_ENVIRONMENT", "")
    if (
        not isinstance(environment, str)
        or not environment
        or not isinstance(identity, VerifiedIdentity)
        or not isinstance(operation, str)
        or type(version) is not int
        or not isinstance(scope_ref, UUID)
        or not all(
            isinstance(value, UUID)
            for value in (
                identity.principal_id,
                identity.office_organization_id,
                identity.backend_organization_id,
            )
        )
        or not isinstance(identity.agent_id, str)
        or not isinstance(identity.scopes, frozenset)
    ):
        raise GatewayDenied()
    spec = OPERATIONS.get((operation, version))
    if (
        spec is None
        or identity.agent_id == "chloe"
        or identity.agent_id not in spec.allowed_agents
        or spec.scope not in identity.scopes
        or scope_ref != identity.principal_id
    ):
        raise GatewayDenied()
    try:
        principals = ServicePrincipal.objects
        organizations = OfficeOrganizationBinding.objects
        grants = OperationGrant.objects
        if lock:
            principals = principals.select_for_update()
            organizations = organizations.select_for_update()
            grants = grants.select_for_update()
        principal = principals.get(
            pk=identity.principal_id,
            agent_id=identity.agent_id,
            environment=environment,
            active=True,
            revoked_at__isnull=True,
        )
        organization = organizations.get(
            environment=environment,
            office_organization_id=identity.office_organization_id,
            backend_organization_id=identity.backend_organization_id,
            active=True,
            revoked_at__isnull=True,
        )
        grant = grants.get(
            principal=principal,
            organization=organization,
            operation=spec.name,
            version=spec.version,
            scope_ref=scope_ref,
            active=True,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        # MySQL's configured collation may compare security labels without case.
        if (
            principal.agent_id != identity.agent_id
            or principal.environment != environment
            or organization.environment != environment
            or grant.operation != spec.name
        ):
            raise GatewayDenied()
        return principal, organization, grant
    except (
        ServicePrincipal.DoesNotExist,
        OfficeOrganizationBinding.DoesNotExist,
        OperationGrant.DoesNotExist,
    ):
        raise GatewayDenied() from None
    except DatabaseError:
        raise GatewayDenied("security_unavailable") from None
