# apps/audio_catalog/admin/rights.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-03.
# Last Update by Hossein Sakkaki on 2026-08-17.

from __future__ import annotations

from django.contrib import admin, messages
from django.utils import timezone

from apps.audio_catalog.models import (
    MusicRightsRecord,
    RightsEvidence,
    RightsParty,
)

from .shared import (
    HiddenFromAdminIndexMixin,
    LargeResultAdminMixin,
    linked_object,
    render_file_link,
    status_badge,
)


class RightsEvidenceInline(admin.StackedInline):
    model = RightsEvidence
    extra = 1
    show_change_link = True

    fields = (
        ("evidence_type", "title"),
        "evidence_file",
        "evidence_link",
        ("captured_at", "sha256"),
        "notes",
    )
    readonly_fields = ("evidence_link",)

    @admin.display(description="Document")
    def evidence_link(self, obj):
        if not obj or not obj.pk:
            return "Document will be available after saving."

        return render_file_link(
            obj.evidence_file,
            label="Open private evidence",
        )


@admin.action(description="Mark selected rights as cleared")
def mark_rights_cleared(modeladmin, request, queryset):
    now = timezone.now()

    count = queryset.update(
        status=MusicRightsRecord.Status.CLEARED,
        reviewed_by=request.user,
        reviewed_at=now,
        updated_at=now,
    )

    modeladmin.message_user(
        request,
        f"{count} rights record(s) cleared.",
        level=messages.SUCCESS,
    )


@admin.action(description="Move selected rights to review")
def mark_rights_review_required(modeladmin, request, queryset):
    count = queryset.update(
        status=MusicRightsRecord.Status.REVIEW_REQUIRED,
        reviewed_by=None,
        reviewed_at=None,
        updated_at=timezone.now(),
    )

    modeladmin.message_user(
        request,
        f"{count} rights record(s) moved to review.",
        level=messages.WARNING,
    )


@admin.action(description="Revoke selected rights")
def revoke_rights(modeladmin, request, queryset):
    now = timezone.now()

    count = queryset.update(
        status=MusicRightsRecord.Status.REVOKED,
        reviewed_by=request.user,
        reviewed_at=now,
        updated_at=now,
    )

    modeladmin.message_user(
        request,
        f"{count} rights record(s) revoked.",
        level=messages.ERROR,
    )


@admin.register(MusicRightsRecord)
class MusicRightsRecordAdmin(
    HiddenFromAdminIndexMixin,
    LargeResultAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "track_link",
        "status_display",
        "license_type",
        "provider_name",
        "territory_mode",
        "ugc_use_allowed",
        "streaming_allowed",
        "synchronization_allowed",
        "external_export_allowed",
        "effective_from",
        "effective_until",
        "reviewed_by",
    )
    list_display_links = ("status_display",)
    list_filter = (
        "status",
        "license_type",
        "territory_mode",
        "provider_name",
        "commercial_use_allowed",
        "ugc_use_allowed",
        "streaming_allowed",
        "synchronization_allowed",
        "adaptation_allowed",
        "clipping_allowed",
        "hosting_allowed",
        "sublicensing_to_end_users_allowed",
        "standalone_download_allowed",
        "external_export_allowed",
        "attribution_required",
        "effective_from",
        "effective_until",
    )
    search_fields = (
        "track__title",
        "track__slug",
        "provider_name",
        "provider_plan",
        "agreement_reference",
        "generation_reference",
        "license_version",
        "public_id",
    )
    autocomplete_fields = (
        "track",
        "master_owner",
        "composition_owner",
        "licensor",
    )
    readonly_fields = (
        "public_id",
        "reviewed_by",
        "reviewed_at",
        "created_at",
        "updated_at",
    )
    actions = (
        mark_rights_cleared,
        mark_rights_review_required,
        revoke_rights,
    )
    inlines = (RightsEvidenceInline,)
    list_select_related = (
        "track",
        "master_owner",
        "composition_owner",
        "licensor",
        "reviewed_by",
    )
    ordering = ("-updated_at", "-id")

    fieldsets = (
        (
            "Track and status",
            {
                "fields": (
                    "track",
                    ("status", "license_type"),
                    ("reviewed_by", "reviewed_at"),
                ),
            },
        ),
        (
            "Rights parties",
            {
                "fields": (
                    "master_owner",
                    "composition_owner",
                    "licensor",
                ),
            },
        ),
        (
            "Provider and agreement",
            {
                "fields": (
                    ("provider_name", "provider_plan"),
                    "provider_account_reference",
                    "generation_reference",
                    "generation_prompt_hash",
                    "agreement_reference",
                    "license_version",
                    "source_url",
                ),
            },
        ),
        (
            "Validity and territory",
            {
                "fields": (
                    ("effective_from", "effective_until"),
                    "territory_mode",
                    "territory_codes",
                ),
            },
        ),
        (
            "Usage rights",
            {
                "fields": (
                    (
                        "commercial_use_allowed",
                        "ugc_use_allowed",
                        "streaming_allowed",
                    ),
                    (
                        "synchronization_allowed",
                        "adaptation_allowed",
                        "clipping_allowed",
                    ),
                    (
                        "hosting_allowed",
                        "sublicensing_to_end_users_allowed",
                    ),
                    (
                        "standalone_download_allowed",
                        "external_export_allowed",
                    ),
                    "perpetual_existing_content_allowed",
                ),
            },
        ),
        (
            "Attribution and restrictions",
            {
                "fields": (
                    "attribution_required",
                    "attribution_text",
                    "restrictions",
                    "notes",
                ),
            },
        ),
        (
            "System",
            {
                "classes": ("collapse",),
                "fields": (
                    "public_id",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        previous_status = None

        if change and obj.pk:
            previous_status = (
                MusicRightsRecord.objects.filter(pk=obj.pk)
                .values_list("status", flat=True)
                .first()
            )

        status_changed = not change or previous_status != obj.status

        if status_changed:
            if obj.status in {
                MusicRightsRecord.Status.CLEARED,
                MusicRightsRecord.Status.RESTRICTED,
                MusicRightsRecord.Status.EXPIRED,
                MusicRightsRecord.Status.REVOKED,
            }:
                obj.reviewed_by = request.user
                obj.reviewed_at = timezone.now()

            elif obj.status in {
                MusicRightsRecord.Status.DRAFT,
                MusicRightsRecord.Status.REVIEW_REQUIRED,
            }:
                obj.reviewed_by = None
                obj.reviewed_at = None

        super().save_model(request, obj, form, change)

    @admin.display(description="Track", ordering="track__title")
    def track_link(self, obj):
        return linked_object(obj.track)

    @admin.display(description="Status", ordering="status")
    def status_display(self, obj):
        color_map = {
            MusicRightsRecord.Status.DRAFT: "#666666",
            MusicRightsRecord.Status.REVIEW_REQUIRED: "#5c6ac4",
            MusicRightsRecord.Status.CLEARED: "#18864b",
            MusicRightsRecord.Status.RESTRICTED: "#c57a00",
            MusicRightsRecord.Status.EXPIRED: "#8b8b8b",
            MusicRightsRecord.Status.REVOKED: "#c0392b",
        }

        return status_badge(
            obj.get_status_display(),
            background=color_map.get(obj.status, "#666666"),
        )


@admin.register(RightsEvidence)
class RightsEvidenceAdmin(
    HiddenFromAdminIndexMixin,
    LargeResultAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "title",
        "rights_record_link",
        "evidence_type",
        "document_link",
        "captured_at",
        "created_at",
    )
    list_filter = (
        "evidence_type",
        "captured_at",
        "created_at",
    )
    search_fields = (
        "title",
        "rights_record__track__title",
        "rights_record__track__slug",
        "sha256",
        "public_id",
    )
    autocomplete_fields = ("rights_record",)
    readonly_fields = (
        "public_id",
        "document_link",
        "created_at",
        "updated_at",
    )
    list_select_related = (
        "rights_record",
        "rights_record__track",
    )

    @admin.display(description="Rights record")
    def rights_record_link(self, obj):
        return linked_object(obj.rights_record)

    @admin.display(description="Document")
    def document_link(self, obj):
        return render_file_link(
            obj.evidence_file,
            label="Open evidence",
        )


@admin.register(RightsParty)
class RightsPartyAdmin(
    LargeResultAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "display_name",
        "legal_name",
        "kind",
        "country_code",
        "contact_email",
        "website_url",
    )
    list_filter = ("kind", "country_code")
    search_fields = (
        "display_name",
        "legal_name",
        "contact_email",
        "external_reference",
        "public_id",
    )
    readonly_fields = (
        "public_id",
        "created_at",
        "updated_at",
    )
    ordering = ("display_name", "id")

    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "display_name",
                    "legal_name",
                    "kind",
                    "country_code",
                ),
            },
        ),
        (
            "Contact and references",
            {
                "fields": (
                    "website_url",
                    "contact_email",
                    "external_reference",
                ),
            },
        ),
        (
            "Metadata",
            {
                "classes": ("collapse",),
                "fields": ("metadata",),
            },
        ),
        (
            "System",
            {
                "classes": ("collapse",),
                "fields": (
                    "public_id",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )