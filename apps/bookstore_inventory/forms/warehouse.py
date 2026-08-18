#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-17.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.bookstore_inventory.models import WarehouseStaffAssignment


CustomUser = get_user_model()


def eligible_warehouse_staff_users():
    """
    Existing TownLIT accounts eligible for warehouse responsibility.

    is_staff is a Python property on CustomUser and cannot be used in a
    database filter. In this project it represents is_admin/is_superuser,
    so those persisted fields are used here.
    """
    return (
        CustomUser.objects
        .filter(
            is_active=True,
            is_deleted=False,
            is_suspended=False,
            is_account_paused=False,
        )
        .filter(
            Q(is_admin=True) | Q(is_superuser=True)
        )
        .order_by("family", "name", "email", "pk")
    )


class WarehouseStaffUserChoiceField(forms.ModelChoiceField):
    """Readable existing-account label for warehouse assignment."""

    def label_from_instance(self, user):
        full_name = " ".join(
            part.strip()
            for part in (
                getattr(user, "name", "") or "",
                getattr(user, "family", "") or "",
            )
            if part.strip()
        )

        identity = (
            full_name
            or getattr(user, "username", "")
            or getattr(user, "email", "")
            or str(user)
        )
        email = (getattr(user, "email", "") or "").strip()

        if email and email != identity:
            return f"{identity} — {email}"

        return identity


class WarehouseStaffAssignmentAdminForm(forms.ModelForm):
    """
    Bookstore-only assignment form.

    It selects an existing TownLIT account and never creates or modifies
    a CustomUser account.
    """

    user = WarehouseStaffUserChoiceField(
        queryset=CustomUser.objects.none(),
        required=True,
        help_text=(
            "Select an existing active TownLIT administrator account. "
            "This form cannot create or modify users."
        ),
    )

    class Meta:
        model = WarehouseStaffAssignment
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        queryset = eligible_warehouse_staff_users()

        # Keep a previously assigned account selectable for historical records,
        # even if that account was later deactivated or suspended.
        current_user_id = getattr(self.instance, "user_id", None)
        if current_user_id:
            queryset = (
                CustomUser.objects
                .filter(
                    Q(pk=current_user_id)
                    | (
                        Q(is_active=True)
                        & Q(is_deleted=False)
                        & Q(is_suspended=False)
                        & Q(is_account_paused=False)
                        & (Q(is_admin=True) | Q(is_superuser=True))
                    )
                )
                .order_by("family", "name", "email", "pk")
                .distinct()
            )

        self.fields["user"].queryset = queryset