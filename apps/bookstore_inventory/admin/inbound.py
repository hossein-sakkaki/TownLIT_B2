# apps/bookstore_inventory/admin/inbound.py

from django.contrib import admin
from django.utils.html import format_html

from apps.bookstore_inventory.admin.actions import post_selected_shipments_to_stock
from apps.bookstore_inventory.admin.mixins import AdminSummaryMixin, ProtectedAfterPostMixin, ProtectedInlineMixin
from apps.bookstore_inventory.models import InboundPayment, InboundShipment, InboundShipmentItem
from apps.bookstore_inventory.services.numbering import generate_shipment_number


class InboundShipmentItemInline(ProtectedInlineMixin):
    # Shipment items inline
    model = InboundShipmentItem
    parent_lock_attr = "is_stock_posted"
    extra = 1
    autocomplete_fields = ("book_edition",)
    fields = ("book_edition", "quantity", "unit_cost", "line_total", "notes")
    readonly_fields = ("line_total",)


class InboundPaymentInline(ProtectedInlineMixin):
    # Shipment payments inline
    model = InboundPayment
    parent_lock_attr = "is_stock_posted"
    extra = 0
    autocomplete_fields = ("recorded_by",)
    fields = ("amount", "currency", "payment_reference", "paid_at", "recorded_by", "notes")


@admin.register(InboundShipment)
class InboundShipmentAdmin(ProtectedAfterPostMixin, AdminSummaryMixin, admin.ModelAdmin):
    # Inbound shipment admin
    actions = [post_selected_shipments_to_stock]

    protected_fieldsets = (
        "warehouse",
        "source_type",
        "supplier_name",
        "supplier_contact",
        "supplier_phone",
        "invoice_reference",
        "received_at",
        "shipping_cost",
        "other_cost",
        "currency",
        "is_consignment",
        "consignment_notes",
    )
    protected_inline_message = "Posted shipments cannot be edited. Items and payments are locked."

    change_list_template = "admin/bookstore_inventory/change_list_with_summary.html"

    summary_config = {
        "shipment_count": {"aggregate": "count"},
        "total_cost_sum": {"aggregate": "sum", "field": "total_cost"},
        "amount_paid_sum": {"aggregate": "sum", "field": "amount_paid"},
        "amount_due_sum": {"aggregate": "sum", "field": "amount_due"},
    }

    list_display = (
        "shipment_number",
        "warehouse",
        "source_type",
        "supplier_name",
        "received_at",
        "total_cost",
        "amount_paid",
        "amount_due",
        "payment_status_badge",
        "stock_posted_badge",
        "is_consignment",
    )
    search_fields = (
        "shipment_number",
        "supplier_name",
        "supplier_contact",
        "supplier_phone",
        "invoice_reference",
    )
    list_filter = (
        "warehouse",
        "source_type",
        "payment_status",
        "is_consignment",
        "currency",
        "received_at",
        "stock_posted_at",
    )
    autocomplete_fields = ("warehouse", "created_by", "stock_posted_by")
    readonly_fields = (
        "subtotal_cost",
        "total_cost",
        "amount_due",
        "created_at",
        "updated_at",
        "stock_posted_at",
        "stock_posted_by",
        "payment_status_badge",
        "stock_posted_badge",
    )
    inlines = [InboundShipmentItemInline, InboundPaymentInline]
    date_hierarchy = "received_at"
    fieldsets = (
        ("Main", {
            "fields": (
                "shipment_number",
                "warehouse",
                "source_type",
                "received_at",
            )
        }),
        ("Supplier", {
            "fields": (
                "supplier_name",
                "supplier_contact",
                "supplier_phone",
                "invoice_reference",
            )
        }),
        ("Costs", {
            "fields": (
                "currency",
                "shipping_cost",
                "other_cost",
                "subtotal_cost",
                "total_cost",
                "amount_paid",
                "amount_due",
                "payment_status",
                "payment_status_badge",
            )
        }),
        ("Consignment", {
            "fields": (
                "is_consignment",
                "consignment_notes",
            )
        }),
        ("Stock", {
            "fields": (
                "stock_posted_at",
                "stock_posted_by",
                "stock_posted_badge",
            )
        }),
        ("Notes", {
            "fields": ("notes", "created_by")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def is_locked(self, obj):
        # Lock after stock posting
        return obj.is_stock_posted

    def get_actions(self, request):
        # Hide action if not allowed
        actions = super().get_actions(request)
        return actions

    def save_model(self, request, obj, form, change):
        # Auto-fill shipment number
        if not obj.shipment_number:
            obj.shipment_number = generate_shipment_number()
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def payment_status_badge(self, obj):
        # Display payment status badge
        color = "#475569"
        if obj.payment_status in {"paid", "not_required"}:
            color = "#15803d"
        elif obj.payment_status == "partial":
            color = "#b45309"
        elif obj.payment_status in {"unpaid", "pay_after_sale"}:
            color = "#b91c1c"

        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>',
            color,
            obj.get_payment_status_display(),
        )

    payment_status_badge.short_description = "Payment status"

    def stock_posted_badge(self, obj):
        # Display stock posting state
        if obj.is_stock_posted:
            return format_html(
                '<span style="color:#15803d;font-weight:600;">Posted</span>'
            )
        return format_html(
            '<span style="color:#b45309;font-weight:600;">Not posted</span>'
        )

    stock_posted_badge.short_description = "Stock"

    def changelist_view(self, request, extra_context=None):
        # Add friendly titles for summary
        extra_context = extra_context or {}
        summary_data = self.get_summary_data(request)
        extra_context["summary_data_verbose"] = {
            "Shipment count": summary_data.get("shipment_count", 0),
            "Total cost": summary_data.get("total_cost_sum", 0),
            "Amount paid": summary_data.get("amount_paid_sum", 0),
            "Amount due": summary_data.get("amount_due_sum", 0),
        }
        return super().changelist_view(request, extra_context=extra_context)