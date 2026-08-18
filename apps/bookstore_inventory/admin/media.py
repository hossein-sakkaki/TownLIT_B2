# apps/bookstore_inventory/admin/media.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from __future__ import annotations

import logging

from django.utils.html import format_html
from django.utils.safestring import SafeString


logger = logging.getLogger(__name__)

ADMIN_PRIVATE_URL_EXPIRES_SECONDS = 15 * 60


def _storage_name(field_file) -> str:
    return (getattr(field_file, "name", "") or "").strip()


def _generate_storage_presigned_url(*, storage, name: str, expires: int) -> str:
    bucket_name = (getattr(storage, "bucket_name", "") or "").strip()
    if not bucket_name:
        bucket_name = (getattr(getattr(storage, "bucket", None), "name", "") or "").strip()
    if not bucket_name:
        return ""

    try:
        client = getattr(
            getattr(getattr(storage, "connection", None), "meta", None),
            "client",
            None,
        )
        if client is None:
            return ""
        return client.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": bucket_name,
                "Key": name,
                "ResponseContentDisposition": "inline",
            },
            ExpiresIn=max(60, int(expires)),
        )
    except Exception:
        logger.exception(
            "bookstore_inventory.admin_private_media_url.failed",
            extra={"storage_name": name, "bucket_name": bucket_name},
        )
        return ""


def _generate_native_storage_url(*, storage, name: str, expires: int) -> str:
    attempts = (
        {"parameters": {"ResponseContentDisposition": "inline"}, "expire": expires},
        {"expire": expires},
        {},
    )
    for kwargs in attempts:
        try:
            url = storage.url(name, **kwargs)
        except TypeError:
            continue
        except Exception:
            logger.exception(
                "bookstore_inventory.admin_native_media_url.failed",
                extra={"storage_name": name},
            )
            return ""
        if url:
            return str(url)
    return ""


def admin_private_file_url(
    field_file,
    *,
    expires: int = ADMIN_PRIVATE_URL_EXPIRES_SECONDS,
) -> str:
    if not field_file:
        return ""

    name = _storage_name(field_file)
    storage = getattr(field_file, "storage", None)
    if not name or storage is None:
        return ""

    # Do not call storage.exists() here. A changelist can contain many covers,
    # and one remote HEAD request per row would make Django Admin unnecessarily slow.
    return _generate_storage_presigned_url(
        storage=storage,
        name=name,
        expires=expires,
    ) or _generate_native_storage_url(
        storage=storage,
        name=name,
        expires=expires,
    )


def admin_image_preview(
    *,
    image_field,
    width: int,
    height: int,
    border_radius: int = 8,
    background: str = "#f8fafc",
    object_fit: str = "contain",
    alt: str = "Book cover preview",
) -> SafeString | str:
    if not image_field:
        return "—"

    image_url = admin_private_file_url(image_field)
    if not image_url:
        return format_html(
            '<span style="color:#888;font-size:12px">{}</span>',
            "Preview unavailable",
        )

    return format_html(
        '<a href="{url}" target="_blank" rel="noopener noreferrer">'
        '<img src="{url}" alt="{alt}" loading="lazy" '
        'style="display:block;width:{width}px;height:{height}px;object-fit:{fit};'
        'border-radius:{radius}px;background:{background};padding:4px;box-sizing:border-box;'
        'border:1px solid rgba(0,0,0,.12);box-shadow:0 2px 8px rgba(0,0,0,.10)" />'
        '</a>',
        url=image_url,
        alt=alt,
        width=max(1, int(width)),
        height=max(1, int(height)),
        fit=object_fit,
        radius=max(0, int(border_radius)),
        background=background,
    )


def book_cover_preview(book, *, width: int = 48, height: int = 64):
    if not book:
        return "—"
    return admin_image_preview(
        image_field=getattr(book, "cover_image", None),
        width=width,
        height=height,
        alt=f"Cover of {book.title}",
    )


def edition_cover_preview(edition, *, width: int = 48, height: int = 64):
    if not edition:
        return "—"
    return admin_image_preview(
        image_field=edition.effective_cover_image,
        width=width,
        height=height,
        alt=f"Cover of {edition}",
    )
