# apps/bookstore_inventory/models/catalog.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.text import slugify

from apps.bookstore_inventory.constants import (
    BookType, ContributorRole, CopyrightStatus, FormatType, PricingMode,
)
from apps.bookstore_inventory.models.base import TimeStampedModel
from apps.bookstore_inventory.models.organizations import OrganizationRecord


class Book(TimeStampedModel):
    title = models.CharField(max_length=255, db_index=True)
    subtitle = models.CharField(max_length=255, blank=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    book_type = models.CharField(
        max_length=40, choices=BookType.choices,
        default=BookType.CHRISTIAN_BOOK, db_index=True,
    )
    description = models.TextField(blank=True)
    subject_category = models.CharField(max_length=120, blank=True, db_index=True)
    publisher = models.ForeignKey(
        OrganizationRecord, on_delete=models.PROTECT, null=True, blank=True,
        related_name="published_books",
    )
    publisher_name = models.CharField(
        max_length=255, blank=True,
        help_text="Historical/display snapshot; choose Publisher for new records.",
    )
    rights_holder = models.ForeignKey(
        OrganizationRecord, on_delete=models.PROTECT, null=True, blank=True,
        related_name="rights_held_books",
    )
    copyright_holder = models.CharField(
        max_length=255, blank=True,
        help_text="Historical/display snapshot; choose Rights holder for new records.",
    )
    original_language = models.CharField(max_length=64, blank=True, db_index=True)
    cover_image = models.ImageField(
        upload_to="bookstore_inventory/books/covers/", blank=True, null=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("title",)
        verbose_name = "Book"
        verbose_name_plural = "Books"

    def __str__(self):
        return self.title

    def _generate_unique_slug(self):
        base_slug = slugify(self.title)[:240] or "book"
        slug, index = base_slug, 1
        while Book.objects.exclude(pk=self.pk).filter(slug=slug).exists():
            slug = f"{base_slug}-{index}"
            index += 1
        return slug

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug()
        if self.publisher_id:
            self.publisher_name = str(self.publisher)
        if self.rights_holder_id:
            self.copyright_holder = str(self.rights_holder)
        super().save(*args, **kwargs)


class BookContributor(TimeStampedModel):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="contributors")
    full_name = models.CharField(max_length=255, db_index=True)
    role = models.CharField(
        max_length=32, choices=ContributorRole.choices,
        default=ContributorRole.AUTHOR, db_index=True,
    )
    sort_order = models.PositiveIntegerField(default=0)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "Book contributor"
        verbose_name_plural = "Book contributors"

    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()})"


class BookEdition(TimeStampedModel):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="editions")
    edition_code = models.CharField(max_length=80, unique=True, db_index=True)
    edition_name = models.CharField(max_length=255, blank=True)
    isbn = models.CharField(max_length=32, blank=True, db_index=True)
    barcode = models.CharField(max_length=64, blank=True, db_index=True)
    language = models.CharField(max_length=64, db_index=True)
    translated_from_language = models.CharField(max_length=64, blank=True)
    translation_name = models.CharField(max_length=255, blank=True)
    print_year = models.PositiveIntegerField(blank=True, null=True, db_index=True)
    print_number = models.PositiveIntegerField(blank=True, null=True)
    format_type = models.CharField(
        max_length=24, choices=FormatType.choices,
        default=FormatType.PAPERBACK, db_index=True,
    )
    page_count = models.PositiveIntegerField(blank=True, null=True)
    publisher = models.ForeignKey(
        OrganizationRecord, on_delete=models.PROTECT, null=True, blank=True,
        related_name="published_editions",
    )
    printer = models.ForeignKey(
        OrganizationRecord, on_delete=models.PROTECT, null=True, blank=True,
        related_name="printed_editions",
    )
    edition_publisher_name = models.CharField(
        max_length=255, blank=True,
        help_text="Historical/display snapshot; choose Publisher for new records.",
    )
    printer_name = models.CharField(
        max_length=255, blank=True,
        help_text="Historical/display snapshot; choose Printer for new records.",
    )
    publication_place = models.CharField(max_length=255, blank=True)
    copyright_status = models.CharField(
        max_length=24, choices=CopyrightStatus.choices,
        default=CopyrightStatus.UNKNOWN, db_index=True,
    )
    cover_image = models.ImageField(
        upload_to="bookstore_inventory/books/edition-covers/", blank=True, null=True,
        help_text="Optional edition-specific cover; falls back to the book cover.",
    )
    pricing_mode = models.CharField(
        max_length=32, choices=PricingMode.choices,
        default=PricingMode.FIXED_PRICE, db_index=True,
    )
    fixed_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    minimum_donation = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=12, default="CAD")
    is_sellable = models.BooleanField(default=True, db_index=True)
    is_distributable = models.BooleanField(default=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("book__title", "language", "print_year", "id")
        verbose_name = "Book edition"
        verbose_name_plural = "Book editions"

    def __str__(self):
        parts = [self.book.title, self.language]
        if self.print_number:
            parts.append(f"print {self.print_number}")
        if self.edition_name:
            parts.append(self.edition_name)
        return " - ".join(parts)

    def clean(self):
        if self.pricing_mode in {PricingMode.FREE, PricingMode.DONATION} and self.fixed_price != Decimal("0.00"):
            raise ValidationError({"fixed_price": "Free or donation editions must have zero fixed price."})
        if self.pricing_mode in {PricingMode.FIXED_PRICE, PricingMode.FIXED_PLUS_DONATION} and self.fixed_price <= Decimal("0.00"):
            raise ValidationError({"fixed_price": "A fixed-price edition must have a price greater than zero."})
        if self.minimum_donation < Decimal("0.00"):
            raise ValidationError({"minimum_donation": "Minimum donation cannot be negative."})

    def save(self, *args, **kwargs):
        if self.publisher_id:
            self.edition_publisher_name = str(self.publisher)
        if self.printer_id:
            self.printer_name = str(self.printer)
        super().save(*args, **kwargs)

    @property
    def effective_cover_image(self):
        return self.cover_image or self.book.cover_image

    @property
    def default_display_price(self):
        if self.pricing_mode == PricingMode.FREE:
            return "Free"
        if self.pricing_mode == PricingMode.DONATION:
            return "Donation"
        if self.pricing_mode == PricingMode.FIXED_PLUS_DONATION:
            return f"{self.fixed_price} {self.currency} + donation"
        return f"{self.fixed_price} {self.currency}"


class EditionPrice(TimeStampedModel):
    edition = models.ForeignKey(BookEdition, on_delete=models.CASCADE, related_name="price_history")
    pricing_mode = models.CharField(max_length=32, choices=PricingMode.choices)
    fixed_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    minimum_donation = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=12, default="CAD")
    valid_from = models.DateTimeField(db_index=True)
    valid_until = models.DateTimeField(null=True, blank=True, db_index=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("-valid_from", "-id")
        constraints = [
            models.CheckConstraint(
                check=Q(valid_until__isnull=True) | Q(valid_until__gt=models.F("valid_from")),
                name="bookstore_price_valid_date_range",
            )
        ]
        verbose_name = "Edition price"
        verbose_name_plural = "Edition price history"

    def __str__(self):
        return f"{self.edition} — {self.fixed_price} {self.currency}"
