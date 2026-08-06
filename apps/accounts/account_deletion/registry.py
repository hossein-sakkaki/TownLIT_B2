#
#  apps/accounts/account_deletion/registry.py
#  TownLIT
#
#  Created by Hossein Sakkaki on 2026-08-04.
#  Last Update by Hossein Sakkaki on 2026-08-04.
#

from dataclasses import dataclass
from typing import Callable

from apps.accounts.account_deletion.context import (
    AccountDeletionContext,
)


AccountDeletionHandler = Callable[
    [AccountDeletionContext],
    None,
]


@dataclass(frozen=True)
class RegisteredDeletionHandler:
    key: str
    order: int
    handler: AccountDeletionHandler


class AccountDeletionRegistry:
    def __init__(self):
        self._handlers: dict[
            str,
            RegisteredDeletionHandler,
        ] = {}

    def register(
        self,
        *,
        key: str,
        order: int,
    ):
        normalized_key = str(key).strip().lower()

        if not normalized_key:
            raise ValueError(
                "Account deletion handler key is required."
            )

        def decorator(
            handler: AccountDeletionHandler,
        ):
            if normalized_key in self._handlers:
                raise RuntimeError(
                    "Duplicate account deletion handler: "
                    f"{normalized_key}"
                )

            self._handlers[normalized_key] = (
                RegisteredDeletionHandler(
                    key=normalized_key,
                    order=int(order),
                    handler=handler,
                )
            )

            return handler

        return decorator

    def handlers(
        self,
    ) -> list[RegisteredDeletionHandler]:
        return sorted(
            self._handlers.values(),
            key=lambda item: (
                item.order,
                item.key,
            ),
        )

    def registered_keys(self) -> set[str]:
        return set(self._handlers.keys())


account_deletion_registry = AccountDeletionRegistry()