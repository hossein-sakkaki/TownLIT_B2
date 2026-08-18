# apps/bookstore_inventory/constants.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django.db import models


class BookType(models.TextChoices):
    BIBLE = "bible", "Bible"
    NEW_TESTAMENT = "new_testament", "New Testament"
    CHRISTIAN_BOOK = "christian_book", "Christian Book"
    GENERAL_BOOK = "general_book", "General Book"
    STUDY_GUIDE = "study_guide", "Study Guide"
    MAGAZINE = "magazine", "Magazine"
    BOOKLET = "booklet", "Booklet"
    OTHER = "other", "Other"


class ContributorRole(models.TextChoices):
    AUTHOR = "author", "Author"
    TRANSLATOR = "translator", "Translator"
    EDITOR = "editor", "Editor"
    COMPILER = "compiler", "Compiler"
    ILLUSTRATOR = "illustrator", "Illustrator"
    OTHER = "other", "Other"


class CopyrightStatus(models.TextChoices):
    OWNED = "owned", "Owned"
    LICENSED = "licensed", "Licensed"
    PUBLIC_DOMAIN = "public_domain", "Public Domain"
    UNKNOWN = "unknown", "Unknown"


class FormatType(models.TextChoices):
    PAPERBACK = "paperback", "Paperback"
    HARDCOVER = "hardcover", "Hardcover"
    BOOKLET = "booklet", "Booklet"
    DIGITAL = "digital", "Digital"
    OTHER = "other", "Other"


class PricingMode(models.TextChoices):
    FREE = "free", "Free"
    FIXED_PRICE = "fixed_price", "Fixed price"
    DONATION = "donation", "Donation"
    FIXED_PLUS_DONATION = "fixed_plus_donation", "Fixed + Donation"


class OrganizationRoleType(models.TextChoices):
    PUBLISHER = "publisher", "Publisher"
    PRINTER = "printer", "Printer"
    SUPPLIER = "supplier", "Supplier"
    DONOR = "donor", "Donor"
    DISTRIBUTOR = "distributor", "Distributor"
    LIBRARY = "library", "Library"
    MINISTRY = "ministry", "Ministry"
    CHURCH = "church", "Church"
    RIGHTS_HOLDER = "rights_holder", "Rights holder"
    CONSIGNMENT_PARTNER = "consignment_partner", "Consignment partner"
    CUSTOMER = "customer", "Customer / recipient"
    OTHER = "other", "Other"


class ProfileLinkStatus(models.TextChoices):
    PENDING = "pending", "Pending verification"
    VERIFIED = "verified", "Verified"
    REJECTED = "rejected", "Rejected"
    UNLINKED = "unlinked", "Unlinked"


class InboundSourceType(models.TextChoices):
    PURCHASE = "purchase", "Purchase"
    DONATION = "donation", "Donation"
    CONSIGNMENT = "consignment", "Consignment"
    INTERNAL_PRINT = "internal_print", "Internal print"
    RETURN = "return", "Return"
    OTHER = "other", "Other"


class InboundPaymentStatus(models.TextChoices):
    NOT_REQUIRED = "not_required", "Not required"
    UNPAID = "unpaid", "Unpaid"
    PARTIAL = "partial", "Partial"
    PAID = "paid", "Paid"
    PAY_AFTER_SALE = "pay_after_sale", "Pay after sale"


class InventoryCondition(models.TextChoices):
    NEW = "new", "New"
    GOOD = "good", "Good"
    DAMAGED = "damaged", "Damaged"
    DISPLAY = "display", "Display copy"
    QUARANTINED = "quarantined", "Quarantined"
    UNSELLABLE = "unsellable", "Unsellable"


class LocationType(models.TextChoices):
    ZONE = "zone", "Zone"
    AISLE = "aisle", "Aisle"
    SHELF = "shelf", "Shelf"
    BIN = "bin", "Bin"
    STAGING = "staging", "Staging area"
    OTHER = "other", "Other"


class WarehouseStaffRole(models.TextChoices):
    PRIMARY_MANAGER = "primary_manager", "Primary manager"
    MANAGER = "manager", "Manager"
    OPERATOR = "operator", "Operator"
    AUDITOR = "auditor", "Read-only auditor"


class InboundPaymentScheduleStatus(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    PARTIAL = "partial", "Partially paid"
    PAID = "paid", "Paid"


class StockMovementType(models.TextChoices):
    IN = "in", "Stock in"
    OUT = "out", "Stock out"
    SALE = "sale", "Sale"
    GIFT = "gift", "Gift"
    DONATION_DISTRIBUTION = "donation_distribution", "Donation distribution"
    RETURN_IN = "return_in", "Return in"
    RETURN_OUT = "return_out", "Return out"
    ADJUSTMENT_PLUS = "adjustment_plus", "Adjustment plus"
    ADJUSTMENT_MINUS = "adjustment_minus", "Adjustment minus"
    DAMAGED = "damaged", "Damaged"
    LOST = "lost", "Lost"
    TRANSFER_IN = "transfer_in", "Transfer in"
    TRANSFER_OUT = "transfer_out", "Transfer out"


class DocumentStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    CONFIRMED = "confirmed", "Confirmed"
    POSTED = "posted", "Posted"
    CANCELLED = "cancelled", "Cancelled"


class ReservationStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    CONSUMED = "consumed", "Consumed"
    RELEASED = "released", "Released"
    EXPIRED = "expired", "Expired"


class TransferStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    DISPATCHED = "dispatched", "Dispatched"
    RECEIVED = "received", "Received"
    CANCELLED = "cancelled", "Cancelled"


class StockCountStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    COUNTING = "counting", "Counting"
    SUBMITTED = "submitted", "Submitted"
    POSTED = "posted", "Posted"
    CANCELLED = "cancelled", "Cancelled"


class AdjustmentReason(models.TextChoices):
    COUNT_VARIANCE = "count_variance", "Stock-count variance"
    DAMAGE = "damage", "Damage"
    LOSS = "loss", "Loss"
    FOUND = "found", "Found stock"
    DATA_CORRECTION = "data_correction", "Data correction"
    OTHER = "other", "Other"


class ReturnDirection(models.TextChoices):
    CUSTOMER_TO_STOCK = "customer_to_stock", "Customer return to stock"
    STOCK_TO_SUPPLIER = "stock_to_supplier", "Return to supplier"


class OrderType(models.TextChoices):
    SALE = "sale", "Sale"
    FREE_DISTRIBUTION = "free_distribution", "Free distribution"
    DONATION_BASED = "donation_based", "Donation based"
    INTERNAL_TRANSFER = "internal_transfer", "Internal transfer"
    PROMOTIONAL = "promotional", "Promotional"


class OrderStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    CONFIRMED = "confirmed", "Confirmed"
    FULFILLED = "fulfilled", "Fulfilled"
    CANCELLED = "cancelled", "Cancelled"


class PaymentStatus(models.TextChoices):
    UNPAID = "unpaid", "Unpaid"
    PARTIAL = "partial", "Partial"
    PAID = "paid", "Paid"
    REFUNDED = "refunded", "Refunded"


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Cash"
    CARD = "card", "Card"
    TRANSFER = "transfer", "Transfer"
    ETRANSFER = "etransfer", "e-Transfer"
    PAYPAL = "paypal", "PayPal"
    STRIPE = "stripe", "Stripe"
    MANUAL = "manual", "Manual"


class CashEntryDirection(models.TextChoices):
    IN = "in", "Cash in"
    OUT = "out", "Cash out"


class CashEntryType(models.TextChoices):
    SALES_INCOME = "sales_income", "Sales income"
    DONATION_INCOME = "donation_income", "Donation income"
    PURCHASE_PAYMENT = "purchase_payment", "Purchase payment"
    SHIPPING_EXPENSE = "shipping_expense", "Shipping expense"
    REFUND = "refund", "Refund"
    MANUAL = "manual", "Manual"


class RecipientType(models.TextChoices):
    PERSON = "person", "Person"
    ORGANIZATION = "organization", "Organization"


class DeliveryMethod(models.TextChoices):
    PICKUP = "pickup", "Pickup"
    SHIPPING = "shipping", "Shipping"
    HAND_DELIVERY = "hand_delivery", "Hand delivery"
    INTERNAL_TRANSFER = "internal_transfer", "Internal transfer"


class OrderPurpose(models.TextChoices):
    PERSONAL_SALE = "personal_sale", "Personal sale"
    ORGANIZATION_SALE = "organization_sale", "Organization sale"
    DONATION = "donation", "Donation"
    CHURCH_SUPPORT = "church_support", "Church support"
    EVENT_DISTRIBUTION = "event_distribution", "Event distribution"
    INTERNAL_USE = "internal_use", "Internal use"
    PROMOTIONAL = "promotional", "Promotional"
    OTHER = "other", "Other"


STOCK_IN_TYPES = {
    StockMovementType.IN, StockMovementType.RETURN_IN,
    StockMovementType.ADJUSTMENT_PLUS, StockMovementType.TRANSFER_IN,
}
STOCK_OUT_TYPES = {
    StockMovementType.OUT, StockMovementType.SALE, StockMovementType.GIFT,
    StockMovementType.DONATION_DISTRIBUTION, StockMovementType.RETURN_OUT,
    StockMovementType.ADJUSTMENT_MINUS, StockMovementType.DAMAGED,
    StockMovementType.LOST, StockMovementType.TRANSFER_OUT,
}
