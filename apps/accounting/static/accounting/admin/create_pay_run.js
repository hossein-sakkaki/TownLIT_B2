// apps/accounting/static/accounting/admin/create_pay_run.js

(function () {
  function setVisible(fieldName, visible) {
    const field = document.getElementById("id_" + fieldName);
    if (!field) return;

    const row = field.closest(".form-row");
    if (!row) return;

    row.style.display = visible ? "" : "none";
  }

  function toggleHourlyFields() {
    const hourlyToggle = document.getElementById("id_show_hourly_fields");

    const hourlyFields = [
      "regular_hours",
      "daily_overtime_hours",
      "weekly_overtime_hours",
      "double_time_hours",
    ];

    const visible = hourlyToggle && hourlyToggle.checked;

    hourlyFields.forEach(function (fieldName) {
      setVisible(fieldName, visible);
    });
  }

  function toggleOverrideFields() {
    const overrideToggle = document.getElementById("id_use_manual_overrides");

    const overrideFields = [
      "employee_cpp",
      "employer_cpp",
      "employee_cpp2",
      "employer_cpp2",
      "employee_ei",
      "employer_ei",
      "federal_income_tax",
      "provincial_income_tax",
      "override_source",
      "override_note",
    ];

    const visible = overrideToggle && overrideToggle.checked;

    overrideFields.forEach(function (fieldName) {
      setVisible(fieldName, visible);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    const hourlyToggle = document.getElementById("id_show_hourly_fields");
    const overrideToggle = document.getElementById("id_use_manual_overrides");

    if (hourlyToggle) {
      hourlyToggle.addEventListener("change", toggleHourlyFields);
    }

    if (overrideToggle) {
      overrideToggle.addEventListener("change", toggleOverrideFields);
    }

    toggleHourlyFields();
    toggleOverrideFields();
  });
})();