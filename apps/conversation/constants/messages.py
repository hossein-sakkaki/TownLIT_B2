# apps/conversation/constants/messages.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

PIN_NONE = "none"
PIN_1_HOUR = "1_hour"
PIN_24_HOURS = "24_hours"
PIN_1_WEEK = "1_week"
PIN_1_MONTH = "1_month"
PIN_3_MONTHS = "3_months"

MESSAGE_PIN_DURATION_CHOICES = [
    (PIN_NONE, "No Expiry"),
    (PIN_1_HOUR, "1 Hour"),
    (PIN_24_HOURS, "24 Hours"),
    (PIN_1_WEEK, "1 Week"),
    (PIN_1_MONTH, "1 Month"),
    (PIN_3_MONTHS, "3 Months"),
]

MSG_LIKE = "like"
MSG_DISLIKE = "dislike"
MSG_GRATITUDE = "gratitude"
MSG_HEART = "heart"
MSG_ENCOURAGEMENT = "encouragement"

MESSAGE_REACTION_TYPE_CHOICES = [
    (MSG_LIKE, "Like"),
    (MSG_DISLIKE, "Dislike"),
    (MSG_GRATITUDE, "Gratitude"),
    (MSG_HEART, "Heart"),
    (MSG_ENCOURAGEMENT, "Encouragement"),
]
