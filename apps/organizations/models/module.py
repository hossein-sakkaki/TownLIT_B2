# apps/organizations/models/module.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.organizations.constants import (
    ORGANIZATION_MODULE_ENTITLEMENT_PREFIX,
    OrganizationModuleAccessMode,
    OrganizationModuleActivationStatus,
    OrganizationModuleFallbackAccessMode,
    OrganizationModuleVisibility,
)


class OrganizationModuleDefinition(models.Model):
    id = models.BigAutoField(primary_key=True)

    key = models.SlugField(
        max_length=80,
        unique=True,
        allow_unicode=False,
        db_index=True,
    )
    name = models.CharField(max_length=160)
    description = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
    )

    entitlement_key = models.CharField(
        max_length=140,
        unique=True,
        db_index=True,
    )

    requires_verification = models.BooleanField(default=True)
    requires_entitlement = models.BooleanField(default=True)
    fallback_access_mode = models.CharField(
        max_length=20,
        choices=OrganizationModuleFallbackAccessMode.choices,
        default=OrganizationModuleFallbackAccessMode.READ_ONLY,
    )

    schema_version = models.PositiveSmallIntegerField(default=1)
    sort_order = models.PositiveSmallIntegerField(
        default=100,
        db_index=True,
    )

    is_public_catalog = models.BooleanField(
        default=True,
        db_index=True,
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organization Module Definition"
        verbose_name_plural = "Organization Module Definitions"
        ordering = ("sort_order", "name", "id")
        indexes = [
            models.Index(
                fields=[
                    "is_active",
                    "is_public_catalog",
                    "sort_order",
                ]
            ),
        ]

    def clean(self):
        super().clean()

        expected_entitlement_key = (
            f"{ORGANIZATION_MODULE_ENTITLEMENT_PREFIX}{self.key}"
        )

        if self.entitlement_key != expected_entitlement_key:
            raise ValidationError({
                "entitlement_key": (
                    "Organization module entitlement keys must use "
                    f"'{expected_entitlement_key}'."
                ),
            })

        if self.schema_version < 1:
            raise ValidationError({
                "schema_version": "Schema version must be at least 1.",
            })

    def save(self, *args, **kwargs):
        self.key = str(self.key or "").strip().lower()
        self.entitlement_key = str(
            self.entitlement_key or ""
        ).strip().lower()
        self.name = " ".join(str(self.name or "").split())

        return super().save(*args, **kwargs)

    def __str__(self):
        return self.key


class OrganizationModuleActivation(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="module_activations",
    )
    module = models.ForeignKey(
        OrganizationModuleDefinition,
        on_delete=models.PROTECT,
        related_name="activations",
    )

    display_name = models.CharField(
        max_length=160,
        null=True,
        blank=True,
    )
    summary = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
    )
    visibility = models.CharField(
        max_length=20,
        choices=OrganizationModuleVisibility.choices,
        default=OrganizationModuleVisibility.PUBLIC,
        db_index=True,
    )

    status = models.CharField(
        max_length=20,
        choices=OrganizationModuleActivationStatus.choices,
        default=OrganizationModuleActivationStatus.ENABLED,
        db_index=True,
    )

    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activated_organization_modules",
    )
    last_changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="changed_organization_modules",
    )

    activated_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )
    disabled_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )
    suspended_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    configuration = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organization Module Activation"
        verbose_name_plural = "Organization Module Activations"
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "module"],
                name="organizations_unique_module_activation",
            ),
            models.CheckConstraint(
                check=(
                    Q(
                        status=OrganizationModuleActivationStatus.ENABLED,
                        disabled_at__isnull=True,
                        suspended_at__isnull=True,
                    )
                    | Q(
                        status=OrganizationModuleActivationStatus.DISABLED,
                        disabled_at__isnull=False,
                        suspended_at__isnull=True,
                    )
                    | Q(
                        status=OrganizationModuleActivationStatus.SUSPENDED,
                        disabled_at__isnull=True,
                        suspended_at__isnull=False,
                    )
                ),
                name="organizations_module_activation_state_consistent",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "status", "visibility"]
            ),
            models.Index(
                fields=["module", "status"]
            ),
        ]

    def clean(self):
        super().clean()

        if self.status == OrganizationModuleActivationStatus.ENABLED:
            if self.disabled_at or self.suspended_at:
                raise ValidationError(
                    "Enabled module activations cannot have disabled or suspended timestamps."
                )

        if self.status == OrganizationModuleActivationStatus.DISABLED:
            if not self.disabled_at or self.suspended_at:
                raise ValidationError(
                    "Disabled module activations require only a disabled timestamp."
                )

        if self.status == OrganizationModuleActivationStatus.SUSPENDED:
            if not self.suspended_at or self.disabled_at:
                raise ValidationError(
                    "Suspended module activations require only a suspended timestamp."
                )

    def save(self, *args, **kwargs):
        self.display_name = (
            " ".join(str(self.display_name).split())
            if self.display_name
            else None
        )
        self.summary = (
            str(self.summary).strip()
            if self.summary
            else None
        )

        return super().save(*args, **kwargs)

    @property
    def is_enabled(self) -> bool:
        return self.status == OrganizationModuleActivationStatus.ENABLED

    @property
    def effective_name(self) -> str:
        return self.display_name or self.module.name

    def __str__(self):
        return f"{self.organization_id}:{self.module.key}:{self.status}"
