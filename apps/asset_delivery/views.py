# apps/asset_delivery/views.py

import logging
import os
from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.asset_delivery.permissions import safe_can_view_target
from apps.asset_delivery.serializers import PlaybackURLSerializer
from apps.asset_delivery.services.target_resolver import (
    get_target_by_content_type,
    get_target_by_app_model,
    get_target_by_slug,
)
from apps.asset_delivery.services.job_resolver import get_latest_done_output_path
from apps.asset_delivery.services.playback_resolver import resolve_fallback_filefield_key
from apps.asset_delivery.services.signers.cloudfront_signer import build_signed_url
from apps.asset_delivery.services.signers.cloudfront_cookies import (
    signed_url_to_cookies,
    strip_query,
)

logger = logging.getLogger(__name__)


def _join_cdn_url(key: str) -> str:
    # Build CDN absolute URL
    base = (getattr(settings, "ASSET_CDN_BASE_URL", "") or "").rstrip("/")
    k = (key or "").lstrip("/")
    if not base:
        raise ValueError("ASSET_CDN_BASE_URL is not set.")
    return f"{base}/{k}"


def _is_hls_path(key: str) -> bool:
    # HLS manifests or playlists
    return key.endswith(".m3u8")


def _hls_dir_path_from_key(key: str) -> str:
    # Cookie Path should be the HLS directory (ends with '/')
    # Example: posts/videos/testimony/.../ -> includes master.m3u8 + variants + segments
    d = os.path.dirname(key).rstrip("/") + "/"
    return "/" + d.lstrip("/")



class AssetPlaybackViewSet(viewsets.ViewSet):
    """
    Playback gateway (video/audio/image/thumbnail).
    Backend authorizes, CDN delivers.
    """
    permission_classes = [AllowAny]

    # -------------------------------------------------------------------------------------------------------------
    def _resolve_target(self, request):
        qp = request.query_params

        if qp.get("content_type_id") and qp.get("object_id"):
            return get_target_by_content_type(int(qp["content_type_id"]), int(qp["object_id"]))

        if qp.get("app_label") and qp.get("model") and qp.get("object_id"):
            return get_target_by_app_model(
                qp["app_label"].strip(),
                qp["model"].strip(),
                int(qp["object_id"])
            )

        if qp.get("app_label") and qp.get("model") and qp.get("slug"):
            return get_target_by_slug(
                qp["app_label"].strip(),
                qp["model"].strip(),
                qp["slug"].strip()
            )

        raise ValueError(
            "Provide (content_type_id, object_id) OR (app_label, model, object_id) OR (app_label, model, slug)."
        )

    # -------------------------------------------------------------------------------------------------------------
    def _set_cloudfront_signed_cookies(
        self,
        response: Response,
        *,
        signed_url: str,
        ttl: int,
        cookie_path: str,
    ) -> None:
        """
        Set CloudFront signed cookies for HLS directory.
        """
        ck = signed_url_to_cookies(signed_url)

        # Cookies should apply to media.townlit.com too
        cookie_domain = (getattr(settings, "ASSET_CDN_COOKIE_DOMAIN", "") or ".townlit.com").strip() or ".townlit.com"

        common = dict(
            max_age=int(ttl),
            secure=True,
            httponly=True,
            samesite="Lax",        # Same-site subdomains (townlit.com <-> media.townlit.com)
            domain=cookie_domain,
            path=cookie_path,      # Critical: limit to that HLS folder
        )

        response.set_cookie("CloudFront-Policy", ck.policy, **common)
        response.set_cookie("CloudFront-Signature", ck.signature, **common)
        response.set_cookie("CloudFront-Key-Pair-Id", ck.key_pair_id, **common)

    # -------------------------------------------------------------------------------------------------------------
    def _sign_key(self, *, key: str, kind: str, field_name: str) -> dict:
        ttl = int(getattr(settings, "ASSET_CDN_DEFAULT_TTL_SECONDS", 900))

        # For HLS: sign the DIRECTORY (wildcard) not a single file
        sign_key = key
        if _is_hls_path(key):
            sign_key = os.path.dirname(key).rstrip("/") + "/*"

        resource_url = _join_cdn_url(sign_key)

        signed = build_signed_url(resource_url=resource_url, expires_in=ttl)
        expires_at = timezone.now() + timedelta(seconds=int(signed.expires_in))

        # Return clean URL for the client (no query) when using cookies
        clean_url = signed.url
        if _is_hls_path(key):
            # Replace wildcard with the actual manifest path the player will request
            # IMPORTANT: keep query in signed.url (needed only to derive cookies), but client should use clean_url
            clean_url = strip_query(_join_cdn_url(key))

        payload = {
            "url": clean_url,
            "expires_in": int(signed.expires_in),
            "expires_at": expires_at,
            "kind": kind,
            "field_name": field_name,

            # Internal: raw signed URL (query included) for cookie extraction
            "_signed_url_raw": signed.url,
            "_source_key": key,
        }

        PlaybackURLSerializer(data={k: v for k, v in payload.items() if not k.startswith("_")}).is_valid(raise_exception=True)
        return payload

    # -------------------------------------------------------------------------------------------------------------
    def _build_playback(self, *, target, kind: str, field_name: str) -> dict:
        job_kind = kind
        if kind in ("thumbnail", "image"):
            job_kind = "image"

        fields_to_try = [field_name]
        if field_name == "thumbnail":
            fields_to_try.append("image")

        for fname in fields_to_try:
            key = get_latest_done_output_path(target_obj=target, field_name=fname, kind=job_kind)
            if not key:
                key = resolve_fallback_filefield_key(target, fname)

            if key:
                return self._sign_key(key=key, kind=kind, field_name=fname)

        raise ValueError("Playback source not found (no job output_path and no file field).")

    # -------------------------------------------------------------------------------------------------------------
    def _handle_get(self, request, kind: str, default_field: str):
        field_name = (request.query_params.get("field_name") or default_field).strip()
        intent = request.query_params.get("intent", "preload")

        try:
            target = self._resolve_target(request)

            # Authz
            if not safe_can_view_target(request, target):
                return Response({"detail": "Access restricted."}, status=status.HTTP_403_FORBIDDEN)

            payload = self._build_playback(target=target, kind=kind, field_name=field_name)

            # Build response now (we may set cookies)
            resp_payload = {k: v for k, v in payload.items() if not k.startswith("_")}
            resp = Response(resp_payload, status=status.HTTP_200_OK)

            # HLS: set signed cookies so variant playlists + segments succeed
            key = payload.get("_source_key") or ""
            raw_signed_url = payload.get("_signed_url_raw") or ""

            # HLS: set signed cookies ONLY when real playback starts
            if key and _is_hls_path(key) and raw_signed_url:
                cookie_path = _hls_dir_path_from_key(key)
                ttl = int(payload["expires_in"])
                self._set_cloudfront_signed_cookies(
                    resp,
                    signed_url=raw_signed_url,
                    ttl=ttl,
                    cookie_path=cookie_path,
                )

            return resp

        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception(f"asset_delivery.playback.{kind} failed")
            return Response({"detail": "Internal error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # -------------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="video")
    def video(self, request):
        return self._handle_get(request, kind="video", default_field="video")

    # -------------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="audio")
    def audio(self, request):
        return self._handle_get(request, kind="audio", default_field="audio")

    # -------------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="image")
    def image(self, request):
        return self._handle_get(request, kind="image", default_field="image")

    # -------------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="thumbnail")
    def thumbnail(self, request):
        return self._handle_get(request, kind="thumbnail", default_field="thumbnail")

    # -------------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="file")
    def file(self, request):
        # FileField download (e.g. conversation.Message.file)
        return self._handle_get(request, kind="file", default_field="file")

    # -------------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="refresh-url")
    def refresh_url(self, request):
        """
        Refresh signed CDN URL for a key.
        NOTE: Keep behavior, but if key is HLS you still need cookies in browser.
        """
        key = (request.data.get("key") or "").strip()
        kind = (request.data.get("kind") or "video").strip()
        field_name = (request.data.get("field_name") or "key").strip()

        if not key:
            return Response({"detail": "Missing 'key'."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = self._sign_key(key=key, kind=kind, field_name=field_name)

            resp_payload = {k: v for k, v in payload.items() if not k.startswith("_")}
            resp = Response(resp_payload, status=status.HTTP_200_OK)

            raw_signed_url = payload.get("_signed_url_raw") or ""
            if _is_hls_path(key) and raw_signed_url:
                cookie_path = _hls_dir_path_from_key(key)
                ttl = int(payload["expires_in"])
                self._set_cloudfront_signed_cookies(
                    resp,
                    signed_url=raw_signed_url,
                    ttl=ttl,
                    cookie_path=cookie_path,
                )

            return resp

        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("asset_delivery.playback.refresh_url failed")
            return Response({"detail": "Internal error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
