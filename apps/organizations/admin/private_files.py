# apps/organizations/admin/private_files.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-13.
# Last Update by Hossein Sakkaki on 2026-10-13.
#

from __future__ import annotations

from pathlib import PurePosixPath
from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


DEFAULT_VERIFICATION_ADMIN_URL_TTL_SECONDS = 300
MIN_VERIFICATION_ADMIN_URL_TTL_SECONDS = 60
MAX_VERIFICATION_ADMIN_URL_TTL_SECONDS = 900


def _verification_admin_url_ttl_seconds() -> int:
    raw_value = getattr(
        settings,
        "ORGANIZATION_VERIFICATION_ADMIN_URL_TTL_SECONDS",
        DEFAULT_VERIFICATION_ADMIN_URL_TTL_SECONDS,
    )

    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        value = DEFAULT_VERIFICATION_ADMIN_URL_TTL_SECONDS

    return max(
        MIN_VERIFICATION_ADMIN_URL_TTL_SECONDS,
        min(MAX_VERIFICATION_ADMIN_URL_TTL_SECONDS, value),
    )


def _safe_download_filename(storage_key: str) -> str:
    filename = PurePosixPath(storage_key).name.strip()
    filename = filename.replace("\r", "").replace("\n", "")
    filename = filename.replace('"', "'")
    return filename or "verification-document"


def _content_disposition(*, filename: str, attachment: bool) -> str:
    disposition = "attachment" if attachment else "inline"
    fallback = filename.encode("ascii", "ignore").decode("ascii").strip()
    fallback = fallback or "verification-document"
    encoded = quote(filename, safe="")

    return (
        f'{disposition}; filename="{fallback}"; '
        f"filename*=UTF-8''{encoded}"
    )


def _s3_client_from_storage(storage):
    connection = getattr(storage, "connection", None)
    meta = getattr(connection, "meta", None)
    return getattr(meta, "client", None)


def build_verification_document_url(
    field_file,
    *,
    attachment: bool = False,
    expires_in: int | None = None,
) -> str:
    """
    Build a short-lived URL for a private verification document.

    S3 is signed directly through the storage client's get_object operation.
    This intentionally bypasses storage.url() when an S3 custom domain is
    configured, because custom-domain URL generation is not guaranteed to
    preserve private-object signing semantics.

    Local/non-S3 storage falls back to the configured storage URL.
    """

    if not field_file:
        raise ValueError("Verification document has no file.")

    storage_key = str(getattr(field_file, "name", "") or "").strip()
    if not storage_key:
        raise ValueError("Verification document has no storage key.")

    storage = getattr(field_file, "storage", None)
    if storage is None:
        raise ImproperlyConfigured(
            "Verification document storage is unavailable."
        )

    s3_client = _s3_client_from_storage(storage)
    bucket_name = str(
        getattr(storage, "bucket_name", "")
        or getattr(settings, "AWS_STORAGE_BUCKET_NAME", "")
        or ""
    ).strip()

    if s3_client is not None and bucket_name:
        ttl = expires_in or _verification_admin_url_ttl_seconds()
        ttl = max(
            MIN_VERIFICATION_ADMIN_URL_TTL_SECONDS,
            min(MAX_VERIFICATION_ADMIN_URL_TTL_SECONDS, int(ttl)),
        )

        filename = _safe_download_filename(storage_key)
        params = {
            "Bucket": bucket_name,
            "Key": storage_key,
            "ResponseContentDisposition": _content_disposition(
                filename=filename,
                attachment=attachment,
            ),
        }

        return s3_client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=ttl,
            HttpMethod="GET",
        )

    return storage.url(storage_key)
