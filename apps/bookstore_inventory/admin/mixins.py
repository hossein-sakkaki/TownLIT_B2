# apps/bookstore_inventory/admin/mixins.py

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce


class AdminSummaryMixin:
    # Add quick summary to changelist
    summary_config = {}

    def get_summary_data(self, request):
        # Build aggregated summary
        if not self.summary_config:
            return {}

        queryset = self.get_queryset(request)
        summary = {}

        for key, config in self.summary_config.items():
            agg = config.get("aggregate")

            if agg == "sum":
                field_name = config["field"]
                value = queryset.aggregate(
                    total=Coalesce(
                        Sum(field_name, output_field=DecimalField(max_digits=18, decimal_places=2)),
                        Value(0, output_field=DecimalField(max_digits=18, decimal_places=2)),
                    )
                )["total"]
                summary[key] = value

            elif agg == "count":
                summary[key] = queryset.count()

        return summary

    def changelist_view(self, request, extra_context=None):
        # Inject summary into changelist context
        extra_context = extra_context or {}
        extra_context["summary_data"] = self.get_summary_data(request)
        return super().changelist_view(request, extra_context=extra_context)


class ProtectedAfterPostMixin:
    # Protect object after posting/fulfillment
    protected_fieldsets = ()
    protected_inline_message = "This record is locked and can no longer be edited."

    def is_locked(self, obj):
        # Override in subclass
        return False

    def get_readonly_fields(self, request, obj=None):
        # Make protected fields readonly after lock
        readonly = list(super().get_readonly_fields(request, obj))
        if obj and self.is_locked(obj):
            for field_name in self.protected_fieldsets:
                if field_name not in readonly:
                    readonly.append(field_name)
        return readonly

    def has_delete_permission(self, request, obj=None):
        # Prevent delete after lock
        if obj and self.is_locked(obj):
            return False
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        # Prevent editing protected fields after lock
        if change and obj and obj.pk:
            original = self.model.objects.get(pk=obj.pk)
            if self.is_locked(original):
                changed_fields = set(form.changed_data)
                blocked_fields = changed_fields.intersection(set(self.protected_fieldsets))
                if blocked_fields:
                    raise ValidationError(
                        f"This record is locked. You cannot change: {', '.join(sorted(blocked_fields))}."
                    )
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        # Prevent saving inlines after lock
        obj = form.instance
        if obj and obj.pk:
            original = self.model.objects.get(pk=obj.pk)
            if self.is_locked(original):
                for formset in formsets:
                    if formset.has_changed():
                        raise ValidationError(self.protected_inline_message)
        super().save_related(request, form, formsets, change)


class ProtectedInlineMixin(admin.TabularInline):
    # Protect inline based on parent state
    parent_lock_attr = None

    def is_parent_locked(self, obj):
        # Read parent lock state
        if not obj or not self.parent_lock_attr:
            return False
        return bool(getattr(obj, self.parent_lock_attr, False))

    def has_add_permission(self, request, obj=None):
        # Disable add after lock
        if self.is_parent_locked(obj):
            return False
        return super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # Disable delete after lock
        if self.is_parent_locked(obj):
            return False
        return super().has_delete_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        # Make inline fully readonly after lock
        readonly = list(super().get_readonly_fields(request, obj))
        if self.is_parent_locked(obj):
            for field in self.fields or ():
                if field not in readonly:
                    readonly.append(field)
        return readonly


class CurrencySummaryMixin(AdminSummaryMixin):
    # Add formatted currency helpers
    currency_field_name = "currency"
    currency_symbol_map = {
        "CAD": "$",
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
    }

    def format_money(self, amount, currency="CAD"):
        # Format amount for admin display
        symbol = self.currency_symbol_map.get(currency, "")
        return f"{symbol}{amount} {currency}" if symbol else f"{amount} {currency}"


class LedgerSummaryMixin:
    # Shared ledger helpers
    def get_ledger_totals(self):
        # Aggregate ledger totals
        queryset = self.model.objects.all()
        totals = queryset.aggregate(
            total_in=Coalesce(
                Sum(
                    "amount",
                    filter=Q(direction="in"),
                    output_field=DecimalField(max_digits=18, decimal_places=2),
                ),
                Value(0, output_field=DecimalField(max_digits=18, decimal_places=2)),
            ),
            total_out=Coalesce(
                Sum(
                    "amount",
                    filter=Q(direction="out"),
                    output_field=DecimalField(max_digits=18, decimal_places=2),
                ),
                Value(0, output_field=DecimalField(max_digits=18, decimal_places=2)),
            ),
        )
        total_in = totals["total_in"]
        total_out = totals["total_out"]
        net = total_in - total_out
        return {
            "total_in": total_in,
            "total_out": total_out,
            "net": net,
        }