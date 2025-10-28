# apps/profiles/management/commands/import_questions.py
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from apps.profiles.models import SpiritualGift, SpiritualGiftSurveyQuestion
from apps.profiles.gift_questions_constants import QUESTIONS

class Command(BaseCommand):
    help = "Import/Upsert spiritual gifts survey questions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Delete all existing questions then import fresh."
        )
        parser.add_argument(
            "--sync-deactivate-missing",
            action="store_true",
            help="After upsert, mark questions not present in QUESTIONS as inactive."
        )

    def handle(self, *args, **options):
        do_replace = options.get("replace", False)
        do_sync_deactivate = options.get("sync_deactivate_missing", False)

        # جمع کلیدهای یکتا برای دیتای ورودی
        incoming_keys = set()  # (question_number, language)
        for q in QUESTIONS:
            qnum = q["question_number"]
            for lang in q["question_text"].keys():
                incoming_keys.add((qnum, lang))

        with transaction.atomic():
            if do_replace:
                SpiritualGiftSurveyQuestion.objects.all().delete()
                self.stdout.write(self.style.WARNING("All existing questions deleted."))

            # Upsert اصلی
            for q in QUESTIONS:
                gift_name = str(q["gift"])
                gift, _ = SpiritualGift.objects.get_or_create(name=gift_name)

                qnum = q["question_number"]
                options_list = q["options"]  # معمولا [1..7]

                for lang, question_text in q["question_text"].items():
                    defaults = {
                        "question_text": question_text,
                        "options": options_list,
                        "gift": gift,
                        "is_active": True,  # در آپدیت فعال نگه دار
                    }
                    SpiritualGiftSurveyQuestion.objects.update_or_create(
                        question_number=qnum,
                        language=lang,
                        defaults=defaults,
                    )

            # همگام‌سازی اختیاری: غیرفعال کردن رکوردهای قدیمیِ ناموجود در QUESTIONS
            if do_sync_deactivate:
                q = Q()
                for (qnum, lang) in incoming_keys:
                    q |= (Q(question_number=qnum) & Q(language=lang))
                # رکوردهایی که بیرون از ورودی جدید هستند
                missing_qs = SpiritualGiftSurveyQuestion.objects.exclude(q)
                updated = missing_qs.update(is_active=False)
                self.stdout.write(self.style.WARNING(f"Deactivated {updated} missing questions."))

        self.stdout.write(self.style.SUCCESS("Questions import completed successfully."))

            
# docker compose exec backend python manage.py import_questions
# docker compose exec backend python manage.py import_questions --replace
# docker compose exec backend python manage.py import_questions --sync-deactivate-missing
