# apps/organizations/models/organization.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-09-27.
#

import uuid
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from apps.organizations.constants import (
    OrganizationKind,
    OrganizationServiceDeliveryMode,
    OrganizationStatus,
    OrganizationVisibility,
)
from apps.organizations.upload_paths import (
    organization_cover_upload_to,
    organization_logo_upload_to,
    organization_thumbnail_upload_to,
)
from common.reference_data.countries import COUNTRY_CHOICES
from common.reference_data.languages import LANGUAGE_CHOICES
from validators.mediaValidators.image_validators import (
    validate_image_file,
    validate_image_size,
)
from validators.security_validators import (
    validate_no_executable_file,
)
from validators.user_validators import validate_phone_number


BRAND_COLOR_VALIDATOR = RegexValidator(
    regex=r"^#[0-9A-Fa-f]{6}$",
    message=(
        "Brand color must use a six-digit HEX value, "
        "for example #1A73E8."
    ),
)


class Organization(models.Model):

    id = models.BigAutoField(
        primary_key=True,
    )

    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    name = models.CharField(
        max_length=160,
        db_index=True,
    )

    short_name = models.CharField(
        max_length=80,
        blank=True,
        default="",
    )

    tagline = models.CharField(
        max_length=240,
        blank=True,
        default="",
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

    founded_year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    # Lightweight public descriptors.
    # This is intentionally independent from the 12 organization modules.
    activity_areas = models.JSONField(
        default=list,
        blank=True,
    )

    # ------------------------------------------------------------------
    # About
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Visual identity
    # ------------------------------------------------------------------

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

    cover_image = models.ImageField(
        upload_to=organization_cover_upload_to,
        null=True,
        blank=True,
        validators=[
            validate_image_file,
            validate_image_size,
            validate_no_executable_file,
        ],
    )

    thumbnail = models.ImageField(
        upload_to=organization_thumbnail_upload_to,
        null=True,
        blank=True,
        validators=[
            validate_image_file,
            validate_image_size,
            validate_no_executable_file,
        ],
    )

    brand_color = models.CharField(
        max_length=7,
        blank=True,
        default="",
        validators=[
            BRAND_COLOR_VALIDATOR,
        ],
    )

    # Existing reusable organization media is selected after
    # the organization has already been created.
    intro_video = models.ForeignKey(
        "organization_media.OrganizationMediaAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name=(
            "featured_intro_for_organizations"
        ),
    )

    # ------------------------------------------------------------------
    # Primary contact
    # ------------------------------------------------------------------

    public_email = models.EmailField(
        null=True,
        blank=True,
    )

    public_phone_number = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        validators=[
            validate_phone_number,
        ],
    )

    website_url = models.URLField(
        max_length=500,
        null=True,
        blank=True,
    )

    # ------------------------------------------------------------------
    # Location
    # ------------------------------------------------------------------

    country = models.CharField(
        max_length=2,
        choices=COUNTRY_CHOICES,
        null=True,
        blank=True,
        db_index=True,
    )

    province_region = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    city = models.CharField(
        max_length=120,
        null=True,
        blank=True,
    )

    postal_code = models.CharField(
        max_length=32,
        blank=True,
        default="",
    )

    address_line1 = models.CharField(
        max_length=250,
        blank=True,
        default="",
    )

    address_line2 = models.CharField(
        max_length=250,
        blank=True,
        default="",
    )

    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )

    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )

    location_url = models.URLField(
        max_length=1000,
        blank=True,
        default="",
    )

    # ------------------------------------------------------------------
    # Service delivery / visiting
    # ------------------------------------------------------------------

    service_delivery_mode = models.CharField(
        max_length=20,
        choices=OrganizationServiceDeliveryMode.choices,
        blank=True,
        default="",
        db_index=True,
    )

    visit_instructions = models.TextField(
        blank=True,
        default="",
    )

    appointment_url = models.URLField(
        max_length=1000,
        blank=True,
        default="",
    )

    contact_form_url = models.URLField(
        max_length=1000,
        blank=True,
        default="",
    )

    # ------------------------------------------------------------------
    # Language / timezone
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Platform relationships
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

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

    updated_at = models.DateTimeField(
        auto_now=True,
    )

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

        ordering = (
            "name",
            "id",
        )

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
            models.Index(
                fields=[
                    "service_delivery_mode",
                    "status",
                ]
            ),
        ]

        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(
                        primary_language__isnull=True
                    )
                    | models.Q(
                        secondary_language__isnull=True
                    )
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

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def clean(self):
        super().clean()

        self._validate_languages()
        self._validate_timezone()
        self._validate_founded_year()
        self._validate_coordinates()
        self._validate_intro_video()

        self.activity_areas = (
            self._normalize_activity_areas(
                self.activity_areas
            )
        )

    def _validate_languages(self):
        primary = (
            str(
                self.primary_language
            ).strip()
            if self.primary_language
            else None
        )

        secondary = (
            str(
                self.secondary_language
            ).strip()
            if self.secondary_language
            else None
        )

        if secondary and not primary:
            raise ValidationError({
                "secondary_language": (
                    "A secondary language requires "
                    "a primary language."
                ),
            })

        if (
            primary
            and secondary
            and primary == secondary
        ):
            raise ValidationError({
                "secondary_language": (
                    "Primary and secondary languages "
                    "must be different."
                ),
            })

    def _validate_timezone(self):
        try:
            ZoneInfo(
                self.timezone or "UTC"
            )

        except ZoneInfoNotFoundError as exc:
            raise ValidationError({
                "timezone": (
                    "Invalid IANA timezone."
                ),
            }) from exc

    def _validate_founded_year(self):
        if self.founded_year is None:
            return

        current_year = (
            timezone.localdate().year
        )

        if not (
            1
            <= self.founded_year
            <= current_year
        ):
            raise ValidationError({
                "founded_year": (
                    "Founded year must be between "
                    f"1 and {current_year}."
                ),
            })

    def _validate_coordinates(self):
        has_latitude = (
            self.latitude is not None
        )

        has_longitude = (
            self.longitude is not None
        )

        if has_latitude != has_longitude:
            raise ValidationError({
                "latitude": (
                    "Latitude and longitude must "
                    "be provided together."
                ),
                "longitude": (
                    "Latitude and longitude must "
                    "be provided together."
                ),
            })

        if self.latitude is not None:
            if not (
                Decimal("-90")
                <= self.latitude
                <= Decimal("90")
            ):
                raise ValidationError({
                    "latitude": (
                        "Latitude must be between "
                        "-90 and 90."
                    ),
                })

        if self.longitude is not None:
            if not (
                Decimal("-180")
                <= self.longitude
                <= Decimal("180")
            ):
                raise ValidationError({
                    "longitude": (
                        "Longitude must be between "
                        "-180 and 180."
                    ),
                })

    def _validate_intro_video(self):
        if not self.intro_video_id:
            return

        if not self.pk:
            raise ValidationError({
                "intro_video": (
                    "Intro video can only be assigned "
                    "after the organization exists."
                ),
            })

        asset = self.intro_video

        if (
            asset.organization_id
            != self.pk
        ):
            raise ValidationError({
                "intro_video": (
                    "Intro video must belong to "
                    "this organization."
                ),
            })

        if (
            str(
                getattr(
                    asset,
                    "kind",
                    "",
                )
            ).lower()
            != "video"
        ):
            raise ValidationError({
                "intro_video": (
                    "Intro media must be a video."
                ),
            })

        if (
            str(
                getattr(
                    asset,
                    "status",
                    "",
                )
            ).lower()
            != "ready"
        ):
            raise ValidationError({
                "intro_video": (
                    "Intro video must be ready "
                    "before it can be featured."
                ),
            })

    @staticmethod
    def _normalize_activity_areas(
        value,
    ):
        if value in (
            None,
            "",
        ):
            return []

        if not isinstance(
            value,
            list,
        ):
            raise ValidationError({
                "activity_areas": (
                    "Activity areas must be a list."
                ),
            })

        if len(value) > 12:
            raise ValidationError({
                "activity_areas": (
                    "A maximum of 12 activity areas "
                    "is allowed."
                ),
            })

        normalized = []
        seen = set()

        for item in value:
            item = " ".join(
                str(
                    item or ""
                ).split()
            )

            if not item:
                continue

            if len(item) > 80:
                raise ValidationError({
                    "activity_areas": (
                        "Each activity area must be "
                        "80 characters or fewer."
                    ),
                })

            key = item.casefold()

            if key in seen:
                continue

            seen.add(
                key
            )

            normalized.append(
                item
            )

        return normalized

    # ------------------------------------------------------------------
    # Persistence normalization
    # ------------------------------------------------------------------

    def save(
        self,
        *args,
        **kwargs,
    ):
        self.name = " ".join(
            str(
                self.name or ""
            ).split()
        )

        self.short_name = " ".join(
            str(
                self.short_name or ""
            ).split()
        )

        self.tagline = " ".join(
            str(
                self.tagline or ""
            ).split()
        )

        self.province_region = " ".join(
            str(
                self.province_region or ""
            ).split()
        )

        self.postal_code = " ".join(
            str(
                self.postal_code or ""
            ).split()
        )

        self.address_line1 = " ".join(
            str(
                self.address_line1 or ""
            ).split()
        )

        self.address_line2 = " ".join(
            str(
                self.address_line2 or ""
            ).split()
        )

        self.brand_color = (
            str(
                self.brand_color or ""
            )
            .strip()
            .upper()
        )

        self.activity_areas = (
            self._normalize_activity_areas(
                self.activity_areas
            )
        )

        self.primary_language = (
            str(
                self.primary_language
            ).strip()
            if self.primary_language
            else None
        )

        self.secondary_language = (
            str(
                self.secondary_language
            ).strip()
            if self.secondary_language
            else None
        )

        self.timezone = (
            str(
                self.timezone or "UTC"
            ).strip()
            or "UTC"
        )

        super().save(
            *args,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def is_operational(
        self,
    ) -> bool:
        return (
            self.status
            == OrganizationStatus.ACTIVE
        )

    def get_absolute_url(self):
        return (
            f"/organizations/{self.slug}"
        )

    @property
    def share_url(self):
        base_url = str(
            getattr(
                settings,
                "APP_LINK_BASE_URL",
                "",
            )
            or getattr(
                settings,
                "UNIVERSAL_LINK_BASE_URL",
                "",
            )
            or getattr(
                settings,
                "SITE_URL",
                "",
            )
            or ""
        ).rstrip("/")

        path = self.get_absolute_url()

        return (
            f"{base_url}{path}"
            if base_url
            else path
        )

    def __str__(self):
        return self.name