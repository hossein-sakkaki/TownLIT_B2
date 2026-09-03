# apps/subscriptions/models/trial.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-28.
# Last Update by Hossein Sakkaki on 2026-08-28.
#

from django.db import models


class SubscriptionTrialUsage(models.Model):
    id = models.BigAutoField(primary_key=True)
    account = models.ForeignKey(
        "subscriptions.SubscriptionAccount",
        on_delete=models.CASCADE,
        related_name="trial_usages",
    )
    trial_key = models.SlugField(max_length=80, db_index=True)
    subscription = models.OneToOneField(
        "subscriptions.Subscription",
        on_delete=models.PROTECT,
        related_name="trial_usage",
    )

    started_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Subscription Trial Usage"
        verbose_name_plural = "Subscription Trial Usages"
        constraints = [
            models.UniqueConstraint(
                fields=["account", "trial_key"],
                name="subscriptions_unique_trial_usage_per_account_key",
            ),
        ]
        indexes = [
            models.Index(fields=["account", "trial_key"]),
        ]

    def __str__(self):
        return f"{self.account_id}:{self.trial_key}"
