# apps/accounts/models/trust.py

from django.conf import settings
from django.db import models


class UserTrustScore(models.Model):
    """
    Stores verification eligibility score for each user.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="trust_score",
    )

    score = models.IntegerField(default=0)
    eligible_for_verification = models.BooleanField(default=False)
    last_calculated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Trust Score"
        verbose_name_plural = "User Trust Scores"

    def __str__(self):
        return f"user={self.user_id} score={self.score}"