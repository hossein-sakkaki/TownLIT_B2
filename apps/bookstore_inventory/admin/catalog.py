# apps/bookstore_inventory/admin/catalog.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django.contrib import admin
from django.db.models import Count, Sum

from apps.bookstore_inventory.admin.common import (
    HiddenFromAdminIndexMixin, ImmutableAdminMixin, WorkflowAdminMixin,
)
from apps.bookstore_inventory.admin.media import book_cover_preview, edition_cover_preview
from apps.bookstore_inventory.models import Book, BookContributor, BookEdition, EditionPrice


class BookContributorInline(admin.TabularInline):
    model = BookContributor
    extra = 0
    fields = ("full_name", "role", "sort_order", "notes")
    ordering = ("sort_order", "id")


class BookEditionInline(admin.TabularInline):
    model = BookEdition
    extra = 0
    fields = ("cover_preview", "edition_code", "language", "print_year", "pricing_mode", "fixed_price", "currency", "is_active")
    readonly_fields = ("cover_preview",)
    show_change_link = True

    @admin.display(description="Cover")
    def cover_preview(self, obj):
        return edition_cover_preview(obj)


class EditionPriceInline(admin.TabularInline):
    model = EditionPrice
    extra = 0
    fields = ("pricing_mode", "fixed_price", "minimum_donation", "currency", "valid_from", "valid_until", "notes")
    ordering = ("-valid_from", "-id")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Book)
class BookAdmin(HiddenFromAdminIndexMixin, WorkflowAdminMixin, admin.ModelAdmin):
    list_display = ("cover_thumbnail", "title", "book_type", "original_language", "publisher", "edition_count", "is_active")
    list_display_links = ("cover_thumbnail", "title")
    list_filter = ("is_active", "book_type", "original_language")
    search_fields = ("title", "subtitle", "publisher_name", "publisher__official_name", "subject_category", "contributors__full_name")
    autocomplete_fields = ("publisher", "rights_holder")
    readonly_fields = ("cover_preview", "slug", "created_at", "updated_at")
    inlines = (BookContributorInline, BookEditionInline)
    fieldsets = (
        ("Identity", {"fields": (("title", "subtitle"), ("book_type", "is_active"), "slug")}),
        ("Catalogue details", {"fields": ("description", ("subject_category", "original_language"))}),
        ("Publishing and rights", {"fields": (("publisher", "rights_holder"), ("publisher_name", "copyright_holder")), "description": "Choose organizations from the shared directory. Text values are retained as historical snapshots."}),
        ("Cover and notes", {"fields": (("cover_preview", "cover_image"), "notes")}),
        ("Audit", {"fields": (("created_at", "updated_at"),), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_edition_count=Count("editions", distinct=True))

    @admin.display(description="Cover")
    def cover_thumbnail(self, obj):
        return book_cover_preview(obj)

    @admin.display(description="Current cover")
    def cover_preview(self, obj):
        if not obj:
            return "Save the book to preview its cover."
        return book_cover_preview(obj, width=180, height=240)

    @admin.display(description="Editions", ordering="_edition_count")
    def edition_count(self, obj):
        return obj._edition_count


@admin.register(BookEdition)
class BookEditionAdmin(HiddenFromAdminIndexMixin, WorkflowAdminMixin, admin.ModelAdmin):
    workflow_select_related = ("book", "publisher", "printer")
    list_display = ("cover_thumbnail", "edition_code", "book", "language", "print_year", "default_display_price", "on_hand", "available", "is_active")
    list_display_links = ("cover_thumbnail", "edition_code")
    list_filter = ("is_active", "is_sellable", "is_distributable", "language", "pricing_mode", "format_type", "copyright_status")
    search_fields = ("edition_code", "book__title", "edition_name", "isbn", "barcode", "translation_name")
    autocomplete_fields = ("book", "publisher", "printer")
    readonly_fields = ("cover_preview", "stock_summary", "created_at", "updated_at")
    fieldsets = (
        ("Identity", {"fields": (("cover_preview", "book"), "cover_image", ("edition_code", "edition_name"), ("isbn", "barcode"), "is_active")}),
        ("Language and print", {"fields": (("language", "translated_from_language"), "translation_name", ("print_year", "print_number"), ("format_type", "page_count"))}),
        ("Publishing and rights", {"fields": (("publisher", "printer"), ("edition_publisher_name", "printer_name"), ("publication_place", "copyright_status")), "description": "Organization fields are reusable directory records; name fields are historical snapshots."}),
        ("Pricing and availability", {"fields": (("pricing_mode", "currency"), ("fixed_price", "minimum_donation"), ("is_sellable", "is_distributable"))}),
        ("Current inventory", {"fields": ("stock_summary",)}),
        ("Notes and audit", {"fields": ("notes", ("created_at", "updated_at")), "classes": ("collapse",)}),
    )
    inlines = (EditionPriceInline,)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _on_hand=Sum("balances__on_hand_quantity"),
            _reserved=Sum("balances__reserved_quantity"),
        )

    @admin.display(description="Cover")
    def cover_thumbnail(self, obj):
        return edition_cover_preview(obj)

    @admin.display(description="Book cover")
    def cover_preview(self, obj):
        if not obj:
            return "Select a book and save to preview its cover."
        return edition_cover_preview(obj, width=180, height=240)

    @admin.display(description="On hand", ordering="_on_hand")
    def on_hand(self, obj):
        return obj._on_hand or 0

    @admin.display(description="Available")
    def available(self, obj):
        return (obj._on_hand or 0) - (obj._reserved or 0)

    @admin.display(description="Stock by warehouse")
    def stock_summary(self, obj):
        if not obj.pk:
            return "Save the edition to see stock."
        balances = obj.balances.select_related("warehouse").order_by("warehouse__name")
        return " | ".join(
            f"{row.warehouse.name}: {row.on_hand_quantity} on hand / {row.available_quantity} available"
            for row in balances
        ) or "No stock"


@admin.register(EditionPrice)
class EditionPriceAdmin(HiddenFromAdminIndexMixin, ImmutableAdminMixin, WorkflowAdminMixin, admin.ModelAdmin):
    workflow_select_related = ("edition", "edition__book")
    list_display = ("valid_from", "edition", "pricing_mode", "fixed_price", "minimum_donation", "currency", "valid_until")
    list_filter = ("pricing_mode", "currency", "valid_from", "valid_until")
    search_fields = ("edition__edition_code", "edition__book__title", "notes")
    date_hierarchy = "valid_from"
