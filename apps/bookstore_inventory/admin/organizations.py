# apps/bookstore_inventory/admin/organizations.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django.contrib import admin
from django.utils import timezone
from django.db.models import Count

from apps.bookstore_inventory.admin.common import (
    HiddenFromAdminIndexMixin, WorkflowAdminMixin, badge,
)
from apps.bookstore_inventory.models import (
    OrganizationAlias, OrganizationProfileLink, OrganizationRecord, OrganizationRole,
)


class OrganizationAliasInline(admin.TabularInline):
    model = OrganizationAlias
    extra = 1
    fields = ("name", "is_primary")


class OrganizationRoleInline(admin.TabularInline):
    model = OrganizationRole
    extra = 1
    fields = ("role", "is_active", "notes")


class OrganizationProfileLinkInline(admin.TabularInline):
    model = OrganizationProfileLink
    extra = 1
    fields = ("content_type", "object_id", "status", "verified_at", "verified_by", "evidence")
    readonly_fields = ("verified_at", "verified_by")


@admin.register(OrganizationRecord)
class OrganizationRecordAdmin(HiddenFromAdminIndexMixin, WorkflowAdminMixin, admin.ModelAdmin):
    list_display = (
        "display_label", "country", "role_summary", "verification_badge",
        "book_count", "shipment_count", "is_active",
    )
    list_display_links = ("display_label",)
    list_filter = ("is_verified", "is_active", "country", "roles__role")
    search_fields = (
        "official_name", "display_name", "normalized_name", "aliases__name",
        "registration_number", "website", "email", "phone",
    )
    readonly_fields = ("public_id", "normalized_name", "merged_into", "usage_summary", "created_at", "updated_at")
    inlines = (OrganizationRoleInline, OrganizationAliasInline)
    fieldsets = (
        ("Identity", {"fields": ("public_id", ("official_name", "display_name"), "normalized_name", ("is_verified", "is_active"), "merged_into")}),
        ("Contact", {"fields": (("website", "email", "phone"), ("address_line_1", "address_line_2"), ("city", "province_state"), ("postal_code", "country"))}),
        ("Legal identifiers", {"fields": (("registration_number", "tax_identifier"),), "classes": ("collapse",)}),
        ("Usage", {"fields": ("usage_summary",)}),
        ("Notes and audit", {"fields": ("notes", ("created_at", "updated_at")), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _book_count=Count("published_books", distinct=True),
            _shipment_count=Count("supplied_shipments", distinct=True),
        ).prefetch_related("roles")

    @admin.display(description="Organization", ordering="display_name")
    def display_label(self, obj):
        return str(obj)

    @admin.display(description="Roles")
    def role_summary(self, obj):
        return ", ".join(role.get_role_display() for role in obj.roles.all() if role.is_active) or "—"

    @admin.display(description="Verified", ordering="is_verified")
    def verification_badge(self, obj):
        return badge("Verified" if obj.is_verified else "Internal only", "success" if obj.is_verified else "neutral")

    @admin.display(description="Books", ordering="_book_count")
    def book_count(self, obj):
        return obj._book_count

    @admin.display(description="Inbound", ordering="_shipment_count")
    def shipment_count(self, obj):
        return obj._shipment_count

    @admin.display(description="Directory usage")
    def usage_summary(self, obj):
        if not obj:
            return "Save the organization to see usage."
        return (
            f"Books published: {obj.published_books.count()} | "
            f"Editions published: {obj.published_editions.count()} | "
            f"Editions printed: {obj.printed_editions.count()} | "
            f"Shipments supplied: {obj.supplied_shipments.count()} | "
            f"Shipments donated: {obj.donated_shipments.count()} | "
            f"Orders received: {obj.book_orders_received.count()}"
        )


@admin.register(OrganizationProfileLink)
class OrganizationProfileLinkAdmin(HiddenFromAdminIndexMixin, WorkflowAdminMixin, admin.ModelAdmin):
    list_display = ("organization", "content_type", "object_id", "status", "verified_at", "verified_by")
    list_filter = ("status", "content_type")
    search_fields = ("organization__official_name", "organization__aliases__name", "=object_id", "evidence")
    autocomplete_fields = ("organization", "verified_by", "requested_by")

    def has_add_permission(self, request):
        # Links must eventually be created through a verified claim workflow.
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        if obj.status == "verified":
            obj.verified_by = request.user
            obj.verified_at = obj.verified_at or timezone.now()
        elif obj.status in {"pending", "rejected", "unlinked"}:
            obj.verified_by = None
            obj.verified_at = None
        super().save_model(request, obj, form, change)
