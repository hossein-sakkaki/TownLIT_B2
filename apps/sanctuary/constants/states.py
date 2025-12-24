# apps/sanctuary/constants/states.py
# ============================================================
# REQUEST / REVIEW / OUTCOME STATES
# ============================================================

# Request lifecycle
PENDING = 'pending'
UNDER_REVIEW = 'under_review'
RESOLVED = 'resolved'
REJECTED = 'rejected'

REQUEST_STATUS_CHOICES = [
    (PENDING, 'Pending'),
    (UNDER_REVIEW, 'Under Review'),
    (RESOLVED, 'Resolved'),
    (REJECTED, 'Rejected'),
]

# Review votes
NO_OPINION = 'no_opinion'
VIOLATION_CONFIRMED = 'violation_confirmed'
VIOLATION_REJECTED = 'violation_rejected'

REVIEW_STATUS_CHOICES = [
    (NO_OPINION, 'No Opinion'),
    (VIOLATION_CONFIRMED, 'Violation Confirmed'),
    (VIOLATION_REJECTED, 'Violation Rejected'),
]

# Final outcome
OUTCOME_CONFIRMED = 'outcome_confirmed'
OUTCOME_REJECTED = 'outcome_rejected'
OUTCOME_PENDING = 'outcome_pending'

OUTCOME_CHOICES = [
    (OUTCOME_CONFIRMED, 'Confirmed'),
    (OUTCOME_REJECTED, 'Rejected'),
    (OUTCOME_PENDING, 'Pending'),
]
