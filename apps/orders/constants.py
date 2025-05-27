# Constants for Order Status choices ----------------------------------------
PENDING = 'pending'
CONFIRMED = 'confirmed'
SHIPPED = 'shipped'
DELIVERED = 'delivered'
CANCELLED = 'cancelled'
RETURNED = 'returned'
ORDER_STATUS_CHOICES = [
    (PENDING, 'Pending'),
    (CONFIRMED, 'Confirmed'),
    (SHIPPED, 'Shipped'),
    (DELIVERED, 'Delivered'),
    (CANCELLED, 'Cancelled'),
    (RETURNED, 'Returned'),
]


# DELIVERY ORDER STATUS Choices ----------------------------------------------
DELIVERY_AWAITING_HELP = 'awaiting_help'
DELIVERY_IN_PAYMENT = 'in_payment' 
DELIVERY_IN_TRANSIT = 'in_transit'
DELIVERY_DELIVERED = 'delivered'
DELIVERY_PAID = 'paid'
DELIVERY_CANCELLED = 'cancelled'
DELIVERY_ORDER_STATUS_CHOICES = [
    (DELIVERY_AWAITING_HELP, 'Awaiting Help'),
    (DELIVERY_IN_PAYMENT, 'In Payment'),
    (DELIVERY_IN_TRANSIT, 'In Transit'),
    (DELIVERY_DELIVERED, 'Delivered'),
    (DELIVERY_PAID, 'Paid'),
    (DELIVERY_CANCELLED, 'Cancelled'),
]


# RETURN ORDER STATUS Choices ------------------------------------------------
PENDING = 'pending'
APPROVED = 'approved'
REJECTED = 'rejected'
RETURN_ORDER_STATUS_CHOICES = [
    (PENDING, 'Pending'),
    (APPROVED, 'Approved'),
    (REJECTED, 'Rejected'),
]