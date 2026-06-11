# apps/accounting/services/payroll/comparison_service.py

from decimal import Decimal

from apps.accounting.models import PayStub


ZERO = Decimal("0.00")


class PayrollComparisonService:
    """
    Compares internal payroll calculation with final pay stub values.
    """

    def compare_pay_stub(self, *, pay_stub: PayStub) -> dict:
        """
        Compare auto values stored in snapshot against final stored values.
        """

        snapshot = pay_stub.calculation_snapshot or {}
        calculated_values = snapshot.get("calculated_values", {})
        manual_overrides = snapshot.get("manual_overrides", {})

        fields = [
            ("employee_cpp", "Employee CPP"),
            ("employer_cpp", "Employer CPP"),
            ("employee_cpp2", "Employee CPP2"),
            ("employer_cpp2", "Employer CPP2"),
            ("employee_ei", "Employee EI"),
            ("employer_ei", "Employer EI"),
            ("federal_income_tax", "Federal income tax"),
            ("provincial_income_tax", "Provincial income tax"),
        ]

        rows = []

        for field_name, label in fields:
            auto_value = self._read_auto_value(
                snapshot=snapshot,
                calculated_values=calculated_values,
                field_name=field_name,
            )

            final_value = Decimal(
                str(getattr(pay_stub, field_name) or ZERO)
            ).quantize(Decimal("0.01"))

            difference = (final_value - auto_value).quantize(Decimal("0.01"))

            rows.append(
                {
                    "field": field_name,
                    "label": label,
                    "auto_value": auto_value,
                    "final_value": final_value,
                    "difference": difference,
                    "matches": difference == ZERO,
                }
            )

        return {
            "pay_stub": pay_stub,
            "employee": pay_stub.employee.display_name,
            "pay_run": pay_stub.pay_run.run_number,
            "has_manual_overrides": manual_overrides.get(
                "has_manual_overrides",
                snapshot.get("has_manual_overrides", False),
            ),
            "override_source": manual_overrides.get(
                "override_source",
                snapshot.get("override_source", ""),
            ),
            "override_note": manual_overrides.get(
                "override_note",
                snapshot.get("override_note", ""),
            ),
            "rows": rows,
        }

    def _read_auto_value(self, *, snapshot: dict, calculated_values: dict, field_name: str) -> Decimal:
        """
        Read auto-calculated value from either new or legacy snapshot shape.
        """

        raw = snapshot.get(f"auto_{field_name}")

        if raw is None:
            raw = calculated_values.get(field_name)

        if raw is None:
            raw = "0.00"

        return Decimal(str(raw)).quantize(Decimal("0.01"))