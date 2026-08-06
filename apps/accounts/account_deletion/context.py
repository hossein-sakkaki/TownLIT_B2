#
#  apps/accounts/account_deletion/context.py
#  TownLIT
#
#  Created by Hossein Sakkaki on 2026-08-04.
#  Last Update by Hossein Sakkaki on 2026-08-04.
#

from dataclasses import dataclass

from django.contrib.auth import get_user_model


CustomUser = get_user_model()


@dataclass(frozen=True)
class AccountDeletionContext:
    user: CustomUser
    original_email: str
    original_username: str
    anonymized_email: str
    anonymized_username: str