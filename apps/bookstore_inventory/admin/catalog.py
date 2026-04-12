# apps/bookstore_inventory/admin/catalog.py

from django.contrib import admin

from apps.bookstore_inventory.models import Book, BookContributor, BookEdition


class BookContributorInline(admin.TabularInline):
    # Book contributors inline
    model = BookContributor
    extra = 1
    fields = ("full_name", "role", "sort_order", "notes")


class BookEditionInline(admin.TabularInline):
    # Book editions inline
    model = BookEdition
    extra = 0
    fields = (
        "edition_code",
        "language",
        "print_year",
        "print_number",
        "pricing_mode",
        "fixed_price",
        "currency",
        "is_active",
    )
    show_change_link = True


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    # Book admin
    list_display = (
        "title",
        "book_type",
        "original_language",
        "publisher_name",
        "is_active",
        "edition_count",
    )
    search_fields = ("title", "subtitle", "publisher_name", "subject_category", "slug")
    list_filter = ("book_type", "original_language", "is_active")
    inlines = [BookContributorInline, BookEditionInline]
    readonly_fields = ("slug", "created_at", "updated_at")
    fieldsets = (
        ("Main", {
            "fields": ("title", "subtitle", "slug", "book_type", "is_active")
        }),
        ("Details", {
            "fields": ("description", "subject_category", "original_language")
        }),
        ("Rights and publisher", {
            "fields": ("publisher_name", "copyright_holder")
        }),
        ("Media and notes", {
            "fields": ("cover_image", "notes")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def edition_count(self, obj):
        # Count editions
        return obj.editions.count()

    edition_count.short_description = "Editions"


@admin.register(BookEdition)
class BookEditionAdmin(admin.ModelAdmin):
    # Edition admin
    list_display = (
        "book",
        "edition_code",
        "language",
        "print_year",
        "print_number",
        "pricing_mode",
        "fixed_price",
        "currency",
        "stock_summary",
        "is_active",
    )
    search_fields = (
        "edition_code",
        "book__title",
        "edition_name",
        "isbn",
        "barcode",
        "translation_name",
    )
    list_filter = (
        "language",
        "pricing_mode",
        "format_type",
        "copyright_status",
        "is_sellable",
        "is_distributable",
        "is_active",
    )
    readonly_fields = ("created_at", "updated_at", "stock_summary")
    autocomplete_fields = ("book",)
    fieldsets = (
        ("Main", {
            "fields": ("book", "edition_code", "edition_name", "is_active")
        }),
        ("Identifiers", {
            "fields": ("isbn", "barcode")
        }),
        ("Language and translation", {
            "fields": ("language", "translated_from_language", "translation_name")
        }),
        ("Print and format", {
            "fields": ("print_year", "print_number", "format_type", "page_count")
        }),
        ("Publisher and copyright", {
            "fields": ("edition_publisher_name", "publication_place", "copyright_status")
        }),
        ("Pricing", {
            "fields": (
                "pricing_mode",
                "fixed_price",
                "minimum_donation",
                "currency",
                "is_sellable",
                "is_distributable",
            )
        }),
        ("Inventory", {
            "fields": ("stock_summary",)
        }),
        ("Notes", {
            "fields": ("notes",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def stock_summary(self, obj):
        # Show stock across warehouses
        balances = obj.balances.select_related("warehouse").all()
        if not balances:
            return "No stock"
        parts = []
        for balance in balances:
            parts.append(
                f"{balance.warehouse.name}: on hand {balance.on_hand_quantity}, available {balance.available_quantity}"
            )
        return " | ".join(parts)

    stock_summary.short_description = "Stock"