// static/bookstore_inventory/admin/js/book_order_admin.js

(function () {
  function toggleSections() {
    const recipientTypeField = document.getElementById("id_recipient_type");
    const deliveryMethodField = document.getElementById("id_delivery_method");

    const personSection = document.querySelector(".book-order-person-section");
    const organizationSection = document.querySelector(".book-order-organization-section");
    const destinationSection = document.querySelector(".book-order-destination-section");

    if (!recipientTypeField) return;

    const recipientType = recipientTypeField.value;
    const deliveryMethod = deliveryMethodField ? deliveryMethodField.value : null;

    if (personSection) {
      personSection.style.display = recipientType === "person" ? "" : "none";
    }

    if (organizationSection) {
      organizationSection.style.display = recipientType === "organization" ? "" : "none";
    }

    if (destinationSection) {
      destinationSection.style.display =
        deliveryMethod === "shipping" || deliveryMethod === "hand_delivery" ? "" : "none";
    }

    const addressLine1 = document.getElementById("id_address_line_1");
    if (addressLine1) {
      if (deliveryMethod === "shipping") {
        addressLine1.setAttribute("required", "required");
      } else {
        addressLine1.removeAttribute("required");
      }
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    toggleSections();

    const recipientTypeField = document.getElementById("id_recipient_type");
    const deliveryMethodField = document.getElementById("id_delivery_method");

    if (recipientTypeField) {
      recipientTypeField.addEventListener("change", toggleSections);
    }

    if (deliveryMethodField) {
      deliveryMethodField.addEventListener("change", toggleSections);
    }
  });
})();