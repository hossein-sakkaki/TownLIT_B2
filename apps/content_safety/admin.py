# apps/content_safety/admin.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-13.
# Last Update by Hossein Sakkaki on 2026-08-13.

from django.contrib import admin

from apps.content_safety.models import (
    ContentSafetyAdjudicationCache,
    ContentSafetyAnalysisCache,
    ContentSafetyEvent,
)


@admin.register(
    ContentSafetyAnalysisCache
)
class ContentSafetyAnalysisCacheAdmin(
    admin.ModelAdmin
):
    list_display = (
        "id",
        "input_type",
        "provider",
        "provider_model",
        "flagged",
        "created_at",
        "expires_at",
    )

    list_filter = (
        "input_type",
        "provider",
        "provider_model",
        "flagged",
    )

    search_fields = (
        "input_hash",
        "provider_response_id",
    )

    readonly_fields = (
        "created_at",
        "last_accessed_at",
    )


@admin.register(
    ContentSafetyEvent
)
class ContentSafetyEventAdmin(
    admin.ModelAdmin
):
    list_display = (
        "id",
        "context",
        "decision",
        "risk_level",
        "reason_code",
        "actor",
        "adjudicated",
        "created_at",
    )

    list_filter = (
        "context",
        "decision",
        "risk_level",
        "adjudicated",
    )

    search_fields = (
        "input_hash",
        "reason_code",
        "actor__username",
    )

    readonly_fields = (
        "created_at",
    )
    

@admin.register(
    ContentSafetyAdjudicationCache
)
class ContentSafetyAdjudicationCacheAdmin(
    admin.ModelAdmin
):
    list_display = (
        "id",
        "context",
        "decision",
        "risk_level",
        "reason_code",
        "model",
        "policy_version",
        "created_at",
        "expires_at",
    )

    list_filter = (
        "context",
        "decision",
        "risk_level",
        "model",
        "policy_version",
    )

    search_fields = (
        "input_hash",
        "signal_hash",
        "reason_code",
    )

    readonly_fields = (
        "created_at",
        "last_accessed_at",
    )