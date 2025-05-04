import random
import string
from apps.accounts.models import InviteCode
from apps.accounts.scripts.utils.invite_words import BIBLE_WORDS

def generate_invite_code():
    word = random.choice(BIBLE_WORDS)
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return f"{prefix}_{word}_{suffix}"
