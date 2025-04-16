# PAYMENT STATUS Choices -------------------------------------------------------------
PENDING = 'pending'
SUCCESS = 'success'
FAILED = 'failed'
PAYMENT_STATUS_CHOICES = [
    (PENDING, 'Pending'),
    (SUCCESS, 'Success'),
    (FAILED, 'Failed'),
]


# SUBSCRIPTION TYPE Choices -----------------------------------------------------------
MONTHLY = 'monthly'
YEARLY = 'yearly'
SUBSCRIPTION_TYPE_CHOICES = [
    (MONTHLY, 'Monthly'),
    (YEARLY, 'Yearly'),
]


# SUBSCRIPTION PRICING TYPE Choices ---------------------------------------------------
ONE_TIME = 'one_time'
RECURRING = 'recurring'
DISCOUNTED_YEARLY = 'discounted_yearly'

SUBSCRIPTION_PRICING_TYPE_CHOICES = [
    (ONE_TIME, 'One-Time'),
    (RECURRING, 'Recurring'),
    (DISCOUNTED_YEARLY, 'Discounted Yearly'),
]


# ADVERTISEMENT TYPE Choices ----------------------------------------------------------
VIDEO = 'video'
BANNER = 'banner'
POPUP = 'popup'
SIDEBAR = 'sidebar'
ADVERTISEMENT_TYPE_CHOICES = [
    (VIDEO, 'Video Advertisement'),
    (BANNER, 'Banner Advertisement'),
    (POPUP, 'Popup Advertisement'),
    (SIDEBAR, 'Sidebar Advertisement'),
]



# PRICING TYPE Choices ----------------------------------------------------------
PRICING_TYPE_SUBSCRIPTION = 'subscription'
PRICING_TYPE_ADVERTISEMENT = 'advertisement'
PRICING_TYPE_CHOICES = [
    (PRICING_TYPE_SUBSCRIPTION, 'Subscription'),
    (PRICING_TYPE_ADVERTISEMENT, 'Advertisement')
    ]


# SUBSCRIPTION TYPE Choices ----------------------------------------------------------
SUBSCRIPTION_TYPE_BASIC = 'basic'
SUBSCRIPTION_TYPE_PREMIUM = 'premium'
SUBSCRIPTION_TYPE_PRO = 'pro'
SUBSCRIPTION_TYPE_CHOICES = [
    (SUBSCRIPTION_TYPE_BASIC, 'Basic'),
    (SUBSCRIPTION_TYPE_PREMIUM, 'Premium'),
    (SUBSCRIPTION_TYPE_PRO, 'Pro')
]


# ADVERTISEMENT TYPE Choices ----------------------------------------------------------
ADVERTISEMENT_TYPE_VIDEO = 'video'
ADVERTISEMENT_TYPE_BANNER = 'banner'
ADVERTISEMENT_TYPE_POPUP = 'popup'
ADVERTISEMENT_TYPE_SIDEBAR = 'sidebar'
ADVERTISEMENT_TYPE_CHOICES = [
    (ADVERTISEMENT_TYPE_VIDEO, 'Video'),
    (ADVERTISEMENT_TYPE_BANNER, 'Banner'),
    (ADVERTISEMENT_TYPE_POPUP, 'Pop-Up'),
    (ADVERTISEMENT_TYPE_SIDEBAR, 'Sidebar')
]


# DURATION Choices ----------------------------------------------------------
DURATION_DAILY = 'daily'
DURATION_MONTHLY = 'monthly'
DURATION_YEARLY = 'yearly'
DURATION_CHOICES = [
    (DURATION_DAILY, 'Daily'),
    (DURATION_MONTHLY, 'Monthly'),
    (DURATION_YEARLY, 'Yearly')
]


# BILLING CYCLE Choices ----------------------------------------------------------
BILLING_CYCLE_ONE_TIME = 'one_time'
BILLING_CYCLE_RECURRING_INDEFINITE = 'recurring_indefinite'
BILLING_CYCLE_RECURRING_UNTIL = 'recurring_until'
BILLING_CYCLE_CHOICES = [
    (BILLING_CYCLE_ONE_TIME, 'One-Time'),
    (BILLING_CYCLE_RECURRING_INDEFINITE, 'Recurring Indefinitely'),
    (BILLING_CYCLE_RECURRING_UNTIL, 'Recurring Until Date')
]