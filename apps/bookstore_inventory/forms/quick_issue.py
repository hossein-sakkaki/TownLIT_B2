# apps/bookstore_inventory/forms/quick_issue.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django import forms
from django.forms import (
    BaseFormSet,
    formset_factory,
)
from django.utils import timezone

from apps.bookstore_inventory.constants import (
    OrderPurpose,
    OrderType,
    PaymentMethod,
    RecipientType,
)
from apps.bookstore_inventory.models import (
    BookEdition,
    OrganizationRecord,
    Warehouse,
)


QUICK_ISSUE_TYPE_CHOICES = (
    (
        OrderType.FREE_DISTRIBUTION,
        "Free distribution",
    ),
    (
        OrderType.SALE,
        "Paid sale",
    ),
)


class QuickIssueForm(forms.Form):
    submission_token = forms.CharField(
        widget=forms.HiddenInput,
    )

    warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.none(),
        label="Warehouse",
        help_text=(
            "Stock will be deducted immediately "
            "from this warehouse."
        ),
    )

    issue_at = forms.DateTimeField(
        label="Issue date and time",
        input_formats=(
            "%Y-%m-%dT%H:%M",
        ),
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={
                "type": "datetime-local",
            },
        ),
    )

    issue_type = forms.ChoiceField(
        choices=QUICK_ISSUE_TYPE_CHOICES,
        initial=OrderType.FREE_DISTRIBUTION,
        label="Issue type",
        help_text=(
            "Choose whether the books were "
            "given away or sold and paid immediately."
        ),
    )

    purpose = forms.ChoiceField(
        choices=OrderPurpose.choices,
        initial=OrderPurpose.CHURCH_SUPPORT,
        label="Purpose",
    )

    recipient_type = forms.ChoiceField(
        choices=(
            (
                RecipientType.ORGANIZATION,
                "Organization / group / ministry",
            ),
            (
                RecipientType.PERSON,
                "Individual",
            ),
        ),
        initial=RecipientType.ORGANIZATION,
        label="Recipient type",
    )

    recipient_organization = forms.ModelChoiceField(
        queryset=OrganizationRecord.objects.none(),
        required=False,
        label="Organization",
        help_text=(
            "Optional. Select an existing directory "
            "organization when appropriate."
        ),
    )

    recipient_name = forms.CharField(
        max_length=255,
        required=False,
        label="Recipient / destination",
        help_text=(
            "Examples: Persian Community - CA Church, "
            "CA Church Welcome Counter, or a person's name."
        ),
    )

    currency = forms.CharField(
        max_length=12,
        initial="CAD",
        label="Currency",
    )

    payment_method = forms.ChoiceField(
        choices=PaymentMethod.choices,
        initial=PaymentMethod.CASH,
        required=False,
        label="Payment method",
    )

    transaction_reference = forms.CharField(
        max_length=120,
        required=False,
        label="Transaction reference",
        help_text=(
            "Optional for cash; recommended for "
            "card, transfer, or e-Transfer."
        ),
    )

    notes = forms.CharField(
        required=False,
        label="Notes",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
            }
        ),
    )

    def __init__(
        self,
        *args,
        warehouse_queryset=None,
        organization_queryset=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.fields["warehouse"].queryset = (
            warehouse_queryset
            if warehouse_queryset is not None
            else Warehouse.objects.none()
        )

        self.fields[
            "recipient_organization"
        ].queryset = (
            organization_queryset
            if organization_queryset is not None
            else OrganizationRecord.objects.none()
        )

    def clean(self):
        cleaned_data = super().clean()

        issue_at = cleaned_data.get(
            "issue_at"
        )

        if (
            issue_at
            and issue_at
            > timezone.now()
        ):
            self.add_error(
                "issue_at",
                (
                    "Issue date and time cannot "
                    "be in the future."
                ),
            )

        recipient_type = cleaned_data.get(
            "recipient_type"
        )
        organization = cleaned_data.get(
            "recipient_organization"
        )
        recipient_name = (
            cleaned_data.get(
                "recipient_name"
            )
            or ""
        ).strip()

        if (
            recipient_type
            == RecipientType.PERSON
            and organization
        ):
            self.add_error(
                "recipient_organization",
                (
                    "An organization cannot be selected "
                    "for an individual recipient."
                ),
            )

        if (
            recipient_type
            == RecipientType.ORGANIZATION
            and organization
            and not recipient_name
        ):
            recipient_name = str(
                organization
            )
            cleaned_data[
                "recipient_name"
            ] = recipient_name

        if not recipient_name:
            self.add_error(
                "recipient_name",
                (
                    "Enter a recipient or destination."
                ),
            )

        issue_type = cleaned_data.get(
            "issue_type"
        )

        if (
            issue_type == OrderType.SALE
            and not cleaned_data.get(
                "payment_method"
            )
        ):
            self.add_error(
                "payment_method",
                (
                    "Payment method is required "
                    "for a paid sale."
                ),
            )

        return cleaned_data


class QuickIssueItemForm(forms.Form):
    book_edition = forms.ModelChoiceField(
        queryset=BookEdition.objects.none(),
        label="Book edition",
    )

    quantity = forms.IntegerField(
        min_value=1,
        initial=1,
        label="Quantity",
    )

    unit_price = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=False,
        label="Unit price",
        help_text=(
            "Used only for paid sales. "
            "Leave blank to use the edition's fixed price."
        ),
    )

    def __init__(
        self,
        *args,
        edition_queryset=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.fields[
            "book_edition"
        ].queryset = (
            edition_queryset
            if edition_queryset is not None
            else BookEdition.objects.none()
        )

class QuickIssueItemFormSet(BaseFormSet):

    def _construct_form(self, i, **kwargs):
        kwargs.setdefault(
            "empty_permitted",
            i != 0,
        )

        return super()._construct_form(
            i,
            **kwargs,
        )

    def clean(self):
        super().clean()

        if any(self.errors):
            return

        seen_editions = set()
        valid_items = 0

        for form in self.forms:
            if not hasattr(
                form,
                "cleaned_data",
            ):
                continue

            if form.cleaned_data.get(
                "DELETE"
            ):
                continue

            edition = form.cleaned_data.get(
                "book_edition"
            )

            if edition is None:
                continue

            valid_items += 1

            if edition.pk in seen_editions:
                raise forms.ValidationError(
                    (
                        "The same book edition cannot "
                        "be entered more than once. "
                        "Combine the quantities into one line."
                    )
                )

            seen_editions.add(
                edition.pk
            )

        if valid_items == 0:
            raise forms.ValidationError(
                "Add at least one book."
            )
            

QuickIssueItemFormSet = formset_factory(
    QuickIssueItemForm,
    formset=QuickIssueItemFormSet,
    extra=1,
    can_delete=True,
    max_num=20,
    validate_max=True,
)