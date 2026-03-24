# apps/profiles/constants/identity.py

# Identity Verification Status Types ---------------------------------------------------------------
NOT_SUBMITTED = 'not_submitted'
PENDING_REVIEW = 'pending_review'
VERIFIED = 'verified'
REJECTED = 'rejected'
IDENTITY_VERIFICATION_STATUS_CHOICES = [
    (NOT_SUBMITTED, 'Not Submitted'),
    (PENDING_REVIEW, 'Pending Review'),
    (VERIFIED, 'Verified'),
    (REJECTED, 'Rejected'),
]