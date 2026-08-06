# apps/sanctuary/admin/helpers.py

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from django.contrib import messages
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html


logger = logging.getLogger(__name__)


@dataclass
class AdminActionResult:
    succeeded: int = 0
    skipped: int = 0
    failed: int = 0

    def mark_succeeded(self) -> None:
        self.succeeded += 1

    def mark_skipped(self) -> None:
        self.skipped += 1

    def mark_failed(self) -> None:
        self.failed += 1


def admin_change_url(
    obj: Any,
) -> str | None:
    if obj is None:
        return None

    try:
        return reverse(
            (
                f"admin:{obj._meta.app_label}_"
                f"{obj._meta.model_name}_change"
            ),
            args=[obj.pk],
        )
    except (
        NoReverseMatch,
        AttributeError,
        TypeError,
    ):
        return None


def admin_link(
    obj: Any,
    label: str | None = None,
):
    if obj is None:
        return "-"

    resolved_label = (
        label
        or str(obj)
    )

    url = admin_change_url(
        obj
    )

    if not url:
        return resolved_label

    return format_html(
        '<a href="{}">{}</a>',
        url,
        resolved_label,
    )


def username_link(
    user: Any,
):
    if user is None:
        return "-"

    username = (
        getattr(
            user,
            "username",
            None,
        )
        or str(user)
    )

    return admin_link(
        user,
        f"@{username}",
    )


def target_link_with_lock(
    target: Any,
    *,
    is_locked: bool,
):
    if target is None:
        return "-"

    linked_target = admin_link(
        target
    )

    if not is_locked:
        return linked_target

    return format_html(
        '{} <span title="Editing is locked">🔒</span>',
        linked_target,
    )


def report_admin_action_summary(
    *,
    model_admin,
    request,
    label: str,
    result: AdminActionResult,
) -> None:
    summary = (
        f"{label}: "
        f"{result.succeeded} succeeded, "
        f"{result.skipped} skipped, "
        f"{result.failed} failed."
    )

    if result.failed:
        level = messages.WARNING
    else:
        level = messages.SUCCESS

    model_admin.message_user(
        request,
        summary,
        level=level,
    )


def run_admin_action(
    *,
    objects: Iterable[Any],
    operation: Callable[[Any], bool | None],
    logger_message: str,
) -> AdminActionResult:
    """
    Execute a per-object operation without hiding failures.

    Return convention:
    - True / None: succeeded
    - False: skipped
    - Exception: failed and logged
    """

    result = AdminActionResult()

    for obj in objects:
        try:
            operation_result = operation(
                obj
            )

            if operation_result is False:
                result.mark_skipped()
            else:
                result.mark_succeeded()

        except Exception:
            result.mark_failed()

            logger.exception(
                logger_message,
                extra={
                    "object_id": getattr(
                        obj,
                        "pk",
                        None,
                    ),
                    "model": (
                        obj._meta.label_lower
                        if hasattr(obj, "_meta")
                        else None
                    ),
                },
            )

    return result