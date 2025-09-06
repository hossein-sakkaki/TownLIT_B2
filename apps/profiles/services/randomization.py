# apps/friendship/services/randomization.py
import random
from django.utils import timezone

def make_day_seed() -> str:
    return timezone.localdate().strftime("%Y%m%d")

def shuffle_list(items, seed: str | None = None):
    a = list(items)
    rnd = random.Random(seed) if seed is not None else random
    rnd.shuffle(a)
    return a
