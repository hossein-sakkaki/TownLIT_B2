# apps/subscriptions/models/entitlement.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-28.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.subscriptions.constants import (
    EntitlementGrantSource,
    EntitlementValueType,
)


def _default_false():
    return False


def _default_true():
    return True


def _validate_value_type(*, value_type, value):
    if (
        value_type == EntitlementValueType.BOOLEAN
        and not isinstance(value, bool)
    ):
        raise ValidationError(
            "Entitlement value must be a boolean."
        )

    if value_type == EntitlementValueType.INTEGER:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
        ):
            raise ValidationError(
                "Entitlement value must be an integer."
            )

    if value_type == EntitlementValueType.DECIMAL:
        try:
            Decimal(str(value))
        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ) as exc:
            raise ValidationError(
                "Entitlement value must be decimal-compatible."
            ) from exc

    if (
        value_type == EntitlementValueType.STRING
        and not isinstance(value, str)
    ):
        raise ValidationError(
            "Entitlement value must be a string."
        )


class EntitlementDefinition(models.Model):
    id = models.BigAutoField(
        primary_key=True,
    )

    key = models.CharField(
        max_length=140,
        unique=True,
    )

    name = models.CharField(
        max_length=140,
    )

    description = models.TextField(
        blank=True,
    )

    value_type = models.CharField(
        max_length=20,
        choices=EntitlementValueType.choices,
        default=EntitlementValueType.BOOLEAN,
    )

    default_value = models.JSONField(
        default=_default_false,
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Entitlement Definition"
        verbose_name_plural = "Entitlement Definitions"
        ordering = ("key",)

    def clean(self):
        super().clean()

        _validate_value_type(
            value_type=self.value_type,
            value=self.default_value,
        )

    def __str__(self):
        return self.key


class PlanEntitlement(models.Model):
    id = models.BigAutoField(
        primary_key=True,
    )

    plan = models.ForeignKey(
        "subscriptions.SubscriptionPlan",
        on_delete=models.CASCADE,
        related_name="plan_entitlements",
    )

    entitlement = models.ForeignKey(
        EntitlementDefinition,
        on_delete=models.PROTECT,
        related_name="plan_entitlements",
    )

    value = models.JSONField(
        default=_default_true,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Plan Entitlement"
        verbose_name_plural = "Plan Entitlements"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "plan",
                    "entitlement",
                ],
                name=(
                    "subscriptions_unique_"
                    "plan_entitlement"
                ),
            ),
        ]

    def clean(self):
        super().clean()

        _validate_value_type(
            value_type=self.entitlement.value_type,
            value=self.value,
        )

    def __str__(self):
        return (
            f"{self.plan.key}:"
            f"{self.entitlement.key}"
        )


class EntitlementGrant(models.Model):
    id = models.BigAutoField(
        primary_key=True,
    )

    account = models.ForeignKey(
        "subscriptions.SubscriptionAccount",
        on_delete=models.CASCADE,
        related_name="entitlement_grants",
    )

    entitlement = models.ForeignKey(
        EntitlementDefinition,
        on_delete=models.PROTECT,
        related_name="grants",
    )

    value = models.JSONField(
        default=_default_true,
    )

    source = models.CharField(
        max_length=20,
        choices=EntitlementGrantSource.choices,
        default=EntitlementGrantSource.SYSTEM,
        db_index=True,
    )

    priority = models.PositiveSmallIntegerField(
        default=100,
        db_index=True,
    )

    source_subscription = models.ForeignKey(
        "subscriptions.Subscription",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entitlement_grants",
    )

    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name=(
            "subscription_entitlement_grants"
        ),
    )

    reason = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
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

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Entitlement Grant"
        verbose_name_plural = "Entitlement Grants"
        ordering = (
            "-priority",
            "-created_at",
        )

        constraints = [
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
                    "subscriptions_entitlement_"
                    "grant_valid_window"
                ),
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "account",
                    "entitlement",
                    "is_active",
                ]
            ),
            models.Index(
                fields=[
                    "account",
                    "priority",
                    "is_active",
                ]
            ),
        ]

    def clean(self):
        super().clean()

        _validate_value_type(
            value_type=self.entitlement.value_type,
            value=self.value,
        )

        if (
            self.ends_at
            and self.ends_at <= self.starts_at
        ):
            raise ValidationError({
                "ends_at": (
                    "Grant end must be after "
                    "grant start."
                ),
            })

    def __str__(self):
        return (
            f"{self.account_id}:"
            f"{self.entitlement.key}:"
            f"{self.value}"
        )