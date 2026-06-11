// apps/accounting/static/accounting/admin/payroll_compensation_plan.js

(function () {
  function toggleCompensationFields() {
    const payTypeSelect = document.getElementById("id_pay_type");
    if (!payTypeSelect) return;

    const payType = payTypeSelect.value;

    const monthlyRows = [
      "monthly_salary",
    ];

    const hourlyRows = [
      "hourly_rate",
      "default_regular_hours_per_period",
    ];

    const overtimeRows = [
      "daily_overtime_after_hours",
      "daily_double_time_after_hours",
      "weekly_overtime_after_hours",
      "overtime_rate_multiplier",
      "double_time_rate_multiplier",
    ];

    function setVisible(fieldName, visible) {
      const field = document.getElementById("id_" + fieldName);
      if (!field) return;

      const row = field.closest(".form-row");
      if (!row) return;

      row.style.display = visible ? "" : "none";
    }

    monthlyRows.forEach(function (fieldName) {
      setVisible(fieldName, payType === "monthly_salary");
    });

    hourlyRows.forEach(function (fieldName) {
      setVisible(fieldName, payType === "hourly");
    });

    // Overtime rules are useful only for hourly plans.
    overtimeRows.forEach(function (fieldName) {
      setVisible(fieldName, payType === "hourly");
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    const payTypeSelect = document.getElementById("id_pay_type");

    if (payTypeSelect) {
      payTypeSelect.addEventListener("change", toggleCompensationFields);
      toggleCompensationFields();
    }
  });
})();