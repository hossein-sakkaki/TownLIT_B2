# apps/accounts/models/address.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki (original creation date not recorded in source).
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Compatibility stage: every normal Address write maintains encrypted storage.

The legacy DB column is retained until backfill has passed verification.
Encrypted data is never silently replaced by legacy data on a failed read.
"""

from django.db import models, transaction

from apps.accounts.constants.address_types import ADDRESS_TYPE_CHOICES, HOME
from apps.core.crypto.field_protection import FieldProtectionUnavailable, FieldProtector


_FIELD = "accounts.Address.additional"


class AddressQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if {"additional", "additional_encrypted"}.intersection(kwargs):
            raise ValueError("Use Address.save() for protected field updates.")
        return super().update(**kwargs)

    def bulk_create(self, objs, *args, **kwargs):
        objs = list(objs)
        if any(obj.additional is not None or obj.additional_encrypted is not None for obj in objs):
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
    additional = models.CharField(max_length=400, null=True, blank=True, verbose_name="Additional")
    address_type = models.CharField(max_length=20, choices=ADDRESS_TYPE_CHOICES, default=HOME, verbose_name="Address Type")
    additional_encrypted = models.TextField(null=True, blank=True, editable=False)

    objects = AddressQuerySet.as_manager()

    def additional_for_read(self):
        if self.additional_encrypted is not None:
            if self.pk is None:
                raise FieldProtectionUnavailable("A persisted Address is required for decryption.")
            return FieldProtector.from_environment().reveal(
                self.additional_encrypted, field=_FIELD, row_id=self.pk
            )
        # Transitional fallback only; Stage B has no plaintext fallback.
        return self.additional

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            updated = set(update_fields)
            if "additional_encrypted" in updated and "additional" not in updated:
                raise ValueError("Update the protected Address field through additional.")
            if "additional" not in updated:
                return super().save(*args, **kwargs)
            if not updated:
                return super().save(*args, **kwargs)
        else:
            updated = None

        if self.pk is not None:
            self.additional_encrypted = FieldProtector.from_environment().protect(
                self.additional, field=_FIELD, row_id=self.pk
            ) if self.additional is not None else None
            if updated is not None:
                kwargs["update_fields"] = updated | {"additional_encrypted"}
            return super().save(*args, **kwargs)

        # A new PK is needed for row-bound authentication. Keep both writes atomic.
        with transaction.atomic(using=self._state.db):
            result = super().save(*args, **kwargs)
            self.additional_encrypted = FieldProtector.from_environment().protect(
                self.additional, field=_FIELD, row_id=self.pk
            ) if self.additional is not None else None
            type(self)._base_manager.db_manager(self._state.db).filter(pk=self.pk).update(
                additional_encrypted=self.additional_encrypted
            )
            return result

    def __str__(self):
        # Never include free-form delivery notes in logs or admin labels.
        return ", ".join((self.street_number, self.route, self.locality,
                          self.administrative_area_level_1, self.postal_code, self.country))

    class Meta:
        verbose_name = "Custom Address"
        verbose_name_plural = "Custom Addresses"
