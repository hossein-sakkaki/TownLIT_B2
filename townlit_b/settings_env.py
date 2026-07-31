# townlit_b/settings_env.py

from __future__ import annotations

import os

from collections.abc import Iterable
from pathlib import Path


_TRUE_VALUES = frozenset({
    "1",
    "true",
    "yes",
    "on",
})

_FALSE_VALUES = frozenset({
    "0",
    "false",
    "no",
    "off",
})


def env_string(
    name: str,
    *,
    default: str = "",
    strip: bool = True,
) -> str:
    """
    Read a string environment variable safely.
    """

    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    return raw_value.strip() if strip else raw_value


def env_bool(
    name: str,
    *,
    default: bool = False,
) -> bool:
    """
    Read a boolean environment variable safely.

    Supported true values:
    1, true, yes, on

    Supported false values:
    0, false, no, off

    Empty or unknown values fall back to default.
    """

    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()

    if not normalized:
        return default

    if normalized in _TRUE_VALUES:
        return True

    if normalized in _FALSE_VALUES:
        return False

    return default


def env_int(
    name: str,
    *,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """
    Read an integer environment variable safely.

    Empty or invalid values fall back to default.
    Optional bounds are applied after parsing.
    """

    raw_value = os.getenv(name)

    if raw_value is None:
        value = default
    else:
        normalized = raw_value.strip()

        if not normalized:
            value = default
        else:
            try:
                value = int(normalized)
            except (TypeError, ValueError):
                value = default

    if minimum is not None:
        value = max(minimum, value)

    if maximum is not None:
        value = min(maximum, value)

    return value


def env_float(
    name: str,
    *,
    default: float,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    """
    Read a floating-point environment variable safely.

    Empty or invalid values fall back to default.
    Optional bounds are applied after parsing.
    """

    raw_value = os.getenv(name)

    if raw_value is None:
        value = default
    else:
        normalized = raw_value.strip()

        if not normalized:
            value = default
        else:
            try:
                value = float(normalized)
            except (TypeError, ValueError):
                value = default

    if minimum is not None:
        value = max(minimum, value)

    if maximum is not None:
        value = min(maximum, value)

    return value


def env_list(
    name: str,
    *,
    default: Iterable[str] = (),
    separator: str = ",",
) -> list[str]:
    """
    Read a separated list from an environment variable.
    """

    raw_value = os.getenv(name)

    if raw_value is None:
        return [
            str(item).strip()
            for item in default
            if str(item).strip()
        ]

    return [
        item.strip()
        for item in raw_value.split(separator)
        if item.strip()
    ]


def env_path(
    name: str,
    *,
    default: str | Path = "",
    base_dir: Path | None = None,
) -> Path:
    """
    Read a filesystem path from an environment variable.

    Relative paths can optionally be resolved from base_dir.
    """

    raw_value = os.getenv(name)

    selected = (
        str(default)
        if raw_value is None
        else raw_value.strip()
    )

    path = Path(selected).expanduser()

    if (
        selected
        and base_dir is not None
        and not path.is_absolute()
    ):
        path = base_dir / path

    return path