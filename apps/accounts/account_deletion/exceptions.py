#
#  apps/accounts/account_deletion/exceptions.py
#  TownLIT
#
#  Created by Hossein Sakkaki on 2026-08-04.
#  Last Update by Hossein Sakkaki on 2026-08-04.
#


class AccountDeletionError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "account_deletion_failed",
    ):
        super().__init__(message)
        self.message = message
        self.code = code


class AccountDeletionNotPending(
    AccountDeletionError
):
    pass


class AccountDeletionDeadlinePassed(
    AccountDeletionError
):
    pass


class AccountDeletionConfigurationError(
    AccountDeletionError
):
    pass