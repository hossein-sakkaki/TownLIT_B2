# apps/core/square/projections/base.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki (original creation date not recorded in supplied source).
# Last Update by Hossein Sakkaki on 2026-11-09.

# apps/core/square/projections/base.py

from __future__ import annotations

from typing import Any, Dict

import logging

from apps.translations.services.automatic import cached_automatic_fields
from apps.translations.services.automatic_dispatch import (
    automatic_stream_request_limit,
    dispatch_missing_automatic_fields,
)

from django.contrib.auth import get_user_model

from apps.core.boundaries.services.policy import BoundaryPolicy

UserModel = get_user_model()
logger = logging.getLogger(__name__)


class SquareProjection:
    """
    Lightweight projection for Square feed items.

    IMPORTANT:
    - NO heavy serialization
    - NO media signing
    - NO playback resolving
    - Only lightweight DB fields
    - Adds owner + peace/boundary metadata for iOS/web safety.
    """

    kind: str = "unknown"

    def __init__(self, obj, *, request=None, viewer=None):
        self.obj = obj
        self.request = request
        self.viewer = viewer if getattr(viewer, "is_authenticated", False) else None
        self._peace_payload = None

    # ---------------------------------------------------------
    # Required projection hooks
    # ---------------------------------------------------------

    def get_preview(self) -> Dict[str, Any]:
        """
        Must return CDN-ready preview URLs.
        """
        raise NotImplementedError

    def get_meta(self) -> Dict[str, Any]:
        """
        Lightweight text metadata.
        """
        return {}

    # ---------------------------------------------------------
    # Owner resolution
    # ---------------------------------------------------------

    def get_owner_object(self):
        """
        Resolve the profile/content owner object.

        TownLIT content usually uses GenericForeignKey ownership:
        - content_type
        - object_id

        This method stays defensive so Square does not crash if one model
        has a different ownership shape.
        """

        content_type = getattr(self.obj, "content_type", None)
        object_id = getattr(self.obj, "object_id", None)

        if content_type and object_id:
            try:
                return content_type.get_object_for_this_type(id=object_id)
            except Exception:
                return None

        for attr in ("owner", "profile", "member", "guest", "name", "user"):
            value = getattr(self.obj, attr, None)
            if value is not None:
                return value

        return None

    def get_owner_user(self):
        """
        Resolve the actual CustomUser behind the content owner.
        """

        owner_object = self.get_owner_object()

        if owner_object is None:
            return None

        if isinstance(owner_object, UserModel):
            return owner_object

        for attr in ("user", "name", "member", "owner"):
            value = getattr(owner_object, attr, None)

            if value is None:
                continue

            if isinstance(value, UserModel):
                return value

            nested_user = getattr(value, "user", None)
            if isinstance(nested_user, UserModel):
                return nested_user

        # Some profile objects may expose user_id without loaded relation.
        user_id = getattr(owner_object, "user_id", None)
        if user_id:
            try:
                return UserModel.objects.filter(id=user_id).first()
            except Exception:
                return None

        return None

    def get_owner_payload(self) -> Dict[str, Any]:
        """
        Lightweight owner payload for frontend/iOS filtering and routing.
        """

        owner_user = self.get_owner_user()

        if not owner_user:
            return {
                "owner_user_id": None,
                "owner_username": None,
            }

        return {
            "owner_user_id": owner_user.id,
            "owner_username": getattr(owner_user, "username", None),
        }

    # ---------------------------------------------------------
    # Peace / Boundary metadata
    # ---------------------------------------------------------

    def get_peace_payload(self) -> Dict[str, Any]:
        """
        Return Stillness/Boundary state between viewer and content owner.

        Rules:
        - Anonymous viewer: no personalized peace state.
        - Own content: always available.
        - Stillness does NOT hide content.
        - Boundary blocks direct interaction and should hide Square item.
        """

        if self._peace_payload is not None:
            return self._peace_payload

        owner_user = self.get_owner_user()
        viewer = self.viewer

        if not viewer or not owner_user:
            return self._remember_peace({
                "in_stillness": False,
                "has_boundary": False,
                "has_boundary_between": False,
                "direct_interaction_available": True,
            })

        if viewer.id == owner_user.id:
            return self._remember_peace({
                "in_stillness": False,
                "has_boundary": False,
                "has_boundary_between": False,
                "direct_interaction_available": True,
            })

        try:
            in_stillness = BoundaryPolicy.is_in_stillness(
                owner=viewer,
                target=owner_user,
            )

            has_boundary = BoundaryPolicy.has_boundary(
                owner=viewer,
                target=owner_user,
            )

            has_boundary_between = BoundaryPolicy.has_boundary_between(
                viewer,
                owner_user,
            )

            return self._remember_peace({
                "in_stillness": bool(in_stillness),
                "has_boundary": bool(has_boundary),
                "has_boundary_between": bool(has_boundary_between),
                "direct_interaction_available": not bool(has_boundary_between),
            })

        except Exception:
            logger.exception("square_boundary_check_failed object_id=%s", getattr(self.obj, "pk", None))
            return self._remember_peace({
                "in_stillness": False,
                "has_boundary": True,
                "has_boundary_between": True,
                "direct_interaction_available": False,
            })

    def _remember_peace(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self._peace_payload = payload
        return payload

    def _localized_meta(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        """Read only fresh cached translations for already-authorized Square items."""
        if self.viewer is None or not isinstance(meta, dict):
            return meta

        label = getattr(getattr(self.obj, "_meta", None), "label_lower", "")
        if label == "posts.moment" or label == "posts.prayer":
            source_fields = {"caption": getattr(self.obj, "caption", None)}
        elif label == "posts.testimony" and getattr(self.obj, "type", None) == "written":
            source_fields = {
                "title": getattr(self.obj, "title", None),
                "content": getattr(self.obj, "content", None),
            }
        else:
            return meta

        if not any(value and str(value).strip() for value in source_fields.values()):
            return meta
        try:
            presentation = cached_automatic_fields(
                obj=self.obj,
                fields=source_fields,
                viewer=self.viewer,
            )
        except Exception:
            logger.exception("square_translation_cache_read_failed id=%s", getattr(self.obj, "pk", None))
            return meta

        # Square is the home entry: translation generation must not depend on
        # opening an individual Stream or tapping a client-side language menu.
        # Only metadata of an item that passed the Boundary gate reaches here.
        remaining = 2
        if self.request is not None:
            already_queued = getattr(
                self.request, "_square_translation_jobs_enqueued", 0,
            )
            remaining = max(0, automatic_stream_request_limit() - already_queued)
        if remaining:
            queued = dispatch_missing_automatic_fields(
                obj=self.obj,
                presentation=presentation,
                viewer=self.viewer,
                remaining=min(remaining, 2),
            )
            if self.request is not None:
                self.request._square_translation_jobs_enqueued = already_queued + queued

        fields = presentation.get("fields", {})
        for field_name, source in source_fields.items():
            result = fields.get(field_name)
            if not isinstance(result, dict) or result.get("status") != "ready":
                continue
            if result.get("original") != source:
                continue
            translated = result.get("translated")
            if not isinstance(translated, str) or not translated.strip():
                continue
            output_key = "localized_title" if field_name == "title" else "localized_excerpt"
            meta[output_key] = translated[:120 if field_name == "title" else 160]
        return meta

    def should_hide_for_boundary(self) -> bool:
        """
        Server-side safety gate.

        Boundary should remove this item from Square for this viewer.
        Stillness should not remove it.
        """

        peace = self.get_peace_payload()
        return bool(peace.get("has_boundary_between")) or not bool(
            peace.get("direct_interaction_available", True)
        )

    # ---------------------------------------------------------
    # Final serializer
    # ---------------------------------------------------------

    def serialize(self) -> Dict[str, Any] | None:
        """
        Final normalized payload for Square.
        """

        if self.should_hide_for_boundary():
            return None

        preview = self.get_preview()
        if not preview:
            return None

        owner_payload = self.get_owner_payload()
        peace_payload = self.get_peace_payload()

        return {
            "kind": self.kind,
            "id": self.obj.id,
            "published_at": getattr(self.obj, "published_at", None),
            "preview": preview,
            "meta": self._localized_meta(dict(self.get_meta())),

            # Owner metadata for iOS/web local safety and future routing.
            **owner_payload,

            # Peace/Boundary metadata.
            **peace_payload,
        }
