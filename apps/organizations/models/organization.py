# apps/organizations/models/organization.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.organizations.upload_paths import organization_logo_upload_to
from apps.organizations.constants import (
    OrganizationKind,
    OrganizationStatus,
    OrganizationVisibility,
)
from common.reference_data.countries import COUNTRY_CHOICES
from common.reference_data.languages import LANGUAGE_CHOICES
from validators.mediaValidators.image_validators import (
    validate_image_file,
    validate_image_size,
)
from validators.security_validators import validate_no_executable_file
from validators.user_validators import validate_phone_number


class Organization(models.Model):

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    name = models.CharField(
        max_length=160,
        db_index=True,
    )
    slug = models.SlugField(
        max_length=190,
        unique=True,
        allow_unicode=True,
        db_index=True,
    )
    kind = models.CharField(
        max_length=40,
        choices=OrganizationKind.choices,
        db_index=True,
    )

    description = models.TextField(
        null=True,
        blank=True,
    )
    history = models.TextField(
        null=True,
        blank=True,
    )
    statement_of_faith = models.TextField(
        null=True,
        blank=True,
    )
    statement_of_purpose = models.TextField(
        null=True,
        blank=True,
    )

    logo = models.ImageField(
        upload_to=organization_logo_upload_to,
        null=True,
        blank=True,
        validators=[
            validate_image_file,
            validate_image_size,
            validate_no_executable_file,
        ],
    )

    public_email = models.EmailField(
        null=True,
        blank=True,
    )
    public_phone_number = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        validators=[validate_phone_number],
    )
    website_url = models.URLField(
        max_length=500,
        null=True,
        blank=True,
    )

    country = models.CharField(
        max_length=2,
        choices=COUNTRY_CHOICES,
        null=True,
        blank=True,
        db_index=True,
    )
    city = models.CharField(
        max_length=120,
        null=True,
        blank=True,
    )

    primary_language = models.CharField(
        max_length=5,
        choices=LANGUAGE_CHOICES,
        null=True,
        blank=True,
    )
    secondary_language = models.CharField(
        max_length=5,
        choices=LANGUAGE_CHOICES,
        null=True,
        blank=True,
    )
    timezone = models.CharField(
        max_length=64,
        default="UTC",
    )

    subscription_account = models.OneToOneField(
        "subscriptions.SubscriptionAccount",
        on_delete=models.PROTECT,
        related_name="organization",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_organizations_v2",
    )

    status = models.CharField(
        max_length=20,
        choices=OrganizationStatus.choices,
        default=OrganizationStatus.ACTIVE,
        db_index=True,
    )
    visibility = models.CharField(
        max_length=20,
        choices=OrganizationVisibility.choices,
        default=OrganizationVisibility.PUBLIC,
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )
    updated_at = models.DateTimeField(auto_now=True)
    suspended_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    class Meta:
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"
        ordering = ("name", "id")
        indexes = [
            models.Index(
                fields=[
                    "status",
                    "visibility",
                    "kind",
                ]
            ),
            models.Index(
                fields=[
                    "country",
                    "city",
                ]
            ),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(primary_language__isnull=True)
                    | models.Q(secondary_language__isnull=True)
                    | ~models.Q(
                        primary_language=models.F(
                            "secondary_language"
                        )
                    )
                ),
                name=(
                    "organizations_distinct_"
                    "profile_languages"
                ),
            ),
        ]

    def clean(self):
        super().clean()

        primary = (
            str(self.primary_language).strip()
            if self.primary_language
            else None
        )
        secondary = (
            str(self.secondary_language).strip()
            if self.secondary_language
            else None
        )

        if secondary and not primary:
            raise ValidationError({
                "secondary_language": (
                    "A secondary language requires a primary language."
                ),
            })

        if primary and secondary and primary == secondary:
            raise ValidationError({
                "secondary_language": (
                    "Primary and secondary languages must be different."
                ),
            })

        try:
            ZoneInfo(self.timezone or "UTC")
        except ZoneInfoNotFoundError as exc:
            raise ValidationError({
                "timezone": "Invalid IANA timezone.",
            }) from exc

    def save(self, *args, **kwargs):
        self.name = " ".join(
            str(self.name or "").split()
        )
        self.primary_language = (
            str(self.primary_language).strip()
            if self.primary_language
            else None
        )
        self.secondary_language = (
            str(self.secondary_language).strip()
            if self.secondary_language
            else None
        )
        self.timezone = (
            str(self.timezone or "UTC").strip()
            or "UTC"
        )

        super().save(*args, **kwargs)

    @property
    def is_operational(self) -> bool:
        return self.status == OrganizationStatus.ACTIVE

    def get_absolute_url(self):
        return f"/organizations/{self.slug}"

    def __str__(self):
        return self.name
