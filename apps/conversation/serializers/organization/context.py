# apps/conversation/serializers/organization/context.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-16.
#

from __future__ import annotations

from apps.asset_delivery.utils.cdn_urls import build_cdn_url
from apps.conversation.constants import OrganizationConversationContextType
from apps.conversation.policies import ConversationContextPolicy
from apps.organizations.selectors.ownership import (
    effective_organization_manager_user_ids,
)


def _field_url(field, *, request=None):
    if not field:
        return None

    try:
        url = field.url
    except Exception:
        return None

    if request:
        return request.build_absolute_uri(url)
    return url


def _field_cdn_url(field):
    if not field:
        return None

    key = str(getattr(field, "name", "") or "").strip()
    if not key:
        return None
    return build_cdn_url(key)


def organization_identity_payload(organization, *, request=None):
    logo = getattr(organization, "logo", None)
    thumbnail = getattr(organization, "thumbnail", None)
    avatar_field = logo or thumbnail
    updated_at = getattr(organization, "updated_at", None)

    return {
        "id": organization.id,
        "public_id": str(organization.public_id),
        "slug": organization.slug,
        "name": organization.name,
        "short_name": organization.short_name,
        "brand_color": organization.brand_color,
        "logo_url": _field_url(logo, request=request),
        "thumbnail_url": _field_url(thumbnail, request=request),
        "avatar_url": _field_url(avatar_field, request=request),
        "avatar_cdn_url": _field_cdn_url(avatar_field),
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


def _members_community_manager_user_ids(organization_context):
    if (
        organization_context.context_type
        != OrganizationConversationContextType.MEMBERS_COMMUNITY
    ):
        return None

    organization = organization_context.organization
    prefetched_memberships = getattr(
        organization,
        "_conversation_manager_memberships",
        None,
    )

    if prefetched_memberships is not None:
        return sorted({
            int(membership.member.user_id)
            for membership in prefetched_memberships
            if membership.member_id
        })

    return sorted(
        effective_organization_manager_user_ids(
            organization=organization,
        )
    )


def organization_conversation_context_payload(dialogue, *, request=None):
    resolved = ConversationContextPolicy.resolve(dialogue)
    if not resolved.is_organization:
        return None

    organization_context = resolved.organization_context
    payload = {
        "type": organization_context.context_type,
        "status": organization_context.status,
        "waiting_for": organization_context.waiting_for,
        "organization": organization_identity_payload(
            organization_context.organization,
            request=request,
        ),
    }

    manager_user_ids = _members_community_manager_user_ids(
        organization_context
    )
    if manager_user_ids is not None:
        payload["manager_user_ids"] = manager_user_ids

    return payload
