# apps/bookstore_inventory/admin/orders.py

from django.contrib import admin
from django.utils.html import format_html

from apps.bookstore_inventory.admin.actions import fulfill_selected_orders
from apps.bookstore_inventory.admin.mixins import AdminSummaryMixin, ProtectedAfterPostMixin, ProtectedInlineMixin
from apps.bookstore_inventory.forms.orders import BookOrderAdminForm
from apps.bookstore_inventory.models import BookOrder, BookOrderItem, PaymentRecord
from apps.bookstore_inventory.services.numbering import generate_order_number


class BookOrderItemInline(ProtectedInlineMixin):
    # Order items inline
    model = BookOrderItem
    parent_lock_attr = "is_fulfilled"
    extra = 1
    autocomplete_fields = ("book_edition", "warehouse")
    fields = (
        "book_edition",
        "warehouse",
        "quantity",
        "unit_price",
        "line_total",
        "pricing_mode_snapshot",
        "notes",
    )
    readonly_fields = ("line_total",)


class PaymentRecordInline(ProtectedInlineMixin):
    # Order payments inline
    model = PaymentRecord
    parent_lock_attr = "is_fulfilled"
    extra = 0
    autocomplete_fields = ("received_by",)
    fields = (
        "amount",
        "currency",
        "payment_method",
        "payment_status",
        "transaction_reference",
        "received_by",
        "received_at",
        "notes",
    )


@admin.register(BookOrder)
class BookOrderAdmin(ProtectedAfterPostMixin, AdminSummaryMixin, admin.ModelAdmin):
    # Order admin
    form = BookOrderAdminForm
    actions = [fulfill_selected_orders]
    # change_list_template = "admin/bookstore_inventory/change_list_with_summary.html"

    protected_fieldsets = (
        "order_type",
        "recipient_type",
        "recipient_first_name",
        "recipient_last_name",
        "recipient_email",
        "recipient_phone",
        "organization_name",
        "organization_contact_person",
        "organization_email",
        "organization_phone",
        "delivery_method",
        "purpose",
        "destination_name",
        "address_line_1",
        "address_line_2",
        "city",
        "province_state",
        "postal_code",
        "country",
        "currency",
        "donation_amount",
        "discount_amount",
    )
    protected_inline_message = "Fulfilled orders cannot be edited. Items and payments are locked."

    summary_config = {
        "order_count": {"aggregate": "count"},
        "total_amount_sum": {"aggregate": "sum", "field": "total_amount"},
        "paid_amount_sum": {"aggregate": "sum", "field": "paid_amount"},
        "remaining_amount_sum": {"aggregate": "sum", "field": "remaining_amount"},
    }

    list_display = (
        "order_number",
        "order_type",
        "recipient_type",
        "recipient_display_admin",
        "purpose",
        "status_badge",
        "currency",
        "total_amount",
        "paid_amount",
        "remaining_amount",
        "payment_status",
        "fulfilled_badge",
        "created_at",
    )
    search_fields = (
        "order_number",
        "recipient_first_name",
        "recipient_last_name",
        "recipient_email",
        "recipient_phone",
        "organization_name",
        "organization_contact_person",
        "organization_email",
        "organization_phone",
        "destination_name",
    )
    list_filter = (
        "order_type",
        "recipient_type",
        "purpose",
        "delivery_method",
        "status",
        "payment_status",
        "currency",
        "created_at",
        "fulfilled_at",
    )
    readonly_fields = (
        "subtotal_amount",
        "total_amount",
        "paid_amount",
        "remaining_amount",
        "fulfilled_at",
        "fulfilled_by",
        "fulfilled_badge",
        "created_at",
        "updated_at",
    )
    autocomplete_fields = ("created_by", "fulfilled_by")
    inlines = [BookOrderItemInline, PaymentRecordInline]
    fieldsets = (
        ("Main", {
            "fields": ("order_number", "order_type", "status", "payment_status")
        }),
        ("Recipient type", {
            "fields": ("recipient_type", "purpose", "delivery_method")
        }),
        ("Person", {
            "classes": ("book-order-person-section",),
            "fields": (
                "recipient_first_name",
                "recipient_last_name",
                "recipient_email",
                "recipient_phone",
            )
        }),
        ("Organization", {
            "classes": ("book-order-organization-section",),
            "fields": (
                "organization_name",
                "organization_contact_person",
                "organization_email",
                "organization_phone",
            )
        }),
        ("Destination", {
            "classes": ("book-order-destination-section",),
            "fields": (
                "destination_name",
                "address_line_1",
                "address_line_2",
                "city",
                "province_state",
                "postal_code",
                "country",
            )
        }),
        ("Amounts", {
            "fields": (
                "currency",
                "subtotal_amount",
                "donation_amount",
                "discount_amount",
                "total_amount",
                "paid_amount",
                "remaining_amount",
            )
        }),
        ("Fulfillment", {
            "fields": ("fulfilled_at", "fulfilled_by", "fulfilled_badge")
        }),
        ("Notes", {
            "fields": ("notes", "created_by")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    class Media:
        # Load admin helper script
        js = ("bookstore_inventory/admin/js/book_order_admin.js",)

    def is_locked(self, obj):
        # Lock after fulfillment
        return obj.is_fulfilled

    def save_model(self, request, obj, form, change):
        # Auto-fill order number
        if not obj.order_number:
            obj.order_number = generate_order_number()
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def recipient_display_admin(self, obj):
        # Show recipient in list display
        return obj.recipient_display

    recipient_display_admin.short_description = "Recipient"

    def fulfilled_badge(self, obj):
        # Display fulfillment state
        if obj.is_fulfilled:
            return format_html(
                '<span style="color:#15803d;font-weight:600;">Fulfilled</span>'
            )
        return format_html(
            '<span style="color:#b45309;font-weight:600;">Pending</span>'
        )

    fulfilled_badge.short_description = "Fulfillment"

    def status_badge(self, obj):
        # Display order status badge
        color = "#475569"
        if obj.status == "fulfilled":
            color = "#15803d"
        elif obj.status == "confirmed":
            color = "#1d4ed8"
        elif obj.status == "draft":
            color = "#b45309"
        elif obj.status == "cancelled":
            color = "#b91c1c"

        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def changelist_view(self, request, extra_context=None):
        # Add friendly titles for summary
        extra_context = extra_context or {}
        summary_data = self.get_summary_data(request)
        extra_context["summary_data_verbose"] = {
            "Order count": summary_data.get("order_count", 0),
            "Total amount": summary_data.get("total_amount_sum", 0),
            "Paid amount": summary_data.get("paid_amount_sum", 0),
            "Remaining amount": summary_data.get("remaining_amount_sum", 0),
        }
        return super().changelist_view(request, extra_context=extra_context)