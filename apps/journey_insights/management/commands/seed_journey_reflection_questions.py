# apps/journey_insights/management/commands/seed_journey_reflection_questions.py

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.journey_insights.constants import (
    ReflectionQuestionKind,
    ReflectionQuestionStatus,
)
from apps.journey_insights.models import ReflectionChoice, ReflectionQuestion
from apps.journey_insights.question_bank.registry import (
    QUESTION_BANK,
    validate_question_bank,
)


class Command(BaseCommand):
    help = "Seed the canonical English Journey reflection question bank."

    def add_arguments(self, parser):
        parser.add_argument(
            "--retire-missing",
            action="store_true",
            help="Retire active database questions that no longer exist in the code bank.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            validate_question_bank()
        except ValueError as exc:
            raise CommandError(str(exc))

        created_questions = 0
        updated_questions = 0
        created_choices = 0
        updated_choices = 0
        retired_questions = 0

        bank_codes = {definition["code"] for definition in QUESTION_BANK}

        for definition in QUESTION_BANK:
            question_obj, question_created = ReflectionQuestion.objects.update_or_create(
                code=definition["code"],
                defaults={
                    "prompt": definition["prompt"],
                    "kind": ReflectionQuestionKind.SINGLE_CHOICE,
                    "primary_dimension": definition["dimension"],
                    "secondary_dimensions": definition.get("secondary_dimensions", []),
                    "status": ReflectionQuestionStatus.ACTIVE,
                    "difficulty": definition.get("difficulty", 1),
                    "sensitivity": definition.get("sensitivity", 1),
                    "selection_weight": definition.get("selection_weight", 1),
                    "minimum_journey_entries": definition.get(
                        "minimum_journey_entries",
                        1,
                    ),
                    "minimum_active_days_in_month": definition.get(
                        "minimum_active_days_in_month",
                        1,
                    ),
                    "allow_for_new_users": definition.get(
                        "allow_for_new_users",
                        True,
                    ),
                    "is_brand_core": definition.get("is_brand_core", False),
                    "version": definition.get("version", 1),
                    "metadata": definition.get("metadata", {}),
                    "is_active": True,
                },
            )

            if question_created:
                created_questions += 1
            else:
                updated_questions += 1

            active_choice_codes: set[str] = set()

            for order, choice_definition in enumerate(
                definition["choices"],
                start=1,
            ):
                choice_code = choice_definition["code"]
                active_choice_codes.add(choice_code)

                choice_obj, choice_created = ReflectionChoice.objects.update_or_create(
                    question=question_obj,
                    code=choice_code,
                    defaults={
                        "label": choice_definition["label"],
                        "order": order,
                        "base_score": choice_definition["base_score"],
                        "dimension_weights": choice_definition["weights"],
                        "scoring_profile": choice_definition.get(
                            "scoring_profile",
                            {},
                        ),
                        "metadata": choice_definition.get("metadata", {}),
                        "is_active": True,
                    },
                )

                if choice_created:
                    created_choices += 1
                else:
                    updated_choices += 1

            question_obj.choices.exclude(
                code__in=active_choice_codes
            ).update(
                is_active=False
            )

        if options["retire_missing"]:
            retired_questions = (
                ReflectionQuestion.objects
                .filter(is_active=True)
                .exclude(code__in=bank_codes)
                .update(
                    is_active=False,
                    status=ReflectionQuestionStatus.RETIRED,
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Journey reflection bank seeded successfully.\n"
                f"Questions created: {created_questions}\n"
                f"Questions updated: {updated_questions}\n"
                f"Choices created: {created_choices}\n"
                f"Choices updated: {updated_choices}\n"
                f"Questions retired: {retired_questions}\n"
                f"Bank size: {len(QUESTION_BANK)}"
            )
        )
        
# docker compose exec -T backend python manage.py seed_journey_reflection_questions