# apps/accounting/models/payroll.py

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .journal_entry import JournalEntry


ZERO = Decimal("0.00")


class PayrollYearConfig(models.Model):
    """
    Stores payroll rules for one tax year.
    Keep annual CRA/CPP/tax values configurable.
    """

    year = models.PositiveIntegerField(unique=True, db_index=True)

    country = models.CharField(max_length=2, default="CA")
    province = models.CharField(max_length=2, default="BC")

    currency = models.CharField(max_length=10, default="CAD")

    # CPP settings
    cpp_enabled = models.BooleanField(default=True)
    cpp_rate_employee = models.DecimalField(max_digits=8, decimal_places=5, default=0)
    cpp_rate_employer = models.DecimalField(max_digits=8, decimal_places=5, default=0)
    cpp_basic_exemption_annual = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cpp_max_pensionable_earnings = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # CPP2 settings
    cpp2_enabled = models.BooleanField(default=False)
    cpp2_rate_employee = models.DecimalField(max_digits=8, decimal_places=5, default=0)
    cpp2_rate_employer = models.DecimalField(max_digits=8, decimal_places=5, default=0)
    cpp2_max_additional_earnings = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # EI settings
    ei_enabled = models.BooleanField(default=True)
    ei_rate_employee = models.DecimalField(max_digits=8, decimal_places=5, default=0)
    ei_rate_employer_multiplier = models.DecimalField(max_digits=8, decimal_places=5, default=0)
    ei_max_insurable_earnings = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Tax settings are JSON to avoid hardcoding yearly rules.
    federal_tax_config = models.JSONField(default=dict, blank=True)
    provincial_tax_config = models.JSONField(default=dict, blank=True)

    # Default TD1 claims for the year.
    default_federal_td1_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    default_provincial_td1_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    note = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-year", "province")

    def __str__(self):
        return f"{self.year} Payroll Config ({self.province})"


class PayrollEmployee(models.Model):
    """
    Payroll profile for employees, officers, or founders.
    """

    TYPE_EMPLOYEE = "employee"
    TYPE_OFFICER = "officer"
    TYPE_DIRECTOR = "director"
    TYPE_CONTRACTOR = "contractor"

    EMPLOYMENT_TYPE_CHOICES = (
        (TYPE_EMPLOYEE, "Employee"),
        (TYPE_OFFICER, "Officer"),
        (TYPE_DIRECTOR, "Director"),
        (TYPE_CONTRACTOR, "Contractor"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payroll_profiles",
    )

    legal_first_name = models.CharField(max_length=100)
    legal_last_name = models.CharField(max_length=100)

    display_name = models.CharField(max_length=255)

    employment_type = models.CharField(
        max_length=30,
        choices=EMPLOYMENT_TYPE_CHOICES,
        default=TYPE_EMPLOYEE,
        db_index=True,
    )

    province_of_employment = models.CharField(max_length=2, default="BC")

    employment_start_date = models.DateField()
    employment_end_date = models.DateField(null=True, blank=True)

    # Store SIN carefully. Prefer external/encrypted storage later.
    sin_last3 = models.CharField(max_length=3, blank=True, default="")
    sin_reference = models.CharField(max_length=255, blank=True, default="")

    is_director = models.BooleanField(default=False)
    is_related_to_employer = models.BooleanField(default=False)

    cpp_exempt = models.BooleanField(
        default=False,
        verbose_name="CPP exempt",
        help_text=(
            "If checked, CPP will NOT be calculated for this employee. "
            "Leave unchecked when CPP should be deducted and remitted."
        ),
    )

    ei_exempt = models.BooleanField(
        default=False,
        verbose_name="EI exempt",
        help_text=(
            "If checked, EI will NOT be calculated for this employee. "
            "Use this when the employee is EI-exempt, such as certain related/employer-controlled situations."
        ),
    )

    income_tax_exempt = models.BooleanField(
        default=False,
        verbose_name="Income tax exempt",
        help_text=(
            "If checked, income tax will NOT be deducted from payroll. "
            "Leave unchecked for regular payroll income tax deductions."
        ),
    )

    federal_td1_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    provincial_td1_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True, default="")

    address_line1 = models.CharField(max_length=255, blank=True, default="")
    address_line2 = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    province = models.CharField(max_length=2, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="")
    country = models.CharField(max_length=2, default="CA")

    is_active = models.BooleanField(default=True)

    internal_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("legal_last_name", "legal_first_name")
        indexes = [
            models.Index(fields=["is_active", "employment_type"]),
            models.Index(fields=["province_of_employment"]),
        ]

    def __str__(self):
        return self.display_name or f"{self.legal_first_name} {self.legal_last_name}"


class PayrollCompensationPlan(models.Model):
    """
    Approved compensation plan for an employee.
    """

    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_CLOSED = "closed"
    PAY_TYPE_MONTHLY_SALARY = "monthly_salary"
    PAY_TYPE_HOURLY = "hourly"
    
    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_CLOSED, "Closed"),
    )
    PAY_TYPE_CHOICES = (
        (PAY_TYPE_MONTHLY_SALARY, "Monthly salary"),
        (PAY_TYPE_HOURLY, "Hourly"),
    )

    employee = models.ForeignKey(
        PayrollEmployee,
        on_delete=models.PROTECT,
        related_name="compensation_plans",
    )

    effective_from = models.DateField(db_index=True)
    effective_to = models.DateField(null=True, blank=True)

    pay_type = models.CharField(
        max_length=30,
        choices=PAY_TYPE_CHOICES,
        default=PAY_TYPE_MONTHLY_SALARY,
        db_index=True,
    )
    monthly_salary = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    hourly_rate = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    default_regular_hours_per_period = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Fallback regular hours for hourly employees when no work summary exists.",
    )

    daily_overtime_after_hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("8.00"),
    )

    daily_double_time_after_hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("12.00"),
    )

    weekly_overtime_after_hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("40.00"),
    )

    overtime_rate_multiplier = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=Decimal("1.500"),
    )

    double_time_rate_multiplier = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=Decimal("2.000"),
    )

    # Vacation can be accrued or paid each period.
    vacation_pay_enabled = models.BooleanField(default=True)
    vacation_pay_rate = models.DecimalField(
        max_digits=8,
        decimal_places=5,
        default=Decimal("0.04000"),
        help_text="Example: 0.04 means 4%.",
    )
    vacation_pay_mode = models.CharField(
        max_length=20,
        choices=(
            ("accrue", "Accrue"),
            ("pay_each_period", "Pay each period"),
        ),
        default="accrue",
    )

    # Sick leave can be tracked even if unpaid.
    sick_leave_enabled = models.BooleanField(default=True)

    board_resolution_date = models.DateField(null=True, blank=True)
    approval_reference = models.CharField(max_length=255, blank=True, default="")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)

    note = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_payroll_compensation_plans",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-effective_from", "-id")
        indexes = [
            models.Index(fields=["employee", "status"]),
            models.Index(fields=["effective_from", "effective_to"]),
        ]

    def __str__(self):
        return f"{self.employee} - {self.monthly_salary}/month"

    def clean(self):
        """
        Validate compensation plan.
        """

        super().clean()

        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError("effective_to cannot be earlier than effective_from.")

        if self.pay_type == self.PAY_TYPE_MONTHLY_SALARY:
            if self.monthly_salary <= Decimal("0.00"):
                raise ValidationError("monthly_salary is required for monthly salary plans.")

        if self.pay_type == self.PAY_TYPE_HOURLY:
            if self.hourly_rate <= Decimal("0.00"):
                raise ValidationError("hourly_rate is required for hourly plans.")

            if self.overtime_rate_multiplier < Decimal("1.000"):
                raise ValidationError("overtime_rate_multiplier must be at least 1.000.")

            if self.double_time_rate_multiplier < Decimal("1.000"):
                raise ValidationError("double_time_rate_multiplier must be at least 1.000.")


# -----------------------------------------------------------------------------
# Pay Schedule
# -----------------------------------------------------------------------------
class PaySchedule(models.Model):
    """
    Defines payroll frequency and payment timing.
    """

    FREQ_MONTHLY = "monthly"
    FREQ_SEMI_MONTHLY = "semi_monthly"
    FREQ_BI_WEEKLY = "bi_weekly"
    FREQ_WEEKLY = "weekly"

    FREQUENCY_CHOICES = (
        (FREQ_MONTHLY, "Monthly"),
        (FREQ_SEMI_MONTHLY, "Semi-monthly"),
        (FREQ_BI_WEEKLY, "Bi-weekly"),
        (FREQ_WEEKLY, "Weekly"),
    )

    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=255)

    frequency = models.CharField(max_length=30, choices=FREQUENCY_CHOICES, default=FREQ_MONTHLY)

    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code",)

    def __str__(self):
        return f"{self.code} - {self.name}"


class PayPeriod(models.Model):
    """
    One payroll period.
    """

    STATUS_OPEN = "open"
    STATUS_PROCESSING = "processing"
    STATUS_CLOSED = "closed"
    STATUS_LOCKED = "locked"

    STATUS_CHOICES = (
        (STATUS_OPEN, "Open"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_CLOSED, "Closed"),
        (STATUS_LOCKED, "Locked"),
    )

    schedule = models.ForeignKey(
        PaySchedule,
        on_delete=models.PROTECT,
        related_name="periods",
    )

    code = models.CharField(max_length=50, unique=True, db_index=True)

    tax_year = models.PositiveIntegerField(db_index=True)

    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)
    pay_date = models.DateField(db_index=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)

    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("start_date",)
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F("start_date")),
                name="pay_period_end_gte_start",
            ),
        ]

    def __str__(self):
        return f"{self.code} ({self.start_date} → {self.end_date})"


# -----------------------------------------------------------------------------
# Work Summary
# -----------------------------------------------------------------------------
class PayrollWorkSummary(models.Model):
    """
    Aggregated work hours for one employee and one pay period.

    Future attendance/time-clock systems will write summarized hours here.
    Payroll uses this model instead of reading raw time punches directly.
    """

    STATUS_DRAFT = "draft"
    STATUS_APPROVED = "approved"
    STATUS_LOCKED = "locked"

    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_LOCKED, "Locked"),
    )

    employee = models.ForeignKey(
        "PayrollEmployee",
        on_delete=models.PROTECT,
        related_name="work_summaries",
    )

    pay_period = models.ForeignKey(
        "PayPeriod",
        on_delete=models.PROTECT,
        related_name="work_summaries",
    )

    regular_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
    )

    daily_overtime_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
    )

    weekly_overtime_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
    )

    double_time_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
    )

    unpaid_break_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
    )

    source_app = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Example: attendance, time_clock, device_clock.",
    )

    source_model = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    source_ref = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )

    note = models.TextField(blank=True)

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_payroll_work_summaries",
    )

    approved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-pay_period__start_date", "employee__display_name")
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "pay_period"],
                name="uniq_payroll_work_summary_employee_period",
            )
        ]

    def __str__(self):
        return f"{self.employee.display_name} | {self.pay_period.code}"

    @property
    def total_hours(self):
        return (
            (self.regular_hours or Decimal("0.00"))
            + (self.daily_overtime_hours or Decimal("0.00"))
            + (self.weekly_overtime_hours or Decimal("0.00"))
            + (self.double_time_hours or Decimal("0.00"))
        )


# -----------------------------------------------------------------------------
# Pay Run
# -----------------------------------------------------------------------------
class PayRun(models.Model):
    """
    Payroll run for one pay period.
    """

    STATUS_DRAFT = "draft"
    STATUS_CALCULATED = "calculated"
    STATUS_APPROVED = "approved"
    STATUS_POSTED = "posted"
    STATUS_PAID = "paid"
    STATUS_VOID = "void"

    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_CALCULATED, "Calculated"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_POSTED, "Posted"),
        (STATUS_PAID, "Paid"),
        (STATUS_VOID, "Void"),
    )

    pay_period = models.ForeignKey(
        PayPeriod,
        on_delete=models.PROTECT,
        related_name="pay_runs",
    )

    payroll_year_config = models.ForeignKey(
        PayrollYearConfig,
        on_delete=models.PROTECT,
        related_name="pay_runs",
    )

    run_number = models.CharField(max_length=50, unique=True, db_index=True)

    run_date = models.DateField(db_index=True)

    description = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)

    total_gross_pay = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_employee_deductions = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_employer_contributions = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_net_pay = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_actual_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_salary_payable = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_remittance_due = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    journal_entry = models.ForeignKey(
        JournalEntry,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pay_runs",
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_pay_runs",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    posted_at = models.DateTimeField(null=True, blank=True)

    internal_note = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_pay_runs",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-run_date", "-id")
        indexes = [
            models.Index(fields=["status", "run_date"]),
            models.Index(fields=["pay_period", "status"]),
        ]

    def __str__(self):
        return f"{self.run_number} - {self.status}"


class PayStub(models.Model):
    """
    Payroll result for one employee in one pay run.
    """

    pay_run = models.ForeignKey(
        PayRun,
        on_delete=models.CASCADE,
        related_name="pay_stubs",
    )

    employee = models.ForeignKey(
        PayrollEmployee,
        on_delete=models.PROTECT,
        related_name="pay_stubs",
    )

    compensation_plan = models.ForeignKey(
        PayrollCompensationPlan,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="pay_stubs",
    )

    # Earned amounts
    gross_salary = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    vacation_pay_earned = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    vacation_pay_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sick_pay_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    taxable_benefits = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    pay_type = models.CharField(
        max_length=30,
        blank=True,
        default="monthly_salary",
        db_index=True,
    )

    hourly_rate = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    regular_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
    )

    daily_overtime_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
    )

    weekly_overtime_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
    )

    double_time_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
    )

    regular_pay = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    daily_overtime_pay = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    weekly_overtime_pay = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    double_time_pay = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    work_summary = models.ForeignKey(
        "PayrollWorkSummary",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pay_stubs",
    )
    pensionable_earnings = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    insurable_earnings = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    taxable_earnings = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Employee deductions
    employee_cpp = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    employee_cpp2 = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    employee_ei = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    federal_income_tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    provincial_income_tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    other_employee_deductions = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    total_employee_deductions = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Employer contributions
    employer_cpp = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    employer_cpp2 = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    employer_ei = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    other_employer_contributions = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    total_employer_contributions = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    net_pay = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Actual cash payment can be lower than net pay.
    actual_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_salary_payable = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Actual salary payment posting.
    salary_payment_journal_entry = models.ForeignKey(
        JournalEntry,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="salary_payment_pay_stubs",
    )

    salary_payment_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    salary_paid_on = models.DateField(null=True, blank=True)

    salary_payment_reference = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    
    total_remittance_due = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    payment_reference = models.CharField(max_length=255, blank=True, default="")
    payment_note = models.CharField(max_length=255, blank=True, default="")

    journal_entry = models.ForeignKey(
        JournalEntry,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pay_stubs",
    )

    calculation_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text="Stores calculation details for audit trail.",
    )

    PAYMENT_METHOD_E_TRANSFER = "e_transfer"
    PAYMENT_METHOD_DIRECT_DEPOSIT = "direct_deposit"
    PAYMENT_METHOD_CHEQUE = "cheque"
    PAYMENT_METHOD_CASH = "cash"
    PAYMENT_METHOD_OTHER = "other"

    PAYMENT_METHOD_CHOICES = (
        (PAYMENT_METHOD_E_TRANSFER, "E-Transfer"),
        (PAYMENT_METHOD_DIRECT_DEPOSIT, "Direct Deposit"),
        (PAYMENT_METHOD_CHEQUE, "Cheque"),
        (PAYMENT_METHOD_CASH, "Cash"),
        (PAYMENT_METHOD_OTHER, "Other"),
    )

    salary_payment_method = models.CharField(
        max_length=30,
        choices=PAYMENT_METHOD_CHOICES,
        blank=True,
        default="",
    )

    pay_stub_emailed_at = models.DateTimeField(null=True, blank=True)

    payment_confirmation_emailed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("pay_run", "employee__legal_last_name", "employee__legal_first_name")
        constraints = [
            models.UniqueConstraint(
                fields=["pay_run", "employee"],
                name="uniq_pay_stub_per_employee_per_run",
            )
        ]

    def __str__(self):
        return f"{self.employee} | {self.pay_run.run_number}"

    def clean(self):
        if self.actual_paid < ZERO:
            raise ValidationError("actual_paid cannot be negative.")

        if self.actual_paid > self.net_pay:
            raise ValidationError("actual_paid cannot exceed net_pay.")

        if self.net_salary_payable != (self.net_pay - self.actual_paid):
            raise ValidationError("net_salary_payable must equal net_pay minus actual_paid.")


# -----------------------------------------------------------------------------
# Payroll Salary Payment
# -----------------------------------------------------------------------------
class PayrollSalaryPayment(models.Model):
    """
    One actual salary payment made for a pay stub.
    Supports full or partial payments.
    """

    METHOD_E_TRANSFER = "e_transfer"
    METHOD_DIRECT_DEPOSIT = "direct_deposit"
    METHOD_CHEQUE = "cheque"
    METHOD_BANK_TRANSFER = "bank_transfer"
    METHOD_OTHER = "other"

    METHOD_CHOICES = (
        (METHOD_E_TRANSFER, "E-Transfer"),
        (METHOD_DIRECT_DEPOSIT, "Direct Deposit"),
        (METHOD_CHEQUE, "Cheque"),
        (METHOD_BANK_TRANSFER, "Bank Transfer"),
        (METHOD_OTHER, "Other"),
    )

    pay_stub = models.ForeignKey(
        PayStub,
        on_delete=models.PROTECT,
        related_name="salary_payments",
    )

    paid_on = models.DateField(db_index=True)

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    payment_method = models.CharField(
        max_length=30,
        choices=METHOD_CHOICES,
        default=METHOD_E_TRANSFER,
        db_index=True,
    )

    payment_reference = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
    )

    journal_entry = models.OneToOneField(
        "accounting.JournalEntry",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payroll_salary_payment_record",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_payroll_salary_payments",
    )

    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-paid_on", "-id")
        indexes = [
            models.Index(fields=["paid_on", "payment_method"]),
            models.Index(fields=["payment_reference"]),
        ]

    def __str__(self):
        return f"{self.pay_stub.employee.display_name} - {self.amount} on {self.paid_on}"
    
    
# -----------------------------------------------------------------------------
# Remittance
# -----------------------------------------------------------------------------
class PayrollRemittance(models.Model):
    """
    Payroll remittance payable to CRA.
    """

    STATUS_DRAFT = "draft"
    STATUS_READY = "ready"
    STATUS_PAID = "paid"
    STATUS_VOID = "void"

    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_READY, "Ready"),
        (STATUS_PAID, "Paid"),
        (STATUS_VOID, "Void"),
    )

    pay_run = models.OneToOneField(
        PayRun,
        on_delete=models.PROTECT,
        related_name="remittance",
    )

    due_date = models.DateField(db_index=True)

    employee_cpp = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    employer_cpp = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    employee_cpp2 = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    employer_cpp2 = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    employee_ei = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    employer_ei = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    federal_income_tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    provincial_income_tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    total_due = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    paid_on = models.DateField(null=True, blank=True)
    payment_reference = models.CharField(max_length=255, blank=True, default="")

    journal_entry = models.ForeignKey(
        JournalEntry,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payroll_remittances",
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)

    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-due_date", "-id")

    def __str__(self):
        return f"Remittance {self.pay_run.run_number} - {self.total_due}"


class PayrollLeavePolicy(models.Model):
    """
    Configurable leave policy for vacation/sick tracking.
    """

    TYPE_VACATION = "vacation"
    TYPE_SICK = "sick"
    TYPE_PERSONAL = "personal"
    TYPE_OTHER = "other"

    LEAVE_TYPE_CHOICES = (
        (TYPE_VACATION, "Vacation"),
        (TYPE_SICK, "Sick"),
        (TYPE_PERSONAL, "Personal"),
        (TYPE_OTHER, "Other"),
    )

    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=255)

    leave_type = models.CharField(max_length=30, choices=LEAVE_TYPE_CHOICES, db_index=True)

    province = models.CharField(max_length=2, default="BC")

    is_paid = models.BooleanField(default=False)

    # Keep rules configurable for yearly legal changes.
    accrual_config = models.JSONField(default=dict, blank=True)
    eligibility_config = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)

    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("province", "leave_type", "code")

    def __str__(self):
        return f"{self.code} - {self.name}"


class PayrollLeaveBalance(models.Model):
    """
    Leave balance per employee and leave policy.
    """

    employee = models.ForeignKey(
        PayrollEmployee,
        on_delete=models.PROTECT,
        related_name="leave_balances",
    )

    policy = models.ForeignKey(
        PayrollLeavePolicy,
        on_delete=models.PROTECT,
        related_name="balances",
    )

    year = models.PositiveIntegerField(db_index=True)

    opening_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    accrued_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    used_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    adjusted_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    closing_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    note = models.TextField(blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-year", "employee", "policy")
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "policy", "year"],
                name="uniq_leave_balance_employee_policy_year",
            )
        ]

    def __str__(self):
        return f"{self.employee} | {self.policy.code} | {self.year}"


class PayrollLeaveEntry(models.Model):
    """
    One leave usage/accrual/adjustment record.
    """

    TYPE_ACCRUAL = "accrual"
    TYPE_USAGE = "usage"
    TYPE_ADJUSTMENT = "adjustment"

    ENTRY_TYPE_CHOICES = (
        (TYPE_ACCRUAL, "Accrual"),
        (TYPE_USAGE, "Usage"),
        (TYPE_ADJUSTMENT, "Adjustment"),
    )

    employee = models.ForeignKey(
        PayrollEmployee,
        on_delete=models.PROTECT,
        related_name="leave_entries",
    )

    policy = models.ForeignKey(
        PayrollLeavePolicy,
        on_delete=models.PROTECT,
        related_name="entries",
    )

    entry_date = models.DateField(db_index=True)
    entry_type = models.CharField(max_length=30, choices=ENTRY_TYPE_CHOICES, db_index=True)

    hours = models.DecimalField(max_digits=10, decimal_places=2)

    pay_stub = models.ForeignKey(
        PayStub,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leave_entries",
    )

    note = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_payroll_leave_entries",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-entry_date", "-id")

    def __str__(self):
        return f"{self.employee} | {self.policy.code} | {self.entry_type} | {self.hours}"