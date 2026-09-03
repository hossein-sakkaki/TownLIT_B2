# apps/organizations/models/role.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.organizations.constants import OrganizationRoleScope


class OrganizationPermission(models.Model):
    id = models.BigAutoField(primary_key=True)
    key = models.CharField(
        max_length=140,
        unique=True,
        db_index=True,
    )
    name = models.CharField(max_length=160)
    category = models.CharField(
        max_length=60,
        db_index=True,
    )
    description = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organization Permission"
        verbose_name_plural = "Organization Permissions"
        ordering = ("category", "key")

    def __str__(self):
        return self.key


class OrganizationRole(models.Model):
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
        related_name="roles",
    )
    key = models.SlugField(
        max_length=80,
        allow_unicode=False,
    )
    name = models.CharField(max_length=120)
    description = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )

    permissions = models.ManyToManyField(
        OrganizationPermission,
        through="organizations.OrganizationRolePermission",
        related_name="roles",
        blank=True,
    )

    priority = models.PositiveSmallIntegerField(
        default=100,
        db_index=True,
    )
    is_system = models.BooleanField(default=False)
    is_protected = models.BooleanField(default=False)
    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organization Role"
        verbose_name_plural = "Organization Roles"
        ordering = ("-priority", "name")
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "key",
                ],
                name=(
                    "organizations_unique_role_key_"
                    "per_organization"
                ),
            ),
        ]

    def __str__(self):
        return f"{self.organization_id}:{self.key}"


class OrganizationRolePermission(models.Model):
    id = models.BigAutoField(primary_key=True)
    role = models.ForeignKey(
        OrganizationRole,
        on_delete=models.CASCADE,
        related_name="role_permissions",
    )
    permission = models.ForeignKey(
        OrganizationPermission,
        on_delete=models.PROTECT,
        related_name="role_permissions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Organization Role Permission"
        verbose_name_plural = "Organization Role Permissions"
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "role",
                    "permission",
                ],
                name=(
                    "organizations_unique_"
                    "role_permission"
                ),
            ),
        ]

    def __str__(self):
        return f"{self.role_id}:{self.permission.key}"


class OrganizationRoleAssignment(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.CASCADE,
        related_name="role_assignments",
    )
    role = models.ForeignKey(
        OrganizationRole,
        on_delete=models.PROTECT,
        related_name="assignments",
    )

    scope_type = models.CharField(
        max_length=20,
        choices=OrganizationRoleScope.choices,
        default=OrganizationRoleScope.ORGANIZATION,
        db_index=True,
    )
    scope_key = models.CharField(
        max_length=120,
        default="",
        blank=True,
        db_index=True,
    )

    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_organization_roles",
    )

    starts_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )
    ends_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    # MySQL-safe uniqueness slot for an active assignment.
    active_slot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organization Role Assignment"
        verbose_name_plural = "Organization Role Assignments"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "membership",
                    "role",
                    "scope_type",
                    "scope_key",
                    "active_slot",
                ],
                name=(
                    "organizations_unique_active_"
                    "role_assignment"
                ),
            ),
            models.CheckConstraint(
                check=(
                    Q(
                        scope_type=OrganizationRoleScope.ORGANIZATION,
                        scope_key="",
                    )
                    | (
                        Q(
                            scope_type=OrganizationRoleScope.MODULE
                        )
                        & ~Q(scope_key="")
                    )
                ),
                name=(
                    "organizations_role_assignment_"
                    "scope_consistent"
                ),
            ),
            models.CheckConstraint(
                check=(
                    Q(ends_at__isnull=True)
                    | Q(
                        ends_at__gt=models.F(
                            "starts_at"
                        )
                    )
                ),
                name=(
                    "organizations_role_assignment_"
                    "valid_window"
                ),
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "membership",
                    "is_active",
                    "scope_type",
                    "scope_key",
                ]
            ),
        ]

    def _sync_active_slot(self):
        self.active_slot = 1 if self.is_active else None

    def clean(self):
        super().clean()
        self._sync_active_slot()

        if (
            self.role.organization_id
            != self.membership.organization_id
        ):
            raise ValidationError({
                "role": (
                    "Role and membership must belong to the same organization."
                ),
            })

        if (
            self.scope_type
            == OrganizationRoleScope.ORGANIZATION
            and self.scope_key
        ):
            raise ValidationError({
                "scope_key": (
                    "Organization-scoped roles cannot define a module scope key."
                ),
            })

        if (
            self.scope_type == OrganizationRoleScope.MODULE
            and not self.scope_key
        ):
            raise ValidationError({
                "scope_key": (
                    "Module-scoped roles require a scope key."
                ),
            })

        if (
            self.scope_type == OrganizationRoleScope.MODULE
            and self.scope_key
        ):
            from apps.organizations.models.module import (
                OrganizationModuleActivation,
            )

            if not OrganizationModuleActivation.objects.filter(
                organization_id=self.membership.organization_id,
                module__key=self.scope_key,
            ).exists():
                raise ValidationError({
                    "scope_key": (
                        "Module-scoped roles require an existing "
                        "organization module activation."
                    ),
                })

        if (
            self.ends_at
            and self.ends_at <= self.starts_at
        ):
            raise ValidationError({
                "ends_at": (
                    "Role assignment end must be after its start."
                ),
            })

    def save(self, *args, **kwargs):
        self._sync_active_slot()

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.add("active_slot")
            kwargs["update_fields"] = list(update_fields)

        return super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.membership_id}:"
            f"{self.role.key}:"
            f"{self.scope_type}:"
            f"{self.scope_key or '*'}"
        )
