# apps/organizations/admin/profile.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-27.
# Last Update by Hossein Sakkaki on 2026-09-27.
#

from django.contrib import admin

from apps.organizations.models import (
    OrganizationBusinessHour,
    OrganizationContactPoint,
    OrganizationRepresentative,
)


@admin.register(
    OrganizationContactPoint
)
class OrganizationContactPointAdmin(
    admin.ModelAdmin
):
    list_display = (
        "organization",
        "channel",
        "label",
        "is_primary",
        "is_public",
        "sort_order",
    )

    list_filter = (
        "channel",
        "is_primary",
        "is_public",
    )

    search_fields = (
        "organization__name",
        "label",
        "value",
    )


@admin.register(
    OrganizationBusinessHour
)
class OrganizationBusinessHourAdmin(
    admin.ModelAdmin
):
    list_display = (
        "organization",
        "weekday",
        "opens_at",
        "closes_at",
        "is_closed",
        "is_24_hours",
        "sort_order",
    )

    list_filter = (
        "weekday",
        "is_closed",
        "is_24_hours",
    )

    search_fields = (
        "organization__name",
    )


@admin.register(
    OrganizationRepresentative
)
class OrganizationRepresentativeAdmin(
    admin.ModelAdmin
):
    list_display = (
        "organization",
        "membership",
        "role_title",
        "status",
        "is_primary",
        "sort_order",
    )

    list_filter = (
        "status",
        "is_primary",
    )

    search_fields = (
        "organization__name",
        "membership__member__user__username",
        "membership__member__user__name",
        "membership__member__user__family",
        "role_title",
    )

    readonly_fields = (
        "public_id",
        "created_at",
        "updated_at",
    )