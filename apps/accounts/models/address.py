# apps/accounts/models/address.py

from django.db import models

from apps.accounts.constants.address_types import ADDRESS_TYPE_CHOICES, HOME


class Address(models.Model):
    id = models.BigAutoField(primary_key=True)
    street_number = models.CharField(max_length=100, blank=True, verbose_name='Streen Number')
    route = models.CharField(max_length=100, blank=True, verbose_name='Route')
    locality = models.CharField(max_length=100, blank=True, verbose_name='Locality')
    administrative_area_level_1 = models.CharField(max_length=100, blank=True, verbose_name='Administrative Area Level 1')
    postal_code = models.CharField(max_length=20, blank=True, verbose_name='Postal Code')
    country = models.CharField(max_length=100, blank=True, verbose_name='Country')
    additional = models.CharField(max_length=400, null=True, blank=True, verbose_name='Additional')
    address_type = models.CharField(max_length=20, choices=ADDRESS_TYPE_CHOICES, default=HOME, verbose_name='Address Type')

    def __str__(self):
        address_parts = [
            self.street_number,
            self.route,
            self.locality,
            self.administrative_area_level_1,
            self.postal_code,
            self.country,
        ]
        if self.additional:
            address_parts.append(self.additional)
        return ', '.join(address_parts)

    class Meta:
        verbose_name = "Custom Address"
        verbose_name_plural = "Custom Addresses"