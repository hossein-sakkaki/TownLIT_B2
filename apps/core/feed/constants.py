# apps/core/feed/constants.py

from datetime import timedelta

# ------------------------------
# Base weights
# ------------------------------
REACTIONS_WEIGHT = 1.0
COMMENTS_WEIGHT = 2.0
RECOMMENTS_WEIGHT = 1.0

# ------------------------------
# Time decay
# ------------------------------
TIME_DECAY_HOURS = 36  # feed half-life

# ------------------------------
# Safety caps (anti-spam)
# ------------------------------
MAX_REACTIONS_EFFECT = 500
MAX_COMMENTS_EFFECT = 200

# =====================================================
# Trending configuration
# =====================================================
# Windows (seconds)
TRENDING_WINDOW_24H = 24 * 60 * 60
TRENDING_WINDOW_7D = 7 * 24 * 60 * 60

# ✅ Phase-1: use 6 months so Square doesn't go empty
TRENDING_WINDOW_6M = int(timedelta(days=183).total_seconds())
TRENDING_WINDOW_DEFAULT = TRENDING_WINDOW_6M  # tweak later

# Weights
TREND_REACTIONS_WEIGHT = 1.0
TREND_COMMENTS_WEIGHT = 2.0
TREND_RECOMMENTS_WEIGHT = 1.5

# Velocity boost
TREND_VELOCITY_MULTIPLIER = 1.8

# Caps (anti-gaming)
TREND_MAX_REACTIONS = 300
TREND_MAX_COMMENTS = 150

# =====================================================
# Hybrid feed weights
# =====================================================
HYBRID_FEED_WEIGHT = 0.65
HYBRID_TREND_WEIGHT = 0.35

# Relationship boosts
HYBRID_FRIEND_BOOST = 1.2
HYBRID_COVENANT_BOOST = 1.4

# ✅ Do not drop content in early phase
HYBRID_MIN_SCORE = 0.0

# ✅ Only "activate" trend blending after enough engagement exists
HYBRID_ENABLE_MIN_ENGAGEMENT = 3  # reactions+comments+recomments

# =====================================================
# Personalized trending
# =====================================================
PERSONAL_TREND_FRIEND_WEIGHT = 1.5
PERSONAL_TREND_COVENANT_WEIGHT = 2.0
PERSONAL_TREND_SELF_WEIGHT = 2.5
PERSONAL_TREND_GLOBAL_WEIGHT = 1.0

# ✅ Do not drop content in early phase
PERSONAL_TREND_MIN_SCORE = 0.0

# ✅ Avoid empty for-you in early phase
PERSONAL_TREND_ENABLE_MIN_ENGAGEMENT = 3
