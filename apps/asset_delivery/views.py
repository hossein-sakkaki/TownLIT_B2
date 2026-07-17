# apps/asset_delivery/views.py

import logging
import os
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.asset_delivery.constants import PlaybackAuthMode, PlaybackIntent
from apps.asset_delivery.permissions import safe_can_view_target
from apps.asset_delivery.serializers import (
    PlaybackBatchRequestSerializer,
    PlaybackBatchResponseSerializer,
    PlaybackURLSerializer,
)
from apps.asset_delivery.services.job_resolver import get_latest_done_output_path
from apps.asset_delivery.services.playback_resolver import resolve_fallback_filefield_key
from apps.asset_delivery.services.request_parser import parse_target_lookup
from apps.asset_delivery.services.signers.cloudfront_cookies import (
    signed_url_to_cookies,
    strip_query,
)
from apps.asset_delivery.services.signers.cloudfront_signer import build_signed_url
from apps.asset_delivery.services.target_resolver import (
    get_target_by_app_model,
    get_target_by_content_type,
    get_target_by_slug,
)
from apps.asset_delivery.services.field_aliases import resolve_field_alias

logger = logging.getLogger(__name__)


def _join_cdn_url(key: str) -> str:
    """Build CDN absolute URL."""
    base = (getattr(settings, "ASSET_CDN_BASE_URL", "") or "").rstrip("/")
    k = (key or "").lstrip("/")
    if not base:
        raise ValueError("ASSET_CDN_BASE_URL is not set.")
    return f"{base}/{k}"


def _is_hls_path(key: str) -> bool:
    """Check if key points to HLS."""
    return key.endswith(".m3u8")


def _hls_cookie_scope_from_key(key: str) -> str:
    """
    Use broad scope for HLS assets.
    """

    parts = key.strip("/").split("/")

    if len(parts) >= 2 and parts[0] == "posts" and parts[1] == "videos":
        return "/posts/videos/"

    return "/"


def _cookie_scope_from_key(key: str) -> str:
    """
    Scope cookies to parent directory.
    """

    k = (key or "").strip("/")
    if not k:
        return "/"

    parent = os.path.dirname(k).strip("/")
    if not parent:
        return "/"

    return f"/{parent}/"


class AssetPlaybackViewSet(viewsets.ViewSet):
    """
    Playback gateway.
    Backend authorizes, CDN delivers.
    """

    permission_classes = [AllowAny]

    def _resolve_target(self, raw_data):
        """
        Resolve target from request data.
        """

        lookup = parse_target_lookup(raw_data)

        if lookup["mode"] == "content_type":
            return get_target_by_content_type(
                lookup["content_type_id"],
                lookup["object_id"],
            )

        if lookup["mode"] == "app_model_object":
            return get_target_by_app_model(
                lookup["app_label"],
                lookup["model"],
                lookup["object_id"],
            )

        if lookup["mode"] == "app_model_slug":
            return get_target_by_slug(
                lookup["app_label"],
                lookup["model"],
                lookup["slug"],
            )

        raise ValueError("Invalid target lookup mode.")

    def _validate_intent(self, raw_intent: str) -> str:
        """
        Validate playback intent.
        """

        intent = (raw_intent or PlaybackIntent.PRELOAD).strip().lower()

        if intent not in PlaybackIntent.ALL:
            raise ValueError(
                f"Invalid intent '{intent}'. "
                f"Allowed: {sorted(PlaybackIntent.ALL)}"
            )

        return intent

    def _set_cloudfront_signed_cookies(
        self,
        response: Response,
        *,
        signed_url: str,
        ttl: int,
        cookie_path: str,
    ) -> None:
        """
        Set CloudFront signed cookies.
        """

        ck = signed_url_to_cookies(signed_url)

        cookie_domain = (
            getattr(settings, "ASSET_CDN_COOKIE_DOMAIN", "") or ".townlit.com"
        ).strip() or ".townlit.com"

        secure = bool(getattr(settings, "ASSET_CDN_COOKIE_SECURE", True))

        common = dict(
            max_age=int(ttl),
            secure=secure,
            httponly=True,
            samesite="Lax",
            domain=cookie_domain,
            path=cookie_path,
        )

        response.set_cookie("CloudFront-Policy", ck.policy, **common)
        response.set_cookie("CloudFront-Signature", ck.signature, **common)
        response.set_cookie("CloudFront-Key-Pair-Id", ck.key_pair_id, **common)

    def _build_meta(self, *, key: str, intent: str) -> dict:
        """
        Build lightweight metadata.
        """

        return {
            "is_hls": _is_hls_path(key),
            "cookie_scope": _hls_cookie_scope_from_key(key) if _is_hls_path(key) else _cookie_scope_from_key(key),
            "intent": intent,
        }

    def _sign_key(self, *, key: str, kind: str, field_name: str, intent: str) -> dict:
        """
        Sign a storage key for delivery.
        """

        ttl = int(getattr(settings, "ASSET_CDN_DEFAULT_TTL_SECONDS", 900))

        sign_key = key
        if _is_hls_path(key):
            sign_key = os.path.dirname(key).rstrip("/") + "/*"

        resource_url = _join_cdn_url(sign_key)
        signed = build_signed_url(resource_url=resource_url, expires_in=ttl)
        expires_at = timezone.now() + timedelta(seconds=int(signed.expires_in))

        clean_url = signed.url
        if _is_hls_path(key):
            clean_url = strip_query(_join_cdn_url(key))

        payload = {
            "url": clean_url,
            "expires_in": int(signed.expires_in),
            "expires_at": expires_at,
            "kind": kind,
            "field_name": field_name,
            "auth_mode": PlaybackAuthMode.COOKIE,
            "refreshable": True,
            "cache_key": key,
            "intent": intent,
            "meta": self._build_meta(key=key, intent=intent),

            # Internal fields
            "_signed_url_raw": signed.url,
            "_source_key": key,
        }

        PlaybackURLSerializer(
            data={k: v for k, v in payload.items() if not k.startswith("_")}
        ).is_valid(raise_exception=True)

        return payload

    def _resolve_playback_key(
        self,
        *,
        target,
        field_name: str,
        job_kind: str,
    ) -> str | None:
        """
        Resolve the current storage key.

        Audio artwork is updated synchronously and does not create a new
        conversion job, so its current FileField must be preferred.
        """
        if field_name == "audio_artwork":
            current_key = resolve_fallback_filefield_key(
                target,
                field_name,
            )

            if current_key:
                return current_key

        job_key = get_latest_done_output_path(
            target_obj=target,
            field_name=field_name,
            kind=job_kind,
        )

        if job_key:
            return job_key

        return resolve_fallback_filefield_key(
            target,
            field_name,
        )

    def _build_playback(
        self,
        *,
        target,
        kind: str,
        field_name: str,
        intent: str,
    ) -> dict:
        """
        Resolve the asset key and sign it.
        """
        job_kind = "image" if kind in ("thumbnail", "image") else kind

        fields_to_try = [field_name]

        if field_name == "thumbnail":
            fields_to_try.append("image")

        for fname in fields_to_try:
            key = self._resolve_playback_key(
                target=target,
                field_name=fname,
                job_kind=job_kind,
            )

            if key:
                return self._sign_key(
                    key=key,
                    kind=kind,
                    field_name=fname,
                    intent=intent,
                )

        raise ValueError("Playback source not found.")

    def _should_set_cookies(self, *, key: str, intent: str) -> bool:
        """
        Decide if response should set cookies.
        """

        if _is_hls_path(key):
            return True

        return intent in {
            PlaybackIntent.PRELOAD,
            PlaybackIntent.VIEW,
            PlaybackIntent.RENDER,
            PlaybackIntent.FEED,
            PlaybackIntent.DETAIL,
        }

    def _public_payload(self, payload: dict) -> dict:
        """
        Remove internal signing fields before returning response.
        """

        return {
            k: v
            for k, v in payload.items()
            if not k.startswith("_")
        }

    def _normalize_batch_item_data(self, item: dict) -> dict:
        """
        Normalize nested batch item target into the flat shape used by
        parse_target_lookup().
        """

        raw = dict(item or {})
        target = raw.pop("target", None)

        if isinstance(target, dict):
            target_type = (target.get("type") or "").strip().lower()

            if target_type in {"object", "app_model_object"}:
                raw["app_label"] = target.get("app_label")
                raw["model"] = target.get("model")
                raw["object_id"] = target.get("object_id")

            elif target_type in {"slug", "app_model_slug"}:
                raw["app_label"] = target.get("app_label")
                raw["model"] = target.get("model")
                raw["slug"] = target.get("slug")

            elif target_type in {"content_type", "content_type_object"}:
                raw["content_type_id"] = target.get("content_type_id")
                raw["object_id"] = target.get("object_id")

            else:
                # Also allow clients to omit type and send direct target fields.
                for key in (
                    "app_label",
                    "model",
                    "object_id",
                    "slug",
                    "content_type_id",
                ):
                    if key in target and key not in raw:
                        raw[key] = target.get(key)

        return raw

    def _build_batch_item_payload(self, *, request, index: int, item: dict) -> dict:
        """
        Resolve one batch item.

        Returns an internal result dict. Internal asset fields are stripped later.
        """

        raw = self._normalize_batch_item_data(item)

        field_name = (raw.get("field_name") or "").strip()
        kind = (raw.get("kind") or "").strip().lower()
        intent = self._validate_intent(raw.get("intent"))

        raw_app_label = raw.get("app_label")
        raw_model = raw.get("model")
        field_name = resolve_field_alias(raw_app_label, raw_model, field_name)

        if not field_name:
            raise ValueError("Missing 'field_name'.")

        if kind not in {"video", "audio", "image", "thumbnail", "file"}:
            raise ValueError("Invalid 'kind'.")

        target = self._resolve_target(raw)

        if not safe_can_view_target(request, target):
            return {
                "index": index,
                "ok": False,
                "error": "Access restricted.",
                "status_code": status.HTTP_403_FORBIDDEN,
            }

        payload = self._build_playback(
            target=target,
            kind=kind,
            field_name=field_name,
            intent=intent,
        )

        return {
            "index": index,
            "ok": True,
            "_payload": payload,
        }

    def _is_batch_hls_result(self, result: dict) -> bool:
        """
        Check if a successful internal batch result is HLS.
        """

        if not result.get("ok"):
            return False

        payload = result.get("_payload") or {}
        key = payload.get("_source_key") or ""

        return bool(key and _is_hls_path(key))

    def _make_public_batch_result(
        self,
        result: dict,
        *,
        hls_cookie_enabled: bool,
    ) -> dict:
        """
        Convert one internal batch result into public response shape.

        Non-HLS batch assets use signed_url mode because one HTTP response
        cannot safely set many different CloudFront cookie policies with the
        same cookie names.

        HLS requires cookies because the playlist and segments need a wildcard
        cookie policy. We only enable it when there is one HLS item in the batch.
        """

        if not result.get("ok"):
            return {
                "index": result.get("index", 0),
                "ok": False,
                "error": result.get("error") or "Playback item failed.",
                "status_code": int(
                    result.get("status_code") or status.HTTP_400_BAD_REQUEST
                ),
            }

        payload = dict(result.get("_payload") or {})
        key = payload.get("_source_key") or ""
        is_hls = bool(key and _is_hls_path(key))

        if is_hls and not hls_cookie_enabled:
            return {
                "index": result.get("index", 0),
                "ok": False,
                "error": "Multiple HLS cookie-scoped assets are not supported in one batch. Resolve this item individually.",
                "status_code": status.HTTP_409_CONFLICT,
            }

        public_payload = self._public_payload(payload)

        if not is_hls:
            # Non-HLS payloads already include signed query params in the URL.
            # Returning signed_url avoids depending on response-level cookies.
            public_payload["auth_mode"] = getattr(
                PlaybackAuthMode,
                "SIGNED_URL",
                "signed_url",
            )

        return {
            "index": result.get("index", 0),
            "ok": True,
            "asset": public_payload,
        }
        
    def _handle_get(self, request, kind: str, default_field: str):
        """
        Handle playback GET requests.
        """

        field_name = (request.query_params.get("field_name") or default_field).strip()
        intent = self._validate_intent(request.query_params.get("intent"))

        raw_app_label = request.query_params.get("app_label")
        raw_model = request.query_params.get("model")
        field_name = resolve_field_alias(raw_app_label, raw_model, field_name)

        try:
            target = self._resolve_target(request.query_params)

            if not safe_can_view_target(request, target):
                return Response(
                    {"detail": "Access restricted."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            payload = self._build_playback(
                target=target,
                kind=kind,
                field_name=field_name,
                intent=intent,
            )

            resp_payload = {k: v for k, v in payload.items() if not k.startswith("_")}
            resp = Response(resp_payload, status=status.HTTP_200_OK)

            key = payload.get("_source_key") or ""
            raw_signed_url = payload.get("_signed_url_raw") or ""

            if key and raw_signed_url and self._should_set_cookies(key=key, intent=intent):
                cookie_path = (
                    _hls_cookie_scope_from_key(key)
                    if _is_hls_path(key)
                    else _cookie_scope_from_key(key)
                )

                ttl = int(payload["expires_in"])
                self._set_cloudfront_signed_cookies(
                    resp,
                    signed_url=raw_signed_url,
                    ttl=ttl,
                    cookie_path=cookie_path,
                )

            return resp

        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception("asset_delivery.playback.get failed")
            return Response(
                {"detail": "Internal error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="video")
    def video(self, request):
        return self._handle_get(request, kind="video", default_field="video")

    @action(detail=False, methods=["get"], url_path="audio")
    def audio(self, request):
        return self._handle_get(request, kind="audio", default_field="audio")

    @action(detail=False, methods=["get"], url_path="image")
    def image(self, request):
        return self._handle_get(request, kind="image", default_field="image")

    @action(detail=False, methods=["get"], url_path="thumbnail")
    def thumbnail(self, request):
        return self._handle_get(request, kind="thumbnail", default_field="thumbnail")

    @action(detail=False, methods=["get"], url_path="file")
    def file(self, request):
        return self._handle_get(request, kind="file", default_field="file")

    @action(detail=False, methods=["post"], url_path="refresh")
    def refresh(self, request):
        """
        Refresh playback using target lookup.
        """

        field_name = (request.data.get("field_name") or "").strip()
        kind = (request.data.get("kind") or "").strip().lower()
        intent = self._validate_intent(request.data.get("intent"))

        raw_app_label = request.data.get("app_label")
        raw_model = request.data.get("model")
        field_name = resolve_field_alias(raw_app_label, raw_model, field_name)

        if not field_name:
            return Response(
                {"detail": "Missing 'field_name'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if kind not in {"video", "audio", "image", "thumbnail", "file"}:
            return Response(
                {"detail": "Invalid 'kind'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            target = self._resolve_target(request.data)

            if not safe_can_view_target(request, target):
                return Response(
                    {"detail": "Access restricted."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            payload = self._build_playback(
                target=target,
                kind=kind,
                field_name=field_name,
                intent=intent,
            )

            resp_payload = {k: v for k, v in payload.items() if not k.startswith("_")}
            resp = Response(resp_payload, status=status.HTTP_200_OK)

            key = payload.get("_source_key") or ""
            raw_signed_url = payload.get("_signed_url_raw") or ""

            if key and raw_signed_url and self._should_set_cookies(key=key, intent=intent):
                cookie_path = (
                    _hls_cookie_scope_from_key(key)
                    if _is_hls_path(key)
                    else _cookie_scope_from_key(key)
                )

                ttl = int(payload["expires_in"])
                self._set_cloudfront_signed_cookies(
                    resp,
                    signed_url=raw_signed_url,
                    ttl=ttl,
                    cookie_path=cookie_path,
                )

            return resp

        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception("asset_delivery.playback.refresh failed")
            return Response(
                {"detail": "Internal error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"], url_path="batch")
    def batch(self, request):
        """
        Resolve multiple playback assets in one request.

        Important cookie rule:
        - Non-HLS assets are returned as signed URLs.
        - One HLS asset can be returned with response-level CloudFront cookies.
        - Multiple HLS assets in one batch are rejected per item so clients can
          fall back to individual resolve calls.
        """

        serializer = PlaybackBatchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        items = serializer.validated_data["items"]

        internal_results = []

        for index, item in enumerate(items):
            try:
                internal_results.append(
                    self._build_batch_item_payload(
                        request=request,
                        index=index,
                        item=item,
                    )
                )
            except ValueError as e:
                internal_results.append(
                    {
                        "index": index,
                        "ok": False,
                        "error": str(e),
                        "status_code": status.HTTP_400_BAD_REQUEST,
                    }
                )
            except Exception:
                logger.exception(
                    "asset_delivery.playback.batch item failed",
                    extra={
                        "batch_index": index,
                    },
                )
                internal_results.append(
                    {
                        "index": index,
                        "ok": False,
                        "error": "Internal error.",
                        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    }
                )

        hls_results = [
            result
            for result in internal_results
            if self._is_batch_hls_result(result)
        ]

        hls_cookie_enabled = len(hls_results) == 1

        public_results = [
            self._make_public_batch_result(
                result,
                hls_cookie_enabled=hls_cookie_enabled,
            )
            for result in internal_results
        ]

        response_payload = {
            "results": public_results,
        }

        response_serializer = PlaybackBatchResponseSerializer(
            data=response_payload
        )
        response_serializer.is_valid(raise_exception=True)

        resp = Response(
            response_serializer.validated_data,
            status=status.HTTP_200_OK,
        )

        if hls_cookie_enabled:
            payload = hls_results[0].get("_payload") or {}
            key = payload.get("_source_key") or ""
            raw_signed_url = payload.get("_signed_url_raw") or ""

            if key and raw_signed_url:
                ttl = int(payload["expires_in"])
                cookie_path = _hls_cookie_scope_from_key(key)

                self._set_cloudfront_signed_cookies(
                    resp,
                    signed_url=raw_signed_url,
                    ttl=ttl,
                    cookie_path=cookie_path,
                )

        return resp