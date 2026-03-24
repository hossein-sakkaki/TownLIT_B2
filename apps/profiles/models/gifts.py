# apps/profiles/models/gifts.py

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.profiles.constants.gift_constants import (
    GIFT_CHOICES,
    GIFT_DESCRIPTIONS,
    GIFT_LANGUAGE_CHOICES,
    ANSWER_CHOICES,
)


class SpiritualGift(models.Model):
    name = models.CharField(max_length=100, choices=GIFT_CHOICES, verbose_name=_("Spiritual Gift Name"))
    description = models.TextField(verbose_name=_("Description"))

    class Meta:
        verbose_name = _("Spiritual Gift")
        verbose_name_plural = _("Spiritual Gifts")

    def __str__(self):
        return self.get_name_display()

    def save(self, *args, **kwargs):
        # Fill default description from constants.
        if not self.description:
            self.description = GIFT_DESCRIPTIONS.get(
                self.name,
                _("No description available"),
            )
        super().save(*args, **kwargs)


class SpiritualGiftSurveyQuestion(models.Model):
    question_text = models.CharField(max_length=500, verbose_name=_("Question Text"))
    question_number = models.IntegerField(verbose_name=_("Question Number"))
    language = models.CharField(max_length=10, choices=GIFT_LANGUAGE_CHOICES, verbose_name=_("Language"))
    options = models.JSONField(verbose_name=_("Options"))
    gift = models.ForeignKey(SpiritualGift, on_delete=models.CASCADE, verbose_name=_("Spiritual Gift"))

    class Meta:
        verbose_name = _("Spiritual Gift Survey Question")
        verbose_name_plural = _("Spiritual Gift Survey Questions")

    def __str__(self):
        return f"{self.question_text} ({self.language})"


class SpiritualGiftSurveyResponse(models.Model):
    id = models.BigAutoField(primary_key=True)
    member = models.ForeignKey("profiles.Member", on_delete=models.CASCADE, verbose_name=_("Member"))
    question = models.ForeignKey(
        SpiritualGiftSurveyQuestion,
        on_delete=models.CASCADE,
        verbose_name=_("Question"),
    )
    question_number = models.IntegerField(verbose_name=_("Question Number"))
    answer = models.IntegerField(choices=ANSWER_CHOICES, verbose_name=_("Answer"))

    class Meta:
        verbose_name = _("Spiritual Gift Survey Response")
        verbose_name_plural = _("Spiritual Gift Survey Responses")

    def __str__(self):
        return f"Response by {self.member} for question {self.question.id}"


class MemberSurveyProgress(models.Model):
    id = models.BigAutoField(primary_key=True)
    member = models.OneToOneField("profiles.Member", on_delete=models.CASCADE, verbose_name=_("Member"))
    current_question = models.IntegerField(default=1, verbose_name=_("Current Question"))
    answered_questions = models.JSONField(default=list, verbose_name=_("Answered Questions"))
    incomplete_survey = models.BooleanField(default=False, verbose_name=_("Incomplete Survey"))

    class Meta:
        verbose_name = _("Member Survey Progress")
        verbose_name_plural = _("Member Survey Progresses")

    def __str__(self):
        return f"Survey progress for {self.member.user.username}"


class MemberSpiritualGifts(models.Model):
    id = models.BigAutoField(primary_key=True)
    member = models.OneToOneField("profiles.Member", on_delete=models.CASCADE, verbose_name=_("Member"))
    gifts = models.ManyToManyField(SpiritualGift, verbose_name=_("Spiritual Gifts"))
    survey_results = models.JSONField(verbose_name=_("Survey Results"))
    created_at = models.DateTimeField(default=timezone.now, verbose_name=_("Created At"))

    class Meta:
        verbose_name = _("User Spiritual Gifts")
        verbose_name_plural = _("User Spiritual Gifts")

    def __str__(self):
        return f"Spiritual Gifts of {self.member}"