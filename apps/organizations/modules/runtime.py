# apps/organizations/modules/runtime.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from dataclasses import dataclass
from importlib import import_module
from typing import Callable, Optional


@dataclass(frozen=True)
class OrganizationModuleRuntime:
    key: str
    initialize: Callable


def get_organization_module_runtime(module_key: str) -> Optional[OrganizationModuleRuntime]:
    normalized_key = str(module_key or "").strip().lower()

    if not normalized_key:
        return None

    try:
        module = import_module(
            f"apps.organizations.modules.{normalized_key}.runtime"
        )
    except ModuleNotFoundError as exc:
        expected_module = (
            f"apps.organizations.modules.{normalized_key}.runtime"
        )

        # Missing specialized package/runtime means this module has no runtime yet.
        if exc.name and expected_module.startswith(exc.name):
            return None

        # Preserve dependency/import errors raised from inside an existing runtime.
        raise

    runtime = getattr(module, "runtime", None)

    if runtime is None:
        return None

    if not isinstance(runtime, OrganizationModuleRuntime):
        raise TypeError(
            f"Invalid organization module runtime for '{normalized_key}'."
        )

    if runtime.key != normalized_key:
        raise ValueError(
            f"Organization module runtime key mismatch for '{normalized_key}'."
        )

    return runtime


def initialize_organization_module_runtime(*, activation, actor=None):
    runtime = get_organization_module_runtime(
        activation.module.key
    )

    if runtime is None:
        return None

    return runtime.initialize(
        activation=activation,
        actor=actor,
    )
