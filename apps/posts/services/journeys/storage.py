# apps/posts/services/journeys/storage.py

from __future__ import annotations

import os
import uuid

from django.conf import settings
from django.core.files.base import File
from django.core.files.storage import default_storage

from common.aws.aws_clients import s3_client


class JourneyStorageError(Exception):
    """
    Raised when immutable Journey asset promotion fails.
    """


def normalize_storage_key(value) -> str:
    return str(value or "").strip().lstrip("/")


def build_journey_asset_key(
    *,
    entry_id: int,
    kind: str,
    source_key: str,
) -> str:
    """
    Build immutable Journey storage key.
    """

    extension = (
        os.path.splitext(source_key)[1].strip().lower()
        or ".jpg"
    )

    return (
        f"posts/{kind}/journey/"
        f"{entry_id}/"
        f"{uuid.uuid4().hex}"
        f"{extension}"
    )


def _copy_with_s3(
    *,
    source_key: str,
    destination_key: str,
) -> str:
    bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "")

    if not bucket:
        raise JourneyStorageError(
            "AWS storage bucket is not configured."
        )

    s3_client.copy_object(
        Bucket=bucket,
        CopySource={
            "Bucket": bucket,
            "Key": source_key,
        },
        Key=destination_key,
        MetadataDirective="COPY",
    )

    return destination_key


def _copy_with_storage(
    *,
    source_key: str,
    destination_key: str,
) -> str:
    """
    Storage-compatible fallback.
    """

    if not default_storage.exists(source_key):
        raise JourneyStorageError(
            f"Source asset does not exist: {source_key}"
        )

    with default_storage.open(source_key, "rb") as source:
        saved_key = default_storage.save(
            destination_key,
            File(source),
        )

    return normalize_storage_key(saved_key)


def copy_storage_asset(
    *,
    source_key: str,
    destination_key: str,
) -> str:
    """
    Promote one render output into Journey storage.
    """

    source = normalize_storage_key(source_key)
    destination = normalize_storage_key(destination_key)

    if not source or not destination:
        raise JourneyStorageError(
            "Source and destination keys are required."
        )

    storage_bucket = getattr(default_storage, "bucket", None)

    if storage_bucket is not None:
        return _copy_with_s3(
            source_key=source,
            destination_key=destination,
        )

    return _copy_with_storage(
        source_key=source,
        destination_key=destination,
    )


def delete_storage_asset(key: str | None) -> None:
    """
    Best-effort asset cleanup.
    """

    normalized = normalize_storage_key(key)

    if not normalized:
        return

    try:
        if default_storage.exists(normalized):
            default_storage.delete(normalized)
    except Exception:
        return