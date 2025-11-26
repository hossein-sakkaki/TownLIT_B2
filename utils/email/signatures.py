# utils/email/signatures.py
import random

SIGNATURES = [
    "With love and light,",
    "With care and peace,",
    "Grace and peace to you,",
    "With blessings and hope,",
    "Shining together in His light,",
    "Warmly in Christ,",
    "With gratitude and joy,",
    "Walking with you in faith,",
    "With warm regards,",
    "With heartfelt blessings,",
    "In His grace,",
    "With peace and compassion,",
    "Faithfully yours,",
    "Blessings to you today,",
    "With deep appreciation,",
    "With hope and courage,",
    "Rooted in love,",
    "Walking beside you,",
    "With strength and light,",
    "In fellowship and kindness,"
]

def pick_signature() -> str:
    """Return a random signature."""
    return random.choice(SIGNATURES)
