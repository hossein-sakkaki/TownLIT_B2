# apps/accounts/services/identity_private_fields.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""IdentityVerification field protection; retains existing Fernet/FieldProtector envelope."""

import json

from django.core.serializers.json import DjangoJSONEncoder

from apps.core.crypto.field_protection import FieldProtector


_FIELDS = {
    "provider_payload": "accounts.IdentityVerification.provider_payload",
    "notes": "accounts.IdentityVerification.notes",
}


def _to_string(name, value):
    if value is None:
        return None
    if name == "provider_payload":
        return json.dumps(
            value,
            cls=DjangoJSONEncoder,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    if name == "notes" and isinstance(value, str):
        return value
    raise TypeError("Invalid protected identity value.")


def encrypt_identity_field(name, value, user_id):
    label = _FIELDS[name]
    return FieldProtector.from_environment().protect(
        _to_string(name, value), field=label, row_id=user_id
    )


def decrypt_identity_field(name, ciphertext, user_id):
    if ciphertext is None:
        return None
    label = _FIELDS[name]
    plaintext = FieldProtector.from_environment().reveal(
        ciphertext, field=label, row_id=user_id
    )
    if name == "provider_payload":
        return json.loads(plaintext)
    return plaintext
