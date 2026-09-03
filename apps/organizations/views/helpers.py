# apps/organizations/views/helpers.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError


def raise_drf_validation_error(exc):
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            raise ValidationError(exc.message_dict) from exc

        if hasattr(exc, "messages"):
            raise ValidationError(exc.messages) from exc

    raise ValidationError(str(exc)) from exc
