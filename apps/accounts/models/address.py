# apps/accounts/models/address.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki (original creation date not recorded in source).
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Encrypted-only delivery instructions; no persisted plaintext copy."""

from django.db import models, transaction

from apps.accounts.constants.address_types import ADDRESS_TYPE_CHOICES, HOME
from apps.core.crypto.field_protection import FieldProtectionUnavailable, FieldProtector


_FIELD = "accounts.Address.additional"
_PENDING = "_dp_pending_additional"


class AddressQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if "additional" in kwargs or "additional_encrypted" in kwargs:
            raise ValueError("Use Address.save() for protected field updates.")
        return super().update(**kwargs)

    def bulk_create(self, objs, *args, **kwargs):
        objs = list(objs)
        if any(_PENDING in obj.__dict__ or obj.additional_encrypted is not None for obj in objs):
            raise ValueError("Bulk creation of protected Address data is not supported.")
        return super().bulk_create(objs, *args, **kwargs)

    def bulk_update(self, objs, fields, *args, **kwargs):
        if {"additional", "additional_encrypted"}.intersection(fields):
            raise ValueError("Bulk updates to protected Address data are not supported.")
        return super().bulk_update(objs, fields, *args, **kwargs)


class Address(models.Model):
    id = models.BigAutoField(primary_key=True)
    street_number = models.CharField(max_length=100, blank=True, verbose_name="Streen Number")
    route = models.CharField(max_length=100, blank=True, verbose_name="Route")
    locality = models.CharField(max_length=100, blank=True, verbose_name="Locality")
    administrative_area_level_1 = models.CharField(max_length=100, blank=True, verbose_name="Administrative Area Level 1")
    postal_code = models.CharField(max_length=20, blank=True, verbose_name="Postal Code")
    country = models.CharField(max_length=100, blank=True, verbose_name="Country")
    address_type = models.CharField(max_length=20, choices=ADDRESS_TYPE_CHOICES, default=HOME, verbose_name="Address Type")
    additional_encrypted = models.TextField(null=True, blank=True, editable=False)

    objects = AddressQuerySet.as_manager()

    @property
    def additional(self):
        if _PENDING in self.__dict__:
            return self.__dict__[_PENDING]
        if self.additional_encrypted is None:
            return None
        if self.pk is None:
            raise FieldProtectionUnavailable("Persisted Address required for decryption.")
        return FieldProtector.from_environment().reveal(
            self.additional_encrypted, field=_FIELD, row_id=self.pk
        )

    @additional.setter
    def additional(self, value):
        if value is not None:
            if not isinstance(value, str):
                raise TypeError("Address additional must be text or None.")
            if len(value) > 400:
                raise ValueError("Address additional exceeds allowed length.")
        self.__dict__[_PENDING] = value

    def additional_for_read(self):
        return self.additional

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        updated = set(update_fields) if update_fields is not None else None
        pending = _PENDING in self.__dict__

        if updated is not None:
            if "additional_encrypted" in updated and "additional" not in updated:
                raise ValueError("Update the protected Address value through additional.")
            if "additional" in updated and not pending:
                raise ValueError("No protected Address value was supplied.")
            if "additional" not in updated:
                return super().save(*args, **kwargs)
            updated.remove("additional")
            updated.add("additional_encrypted")
            kwargs["update_fields"] = updated

        if not pending:
            return super().save(*args, **kwargs)

        value = self.__dict__[_PENDING]
        if self.pk is not None:
            self.additional_encrypted = (
                FieldProtector.from_environment().protect(value, field=_FIELD, row_id=self.pk)
                if value is not None else None
            )
            result = super().save(*args, **kwargs)
            self.__dict__.pop(_PENDING, None)
            return result

        # New PK and its ciphertext must commit atomically; no plaintext column exists.
        with transaction.atomic(using=self._state.db):
            result = super().save(*args, **kwargs)
            encrypted = (
                FieldProtector.from_environment().protect(value, field=_FIELD, row_id=self.pk)
                if value is not None else None
            )
            type(self)._base_manager.db_manager(self._state.db).filter(pk=self.pk).update(
                additional_encrypted=encrypted
            )
            self.additional_encrypted = encrypted
        self.__dict__.pop(_PENDING, None)
        return result

    def __str__(self):
        return ", ".join((self.street_number, self.route, self.locality,
                          self.administrative_area_level_1, self.postal_code, self.country))

    class Meta:
        verbose_name = "Custom Address"
        verbose_name_plural = "Custom Addresses"
