# utils/email/notification_respect_lines.py
import random

NOTIFICATION_RESPECT_LINES = [
    "We respect your time and attention, and you can adjust what you receive anytime in your account settings.",
    "Your peace matters to us — feel free to tailor your notifications whenever you wish.",
    "We aim to keep things meaningful, and you’re welcome to fine-tune your preferences at any moment.",
    "TownLIT wants to support you, not overwhelm you. You can update your notification choices whenever you like.",
    "Your experience should feel calm and personal — you can refine your preferences anytime in your settings.",
    "We keep things simple and respectful. If you ever want to change what you receive, it’s always available in your settings.",
    "Your comfort guides our design. You can review or update your notification preferences whenever it suits you.",
    "You choose what matters most to you — and you can adjust these choices anytime in your account settings.",
    "Your attention is valuable. Whenever you wish, you can revisit your notification preferences and make changes.",
    "Stay connected in a way that feels right for you. You’re free to manage or update your preferences anytime.",
]


def pick_respect_line() -> str:
    return random.choice(NOTIFICATION_RESPECT_LINES)
