# apps/organizations/services/module_catalog.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.organizations.constants import (
    DEFAULT_ORGANIZATION_MODULE_DEFINITIONS,
    ORGANIZATION_MODULE_ENTITLEMENT_PREFIX,
    OrganizationModuleFallbackAccessMode,
)
from apps.organizations.models import OrganizationModuleDefinition
from apps.subscriptions.constants import EntitlementValueType
from apps.subscriptions.models import EntitlementDefinition, PlanEntitlement


def module_entitlement_key(module_key: str) -> str:
    normalized_key = str(module_key or "").strip().lower()

    if not normalized_key:
        raise ValidationError("Module key is required.")

    return f"{ORGANIZATION_MODULE_ENTITLEMENT_PREFIX}{normalized_key}"


@transaction.atomic
def bootstrap_organization_module_catalog():
    modules = {}

    for definition in DEFAULT_ORGANIZATION_MODULE_DEFINITIONS:
        module_key = str(definition["key"])
        entitlement_key = module_entitlement_key(module_key)

        entitlement, _ = EntitlementDefinition.objects.get_or_create(
            key=entitlement_key,
            defaults={
                "name": definition["name"],
                "description": definition["description"],
                "value_type": EntitlementValueType.BOOLEAN,
                "default_value": False,
                "is_active": True,
                "metadata": {
                    "domain": "organizations",
                    "module_key": module_key,
                },
            },
        )

        entitlement.name = definition["name"]
        entitlement.description = definition["description"]
        entitlement.value_type = EntitlementValueType.BOOLEAN
        entitlement.default_value = False
        entitlement.is_active = True
        entitlement.metadata = {
            **(entitlement.metadata or {}),
            "domain": "organizations",
            "module_key": module_key,
        }
        entitlement.full_clean()
        entitlement.save(
            update_fields=[
                "name",
                "description",
                "value_type",
                "default_value",
                "is_active",
                "metadata",
                "updated_at",
            ]
        )

        module, _ = OrganizationModuleDefinition.objects.get_or_create(
            key=module_key,
            defaults={
                "name": definition["name"],
                "description": definition["description"],
                "entitlement_key": entitlement_key,
                "requires_verification": True,
                "requires_entitlement": True,
                "fallback_access_mode": (
                    OrganizationModuleFallbackAccessMode.READ_ONLY
                ),
                "schema_version": 1,
                "sort_order": definition["sort_order"],
                "is_public_catalog": True,
                "is_active": True,
            },
        )

        module.name = definition["name"]
        module.description = definition["description"]
        module.entitlement_key = entitlement_key
        module.requires_verification = True
        module.requires_entitlement = True
        module.fallback_access_mode = (
            OrganizationModuleFallbackAccessMode.READ_ONLY
        )
        module.sort_order = definition["sort_order"]
        module.is_public_catalog = True
        module.is_active = True
        module.full_clean()
        module.save(
            update_fields=[
                "name",
                "description",
                "entitlement_key",
                "requires_verification",
                "requires_entitlement",
                "fallback_access_mode",
                "sort_order",
                "is_public_catalog",
                "is_active",
                "updated_at",
            ]
        )

        modules[module.key] = module

    return modules


def get_organization_module_definition(*, module_key, active_only=True):
    queryset = OrganizationModuleDefinition.objects.all()

    if active_only:
        queryset = queryset.filter(is_active=True)

    module = queryset.filter(
        key=str(module_key or "").strip().lower()
    ).first()

    if not module:
        raise ValidationError("Unknown organization module.")

    return module


@transaction.atomic
def set_plan_module_entitlement(*, plan, module_key, value=True):
    module = get_organization_module_definition(module_key=module_key)

    entitlement = EntitlementDefinition.objects.get(
        key=module.entitlement_key,
        is_active=True,
    )

    item, _ = PlanEntitlement.objects.update_or_create(
        plan=plan,
        entitlement=entitlement,
        defaults={"value": bool(value)},
    )

    item.full_clean()
    item.save()
    return item


@transaction.atomic
def set_plan_module_entitlements(*, plan, module_values):
    results = {}

    for module_key, value in dict(module_values).items():
        item = set_plan_module_entitlement(
            plan=plan,
            module_key=module_key,
            value=value,
        )
        results[str(module_key)] = item

    return results
