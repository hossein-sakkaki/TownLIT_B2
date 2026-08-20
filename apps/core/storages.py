# apps/core/storages.py
#
# TownLIT
#
# Last Update by Hossein Sakkaki on 2026-08-20.

from __future__ import annotations

from urllib.parse import quote

from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class PrivateMediaStorage(S3Boto3Storage):
    """
    Default private storage for application media.

    Objects remain private in S3 and are delivered through
    TownLIT's protected media-delivery architecture.
    """

    default_acl = None
    querystring_auth = True


class PublicEmailStorage(S3Boto3Storage):
    """
    Permanent public media embedded in email HTML.

    S3 objects are stored under:
        public/emails/...

    The S3 bucket itself remains private.

    Public delivery happens through the dedicated unsigned
    CloudFront behavior for:
        public/emails/*

    Final URLs therefore use:
        https://media.townlit.com/public/emails/...
    """

    location = "public/emails"

    default_acl = None
    querystring_auth = False
    file_overwrite = False

    def get_object_parameters(self, name):
        return {
            "CacheControl": (
                "public, max-age=31536000, immutable"
            ),
        }

    def url(
        self,
        name,
        parameters=None,
        expire=None,
        http_method=None,
    ):
        cdn_base_url = (
            getattr(
                settings,
                "ASSET_CDN_BASE_URL",
                "",
            )
            .strip()
            .rstrip("/")
        )

        if not cdn_base_url:
            return super().url(
                name,
                parameters=parameters,
                expire=expire,
                http_method=http_method,
            )

        object_key = self._normalize_name(
            name
        )

        encoded_key = quote(
            object_key,
            safe="/~",
        )

        return (
            f"{cdn_base_url}/"
            f"{encoded_key}"
        )