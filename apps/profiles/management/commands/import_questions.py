from django.core.management.base import BaseCommand
from apps.profiles.models import SpiritualGift, SpiritualGiftSurveyQuestion
from apps.config.gift_questions_constants import QUESTIONS
from django.db import transaction


class Command(BaseCommand):
    help = 'Import questions for spiritual gifts survey'

    def handle(self, *args, **kwargs):
        with transaction.atomic():
            for q in QUESTIONS:
                gift, created = SpiritualGift.objects.get_or_create(name=q["gift"])

                for lang, question_text in q["question_text"].items():
                    SpiritualGiftSurveyQuestion.objects.create(
                        question_text=question_text,
                        question_number=q['question_number'],
                        language=lang,
                        options=q["options"],
                        gift=gift
                    )

            self.stdout.write(self.style.SUCCESS('Successfully imported questions'))