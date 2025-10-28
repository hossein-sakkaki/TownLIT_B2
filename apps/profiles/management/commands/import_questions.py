from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from apps.profiles.models import SpiritualGift, SpiritualGiftSurveyQuestion
from apps.profiles.gift_questions_constants import QUESTIONS


class Command(BaseCommand):
    help = "Import/Upsert spiritual gifts survey questions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Delete all existing questions, then import from scratch.",
        )
        parser.add_argument(
            "--sync-delete-missing",
            action="store_true",
            help="After upsert, delete questions not present in the QUESTIONS input.",
        )

    def handle(self, *args, **options):
        do_replace = options.get("replace", False)
        do_sync_delete = options.get("--sync-delete-missing", False) or options.get("sync_delete_missing", False)

        # Build a set of unique keys (question_number, language) from input
        incoming_keys = set()
        for q in QUESTIONS:
            qnum = int(q["question_number"])
            for lang in q["question_text"].keys():
                incoming_keys.add((qnum, lang))

        with transaction.atomic():
            if do_replace:
                # Hard reset: delete everything first
                SpiritualGiftSurveyQuestion.objects.all().delete()
                self.stdout.write(self.style.WARNING("All existing questions deleted."))

            # Main upsert loop
            for q in QUESTIONS:
                gift_name = str(q["gift"])  # must match choices on SpiritualGift.name
                gift, _ = SpiritualGift.objects.get_or_create(name=gift_name)

                qnum = int(q["question_number"])
                options_list = list(q["options"])  # e.g., [1,2,3,4,5,6,7]

                for lang, question_text in q["question_text"].items():
                    # Ensure we don't have duplicate rows for the same unique key
                    # (If historical duplicates exist, keep latest after update_or_create.)
                    duplicates = SpiritualGiftSurveyQuestion.objects.filter(
                        question_number=qnum, language=lang
                    ).order_by("id")
                    if duplicates.count() > 1:
                        # Keep last, delete older ones
                        to_delete = duplicates.values_list("id", flat=True)[:-1]
                        SpiritualGiftSurveyQuestion.objects.filter(id__in=to_delete).delete()

                    # Upsert by (question_number, language)
                    SpiritualGiftSurveyQuestion.objects.update_or_create(
                        question_number=qnum,
                        language=lang,
                        defaults={
                            "question_text": question_text,
                            "options": options_list,
                            "gift": gift,
                        },
                    )

            # Optional sync: delete records not present in current QUESTIONS
            if do_sync_delete:
                q_filter = Q()
                # Build OR filter matching incoming keys
                for (qnum, lang) in incoming_keys:
                    q_filter |= (Q(question_number=qnum) & Q(language=lang))

                # If there are existing rows not in incoming set -> delete them
                if q_filter:
                    deleted_count, _ = SpiritualGiftSurveyQuestion.objects.exclude(q_filter).delete()
                else:
                    deleted_count, _ = SpiritualGiftSurveyQuestion.objects.all().delete()

                self.stdout.write(self.style.WARNING(f"Deleted {deleted_count} missing questions."))

        self.stdout.write(self.style.SUCCESS("Questions import completed successfully."))


            
# docker compose exec backend python manage.py import_questions
# docker compose exec backend python manage.py import_questions --replace
# docker compose exec backend python manage.py import_questions --sync-deactivate-missing
