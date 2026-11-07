# apps/core/crypto/protected_columns.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Shared typed adapters for TownLIT's existing row-bound FieldProtector.

No new encryption primitive is introduced. No log output contains cleartext.
The two model mixins are for an explicit expand/backfill/cutover migration.
"""
from __future__ import annotations

import json
from datetime import date, datetime

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction

from apps.core.crypto.field_protection import FieldProtector, FieldProtectionIntegrityError


# Spec format: public_name -> (encrypted_column, "date" | "text" | "json")

def _encode(value, kind):
    if value is None:
        return None
    if kind == "date":
        if isinstance(value, datetime):
            raise TypeError("Protected birthday requires a date, not datetime.")
        if isinstance(value, str):
            value = date.fromisoformat(value)
        if not isinstance(value, date):
            raise TypeError("Protected date must be a date or ISO date string.")
        return value.isoformat()
    if kind == "text":
        if not isinstance(value, str):
            raise TypeError("Protected text must be a string or None.")
        return value
    if kind == "json":
        return json.dumps(value, cls=DjangoJSONEncoder, ensure_ascii=False,
                          separators=(",", ":"), sort_keys=True)
    raise ValueError("Unknown protected field codec.")


def _decode(value, kind):
    if value is None:
        return None
    if kind == "date":
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise FieldProtectionIntegrityError("Invalid protected date payload.") from exc
    if kind == "json":
        try:
            return json.loads(value)
        except (TypeError, ValueError) as exc:
            raise FieldProtectionIntegrityError("Invalid protected JSON payload.") from exc
    if kind == "text":
        return value
    raise ValueError("Unknown protected field codec.")


def _field_identifier(obj, name):
    return f"{obj._meta.label}.{name}"


def protect_column(obj, name, value, kind):
    plain = _encode(value, kind)
    if plain is None:
        return None
    return FieldProtector.from_environment().protect(
        plain, field=_field_identifier(obj, name), row_id=obj.pk
    )


def reveal_column(obj, name, encrypted, kind):
    if encrypted is None:
        return None
    raw = FieldProtector.from_environment().reveal(
        encrypted, field=_field_identifier(obj, name), row_id=obj.pk
    )
    return _decode(raw, kind)


class ShadowProtectedFieldsMixin:
    """Stage A: preserve legacy columns, and persist bound ciphertext alongside them."""

    protected_field_specs = {}

    def save(self, *args, **kwargs):
        requested = kwargs.get("update_fields")
        requested = set(requested) if requested is not None else None
        if requested is not None and not requested:
            return super().save(*args, **kwargs)
        due = {
            name: (storage, kind)
            for name, (storage, kind) in self.protected_field_specs.items()
            if requested is None or name in requested
        }
        alias = kwargs.get("using") or self._state.db
        with transaction.atomic(using=alias):
            result = super().save(*args, **kwargs)
            updates = {}
            for name, (storage, kind) in due.items():
                value = getattr(self, name)
                updates[storage] = protect_column(self, name, value, kind)
            if updates:
                type(self)._base_manager.db_manager(self._state.db).filter(pk=self.pk).update(**updates)
                for storage, encrypted in updates.items():
                    setattr(self, storage, encrypted)
        return result


class EncryptedPropertyFieldsMixin:
    """Stage B: logical Python properties backed solely by encrypted DB columns."""

    protected_field_specs = {}

    def _protected_get(self, name):
        pending = self.__dict__.get("_dp_pending_fields", {})
        if name in pending:
            return pending[name]
        storage, kind = self.protected_field_specs[name]
        return reveal_column(self, name, getattr(self, storage), kind)

    def _protected_set(self, name, value):
        storage, kind = self.protected_field_specs[name]
        # Validate and normalize at assignment; encryption happens on save.
        encoded = _encode(value, kind)
        decoded = _decode(encoded, kind)
        self.__dict__.setdefault("_dp_pending_fields", {})[name] = decoded

    def save(self, *args, **kwargs):
        requested = kwargs.get("update_fields")
        requested = set(requested) if requested is not None else None
        pending = self.__dict__.get("_dp_pending_fields", {})
        if requested is not None and not requested:
            return super().save(*args, **kwargs)

        processed = {}
        for name, (storage, kind) in self.protected_field_specs.items():
            if requested is not None and storage in requested and name not in requested:
                raise ValueError("Protected columns must be written through their public properties.")
            if requested is not None and name in requested:
                requested.remove(name)
                requested.add(storage)
                if name not in pending:
                    raise ValueError("No protected field value was supplied.")
            if name in pending and (requested is None or storage in requested):
                processed[name] = (storage, kind, pending[name])

        if requested is not None:
            kwargs["update_fields"] = requested
        new_row = self._state.adding
        alias = kwargs.get("using") or self._state.db
        with transaction.atomic(using=alias):
            if not new_row:
                for name, (storage, kind, value) in processed.items():
                    setattr(self, storage, protect_column(self, name, value, kind))
            result = super().save(*args, **kwargs)
            if new_row and processed:
                updates = {}
                for name, (storage, kind, value) in processed.items():
                    updates[storage] = protect_column(self, name, value, kind)
                type(self)._base_manager.db_manager(self._state.db).filter(pk=self.pk).update(**updates)
                for storage, encrypted in updates.items():
                    setattr(self, storage, encrypted)
        for name in processed:
            pending.pop(name, None)
        return result


class ProtectedColumnsQuerySet(models.QuerySet):
    """Reject mass writes bypassing field validation and encryption."""

    def _protected_names(self):
        specs = self.model.protected_field_specs
        return set(specs) | {storage for storage, _ in specs.values()}

    def update(self, **kwargs):
        if self._protected_names().intersection(kwargs):
            raise ValueError("Bulk update of protected data is unsupported; use model.save().")
        return super().update(**kwargs)

    def bulk_create(self, objs, *args, **kwargs):
        raise ValueError("Bulk creation of protected model rows is unsupported; use model.save().")

    def bulk_update(self, objs, fields, *args, **kwargs):
        if self._protected_names().intersection(fields):
            raise ValueError("Bulk update of protected data is unsupported; use model.save().")
        return super().bulk_update(objs, fields, *args, **kwargs)
