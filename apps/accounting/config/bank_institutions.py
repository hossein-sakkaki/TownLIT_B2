# apps/accounting/config/bank_institutions.py

BANK_INSTITUTIONS = [
    {
        "code": "BMO",
        "name": "BMO Bank of Montreal",
        "institution_type": "bank",
        "country": "CA",
        "swift_code": "",
        "website": "https://www.bmo.com",
        "support_phone": "",
        "support_email": "",
        "note": "Primary banking institution for TownLIT",
    },
    {
        "code": "STRIPE",
        "name": "Stripe",
        "institution_type": "payment_processor",
        "country": "US",
        "swift_code": "",
        "website": "https://stripe.com",
        "support_phone": "",
        "support_email": "",
        "note": "Payment processor for subscriptions and online payments",
    },
    {
        "code": "PAYPAL",
        "name": "PayPal",
        "institution_type": "payment_processor",
        "country": "US",
        "swift_code": "",
        "website": "https://www.paypal.com",
        "support_phone": "",
        "support_email": "",
        "note": "Payment processor for online payments and transfers",
    },
]