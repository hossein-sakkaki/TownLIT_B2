# apps/organizations/admin/organizations.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-10-13.
#

from urllib.parse import urlencode

from django.contrib import admin
from django.db.models import Count, Exists, OuterRef, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from apps.organizations.constants import (
    MembershipRequestStatus,
    OPEN_VERIFICATION_CASE_STATUSES,
    OrganizationMembershipStatus,
    OrganizationVerificationGrantStatus,
)
from apps.organizations.models import (
    Organization,
    OrganizationAuditLog,
    OrganizationMembership,
    OrganizationMembershipRequest,
    OrganizationModuleActivation,
    OrganizationVerificationCase,
    OrganizationVerificationGrant,
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "kind",
        "status_badge",
        "verification_badge",
        "active_members_count",
        "pending_requests_count",
        "open_verification_count",
        "country",
        "visibility",
        "updated_at",
    )
    list_filter = (
        "kind",
        "status",
        "visibility",
        "country",
        "service_delivery_mode",
        "primary_language",
    )
    search_fields = (
        "name",
        "short_name",
        "slug",
        "public_id",
        "public_email",
        "public_phone_number",
        "website_url",
        "city",
        "province_region",
    )
    ordering = ("name", "id")
    list_select_related = (
        "created_by",
        "subscription_account",
    )
    list_per_page = 50
    show_full_result_count = False
    date_hierarchy = "created_at"
    raw_id_fields = ("intro_video",)

    readonly_fields = (
        "public_id",
        "slug",
        "created_by",
        "subscription_account",
        "status",
        "suspended_at",
        "closed_at",
        "created_at",
        "updated_at",
        "admin_shortcuts",
    )

    fieldsets = (
        (
            "Operations",
            {
                "fields": (
                    "admin_shortcuts",
                    "status",
                    "visibility",
                    "created_by",
                    "subscription_account",
                    "created_at",
                    "updated_at",
                    "suspended_at",
                    "closed_at",
                ),
            },
        ),
        (
            "Identity",
            {
                "fields": (
                    "public_id",
                    "name",
                    "short_name",
                    "tagline",
                    "slug",
                    "kind",
                    "founded_year",
                    "activity_areas",
                ),
            },
        ),
        (
            "About",
            {
                "fields": (
                    "description",
                    "history",
                    "statement_of_faith",
                    "statement_of_purpose",
                ),
            },
        ),
        (
            "Visual identity",
            {
                "fields": (
                    "logo",
                    "cover_image",
                    "thumbnail",
                    "brand_color",
                    "intro_video",
                ),
            },
        ),
        (
            "Primary contact",
            {
                "fields": (
                    "public_email",
                    "public_phone_number",
                    "website_url",
                    "contact_form_url",
                    "appointment_url",
                ),
            },
        ),
        (
            "Location",
            {
                "fields": (
                    "country",
                    "province_region",
                    "city",
                    "postal_code",
                    "address_line1",
                    "address_line2",
                    "latitude",
                    "longitude",
                    "location_url",
                ),
            },
        ),
        (
            "Service & visit",
            {
                "fields": (
                    "service_delivery_mode",
                    "visit_instructions",
                ),
            },
        ),
        (
            "Language & timezone",
            {
                "fields": (
                    "primary_language",
                    "secondary_language",
                    "timezone",
                ),
            },
        ),
    )

    def get_queryset(self, request):
        now = timezone.now()

        active_grants = (
            OrganizationVerificationGrant.objects
            .filter(
                organization_id=OuterRef("pk"),
                status=OrganizationVerificationGrantStatus.ACTIVE,
                revoked_at__isnull=True,
            )
            .filter(
                Q(expires_at__isnull=True)
                | Q(expires_at__gt=now)
            )
        )

        return (
            super()
            .get_queryset(request)
            .annotate(
                _active_members_count=Count(
                    "memberships",
                    filter=Q(
                        memberships__status=OrganizationMembershipStatus.ACTIVE
                    ),
                    distinct=True,
                ),
                _pending_requests_count=Count(
                    "membership_requests",
                    filter=Q(
                        membership_requests__status=MembershipRequestStatus.PENDING
                    ),
                    distinct=True,
                ),
                _open_verification_count=Count(
                    "verification_cases",
                    filter=Q(
                        verification_cases__status__in=(
                            OPEN_VERIFICATION_CASE_STATUSES
                        )
                    ),
                    distinct=True,
                ),
                _has_active_verification=Exists(active_grants),
            )
        )

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colors = {
            "active": "#198754",
            "suspended": "#fd7e14",
            "closed": "#6c757d",
        }
        return self._badge(
            obj.get_status_display(),
            colors.get(obj.status, "#6c757d"),
        )

    @admin.display(description="Verification")
    def verification_badge(self, obj):
        if getattr(obj, "_has_active_verification", False):
            return self._badge("Verified", "#198754")

        open_count = getattr(obj, "_open_verification_count", 0)
        if open_count:
            return self._badge("In review", "#0d6efd")

        return self._badge("Not verified", "#6c757d")

    @admin.display(
        description="Active members",
        ordering="_active_members_count",
    )
    def active_members_count(self, obj):
        return getattr(obj, "_active_members_count", 0)

    @admin.display(
        description="Pending requests",
        ordering="_pending_requests_count",
    )
    def pending_requests_count(self, obj):
        return getattr(obj, "_pending_requests_count", 0)

    @admin.display(
        description="Open verification",
        ordering="_open_verification_count",
    )
    def open_verification_count(self, obj):
        return getattr(obj, "_open_verification_count", 0)

    @admin.display(description="Organization operations")
    def admin_shortcuts(self, obj):
        if not obj or not obj.pk:
            return "Save the organization before opening related operations."

        links = (
            (
                self._related_changelist_url(
                    OrganizationVerificationCase,
                    obj.pk,
                ),
                "Verification",
            ),
            (
                self._related_changelist_url(
                    OrganizationMembership,
                    obj.pk,
                ),
                "Members",
            ),
            (
                self._related_changelist_url(
                    OrganizationMembershipRequest,
                    obj.pk,
                ),
                "Membership requests",
            ),
            (
                self._related_changelist_url(
                    OrganizationModuleActivation,
                    obj.pk,
                ),
                "Modules",
            ),
            (
                self._related_changelist_url(
                    OrganizationAuditLog,
                    obj.pk,
                ),
                "Audit log",
            ),
        )

        return format_html_join(
            " ",
            '<a class="button" href="{}">{}</a>',
            links,
        )

    @staticmethod
    def _related_changelist_url(model, organization_id):
        url = reverse(
            (
                f"admin:{model._meta.app_label}_"
                f"{model._meta.model_name}_changelist"
            )
        )
        query = urlencode({
            "organization__id__exact": organization_id,
        })
        return f"{url}?{query}"

    @staticmethod
    def _badge(label, color):
        return format_html(
            '<span style="display:inline-block;padding:2px 8px;'
            'border-radius:999px;background:{};color:#fff;font-weight:600;">'
            "{}</span>",
            color,
            label,
        )
