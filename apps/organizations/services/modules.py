# apps/organizations/services/modules.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.organizations.constants import (
    OrganizationAuditAction,
    OrganizationAuditSource,
    OrganizationModuleAccessMode,
    OrganizationModuleAccessReason,
    OrganizationModuleActivationStatus,
    OrganizationModuleVisibility,
    OrganizationPermissionKey,
    OrganizationRoleScope,
    OrganizationStatus,
)
from apps.organizations.feature_flags import (
    ensure_organization_modules_enabled,
    organization_modules_enabled,
)
from apps.organizations.models import (
    OrganizationAuditLog,
    OrganizationModuleActivation,
)
from apps.organizations.selectors.verification import (
    is_organization_verified,
)
from apps.organizations.services.access import (
    user_has_organization_permission,
)
from apps.organizations.modules.runtime import (
    initialize_organization_module_runtime,
)
from apps.organizations.services.module_catalog import (
    get_organization_module_definition,
)
from apps.subscriptions.constants import SubscriptionAccountStatus
from apps.subscriptions.services.entitlements import has_entitlement


@dataclass(frozen=True)
class OrganizationModuleAccess:
    module_key: str
    access_mode: str
    reason: str
    definition: object | None
    activation: object | None
    is_verified: bool
    has_entitlement: bool
    can_manage: bool
    can_write: bool

    @property
    def is_available(self) -> bool:
        return self.access_mode in {
            OrganizationModuleAccessMode.FULL,
            OrganizationModuleAccessMode.READ_ONLY,
        }


def _actor_can_manage_module(*, actor, organization, module_key) -> bool:
    return user_has_organization_permission(
        user=actor,
        organization=organization,
        permission_key=OrganizationPermissionKey.MANAGE_MODULES,
        scope_type=OrganizationRoleScope.MODULE,
        scope_key=module_key,
    )


def _require_actor_can_manage_module(*, actor, organization, module_key):
    if not _actor_can_manage_module(
        actor=actor,
        organization=organization,
        module_key=module_key,
    ):
        raise PermissionDenied(
            "You do not have permission to manage this organization module."
        )


def get_organization_module_access(
    *,
    organization,
    module_key,
    actor=None,
    now=None,
):
    now = now or timezone.now()
    normalized_key = str(module_key or "").strip().lower()

    can_manage = False
    if actor:
        can_manage = _actor_can_manage_module(
            actor=actor,
            organization=organization,
            module_key=normalized_key,
        )

    if not organization_modules_enabled():
        return OrganizationModuleAccess(
            module_key=normalized_key,
            access_mode=OrganizationModuleAccessMode.UNAVAILABLE,
            reason=OrganizationModuleAccessReason.FEATURE_DISABLED,
            definition=None,
            activation=None,
            is_verified=False,
            has_entitlement=False,
            can_manage=can_manage,
            can_write=False,
        )

    definition = None
    try:
        definition = get_organization_module_definition(
            module_key=normalized_key,
            active_only=False,
        )
    except ValidationError:
        pass

    if not definition:
        return OrganizationModuleAccess(
            module_key=normalized_key,
            access_mode=OrganizationModuleAccessMode.UNAVAILABLE,
            reason=OrganizationModuleAccessReason.MODULE_NOT_FOUND,
            definition=None,
            activation=None,
            is_verified=False,
            has_entitlement=False,
            can_manage=can_manage,
            can_write=False,
        )

    if not definition.is_active:
        return OrganizationModuleAccess(
            module_key=normalized_key,
            access_mode=OrganizationModuleAccessMode.UNAVAILABLE,
            reason=OrganizationModuleAccessReason.MODULE_INACTIVE,
            definition=definition,
            activation=None,
            is_verified=False,
            has_entitlement=False,
            can_manage=can_manage,
            can_write=False,
        )

    activation = (
        OrganizationModuleActivation.objects
        .select_related("module", "organization__subscription_account")
        .filter(
            organization=organization,
            module=definition,
        )
        .first()
    )

    verified = (
        is_organization_verified(
            organization=organization,
            now=now,
        )
        if definition.requires_verification
        else True
    )

    entitled = (
        has_entitlement(
            account=organization.subscription_account,
            key=definition.entitlement_key,
            now=now,
        )
        if definition.requires_entitlement
        else True
    )

    if organization.status != OrganizationStatus.ACTIVE:
        return OrganizationModuleAccess(
            module_key=normalized_key,
            access_mode=OrganizationModuleAccessMode.LOCKED,
            reason=OrganizationModuleAccessReason.ORGANIZATION_UNAVAILABLE,
            definition=definition,
            activation=activation,
            is_verified=verified,
            has_entitlement=entitled,
            can_manage=can_manage,
            can_write=False,
        )

    if not activation:
        return OrganizationModuleAccess(
            module_key=normalized_key,
            access_mode=OrganizationModuleAccessMode.UNAVAILABLE,
            reason=OrganizationModuleAccessReason.NOT_ACTIVATED,
            definition=definition,
            activation=None,
            is_verified=verified,
            has_entitlement=entitled,
            can_manage=can_manage,
            can_write=False,
        )

    if activation.status == OrganizationModuleActivationStatus.DISABLED:
        return OrganizationModuleAccess(
            module_key=normalized_key,
            access_mode=OrganizationModuleAccessMode.UNAVAILABLE,
            reason=OrganizationModuleAccessReason.ACTIVATION_DISABLED,
            definition=definition,
            activation=activation,
            is_verified=verified,
            has_entitlement=entitled,
            can_manage=can_manage,
            can_write=False,
        )

    if activation.status == OrganizationModuleActivationStatus.SUSPENDED:
        return OrganizationModuleAccess(
            module_key=normalized_key,
            access_mode=OrganizationModuleAccessMode.LOCKED,
            reason=OrganizationModuleAccessReason.ACTIVATION_SUSPENDED,
            definition=definition,
            activation=activation,
            is_verified=verified,
            has_entitlement=entitled,
            can_manage=can_manage,
            can_write=False,
        )

    if (
        organization.subscription_account.status
        != SubscriptionAccountStatus.ACTIVE
    ):
        return OrganizationModuleAccess(
            module_key=normalized_key,
            access_mode=OrganizationModuleAccessMode.LOCKED,
            reason=(
                OrganizationModuleAccessReason.SUBSCRIPTION_ACCOUNT_UNAVAILABLE
            ),
            definition=definition,
            activation=activation,
            is_verified=verified,
            has_entitlement=False,
            can_manage=can_manage,
            can_write=False,
        )

    if definition.requires_verification and not verified:
        return OrganizationModuleAccess(
            module_key=normalized_key,
            access_mode=OrganizationModuleAccessMode.LOCKED,
            reason=OrganizationModuleAccessReason.VERIFICATION_REQUIRED,
            definition=definition,
            activation=activation,
            is_verified=False,
            has_entitlement=entitled,
            can_manage=can_manage,
            can_write=False,
        )

    if definition.requires_entitlement and not entitled:
        return OrganizationModuleAccess(
            module_key=normalized_key,
            access_mode=definition.fallback_access_mode,
            reason=OrganizationModuleAccessReason.ENTITLEMENT_REQUIRED,
            definition=definition,
            activation=activation,
            is_verified=verified,
            has_entitlement=False,
            can_manage=can_manage,
            can_write=False,
        )

    return OrganizationModuleAccess(
        module_key=normalized_key,
        access_mode=OrganizationModuleAccessMode.FULL,
        reason=OrganizationModuleAccessReason.AVAILABLE,
        definition=definition,
        activation=activation,
        is_verified=verified,
        has_entitlement=entitled,
        can_manage=can_manage,
        can_write=can_manage,
    )


def ensure_organization_module_read_access(
    *,
    organization,
    module_key,
    actor=None,
    now=None,
):
    access = get_organization_module_access(
        organization=organization,
        module_key=module_key,
        actor=actor,
        now=now,
    )

    if access.access_mode not in {
        OrganizationModuleAccessMode.FULL,
        OrganizationModuleAccessMode.READ_ONLY,
    }:
        raise PermissionDenied(
            f"Organization module access is unavailable: {access.reason}."
        )

    return access


def ensure_organization_module_write_access(
    *,
    organization,
    module_key,
    actor,
    now=None,
):
    access = get_organization_module_access(
        organization=organization,
        module_key=module_key,
        actor=actor,
        now=now,
    )

    if not access.can_manage:
        raise PermissionDenied(
            "You do not have permission to manage this organization module."
        )

    if access.access_mode != OrganizationModuleAccessMode.FULL:
        raise PermissionDenied(
            f"Organization module is not writable: {access.reason}."
        )

    return access


def _validate_activation_eligibility(*, organization, definition, now=None):
    now = now or timezone.now()

    if organization.status != OrganizationStatus.ACTIVE:
        raise ValidationError(
            "Only active organizations can enable service modules."
        )

    if not definition.is_active:
        raise ValidationError("This organization module is not active.")

    if definition.requires_verification and not is_organization_verified(
        organization=organization,
        now=now,
    ):
        raise ValidationError(
            "Organization verification is required to enable this module."
        )

    if (
        organization.subscription_account.status
        != SubscriptionAccountStatus.ACTIVE
    ):
        raise ValidationError(
            "The organization subscription account is unavailable."
        )

    if definition.requires_entitlement and not has_entitlement(
        account=organization.subscription_account,
        key=definition.entitlement_key,
        now=now,
    ):
        raise ValidationError(
            "An active module entitlement is required to enable this module."
        )


@transaction.atomic
def activate_organization_module(
    *,
    organization,
    module_key,
    actor,
    display_name=None,
    summary=None,
    visibility=None,
    now=None,
):
    ensure_organization_modules_enabled()
    now = now or timezone.now()

    definition = get_organization_module_definition(
        module_key=module_key,
    )

    _require_actor_can_manage_module(
        actor=actor,
        organization=organization,
        module_key=definition.key,
    )

    _validate_activation_eligibility(
        organization=organization,
        definition=definition,
        now=now,
    )

    activation = (
        OrganizationModuleActivation.objects
        .select_for_update()
        .filter(
            organization=organization,
            module=definition,
        )
        .first()
    )

    created = activation is None

    if activation is None:
        activation = OrganizationModuleActivation(
            organization=organization,
            module=definition,
            activated_by=actor,
            activated_at=now,
        )

    if activation.status == OrganizationModuleActivationStatus.SUSPENDED:
        raise PermissionDenied(
            "Suspended modules must be restored through the TownLIT staff workflow."
        )

    previous_status = activation.status

    if created or display_name is not None:
        activation.display_name = display_name

    if created or summary is not None:
        activation.summary = summary

    if visibility is not None:
        activation.visibility = visibility
    activation.status = OrganizationModuleActivationStatus.ENABLED
    activation.disabled_at = None
    activation.suspended_at = None
    activation.last_changed_by = actor
    activation.full_clean()
    activation.save()

    # Initialize specialized module runtime in the same transaction.
    initialize_organization_module_runtime(
        activation=activation,
        actor=actor,
    )

    audit_action = (
        OrganizationAuditAction.MODULE_ENABLED
        if created or previous_status != OrganizationModuleActivationStatus.ENABLED
        else OrganizationAuditAction.MODULE_UPDATED
    )

    OrganizationAuditLog.objects.create(
        organization=organization,
        action=audit_action,
        source=OrganizationAuditSource.SERVICE,
        actor=actor,
        module_activation=activation,
        metadata={
            "module_key": definition.key,
            "visibility": activation.visibility,
        },
    )

    return activation


@transaction.atomic
def update_organization_module_profile(
    *,
    activation,
    actor,
    display_name=None,
    summary=None,
    visibility=None,
):
    ensure_organization_modules_enabled()

    activation = (
        OrganizationModuleActivation.objects
        .select_for_update()
        .select_related("organization", "module")
        .get(pk=activation.pk)
    )

    _require_actor_can_manage_module(
        actor=actor,
        organization=activation.organization,
        module_key=activation.module.key,
    )

    if (
        activation.status == OrganizationModuleActivationStatus.SUSPENDED
        and not getattr(actor, "is_staff", False)
    ):
        raise PermissionDenied(
            "This organization module is suspended by TownLIT."
        )

    activation.display_name = display_name
    activation.summary = summary

    if visibility is not None:
        activation.visibility = visibility

    activation.last_changed_by = actor
    activation.full_clean()
    activation.save()

    OrganizationAuditLog.objects.create(
        organization=activation.organization,
        action=OrganizationAuditAction.MODULE_UPDATED,
        source=OrganizationAuditSource.SERVICE,
        actor=actor,
        module_activation=activation,
        metadata={
            "module_key": activation.module.key,
            "visibility": activation.visibility,
        },
    )

    return activation


@transaction.atomic
def disable_organization_module(*, activation, actor, now=None):
    ensure_organization_modules_enabled()
    now = now or timezone.now()

    activation = (
        OrganizationModuleActivation.objects
        .select_for_update()
        .select_related("organization", "module")
        .get(pk=activation.pk)
    )

    _require_actor_can_manage_module(
        actor=actor,
        organization=activation.organization,
        module_key=activation.module.key,
    )

    if activation.status == OrganizationModuleActivationStatus.SUSPENDED:
        raise PermissionDenied(
            "Suspended modules can only be restored by TownLIT staff."
        )

    if activation.status == OrganizationModuleActivationStatus.DISABLED:
        return activation

    activation.status = OrganizationModuleActivationStatus.DISABLED
    activation.disabled_at = now
    activation.suspended_at = None
    activation.last_changed_by = actor
    activation.full_clean()
    activation.save()

    OrganizationAuditLog.objects.create(
        organization=activation.organization,
        action=OrganizationAuditAction.MODULE_DISABLED,
        source=OrganizationAuditSource.SERVICE,
        actor=actor,
        module_activation=activation,
        metadata={"module_key": activation.module.key},
    )

    return activation


@transaction.atomic
def suspend_organization_module(*, activation, actor, reason, now=None):
    ensure_organization_modules_enabled()
    now = now or timezone.now()

    if not actor or not getattr(actor, "is_staff", False):
        raise PermissionDenied(
            "Only TownLIT staff can suspend organization modules."
        )

    activation = (
        OrganizationModuleActivation.objects
        .select_for_update()
        .select_related("organization", "module")
        .get(pk=activation.pk)
    )

    if activation.status == OrganizationModuleActivationStatus.SUSPENDED:
        return activation

    activation.status = OrganizationModuleActivationStatus.SUSPENDED
    activation.suspended_at = now
    activation.disabled_at = None
    activation.last_changed_by = actor
    activation.metadata = {
        **(activation.metadata or {}),
        "suspension_reason": str(reason or "").strip(),
    }
    activation.full_clean()
    activation.save()

    OrganizationAuditLog.objects.create(
        organization=activation.organization,
        action=OrganizationAuditAction.MODULE_SUSPENDED,
        source=OrganizationAuditSource.ADMIN,
        actor=actor,
        module_activation=activation,
        metadata={
            "module_key": activation.module.key,
            "reason": str(reason or "").strip(),
        },
    )

    return activation


@transaction.atomic
def restore_suspended_organization_module(*, activation, actor):
    ensure_organization_modules_enabled()

    if not actor or not getattr(actor, "is_staff", False):
        raise PermissionDenied(
            "Only TownLIT staff can restore suspended organization modules."
        )

    activation = (
        OrganizationModuleActivation.objects
        .select_for_update()
        .select_related("organization", "module")
        .get(pk=activation.pk)
    )

    if activation.status != OrganizationModuleActivationStatus.SUSPENDED:
        return activation

    activation.status = OrganizationModuleActivationStatus.ENABLED
    activation.suspended_at = None
    activation.disabled_at = None
    activation.last_changed_by = actor
    activation.full_clean()
    activation.save()

    OrganizationAuditLog.objects.create(
        organization=activation.organization,
        action=OrganizationAuditAction.MODULE_RESTORED,
        source=OrganizationAuditSource.ADMIN,
        actor=actor,
        module_activation=activation,
        metadata={"module_key": activation.module.key},
    )

    return activation
