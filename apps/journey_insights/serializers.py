# apps/journey_insights/serializers.py

from rest_framework import serializers

from apps.journey_insights.constants import (
    DailyReflectionPromptDecision,
)
from apps.journey_insights.models import (
    MonthlyInsightDimension,
    MonthlyInsightReport,
    ReflectionAnswer,
    ReflectionSession,
    ReflectionSessionQuestion,
)
from apps.journey_insights.services.reflections import (
    create_reflection_session,
    submit_reflection_answer,
)


class ReflectionQuestionPayloadSerializer(serializers.ModelSerializer):
    question_id = serializers.UUIDField(
        source="question.public_id",
        read_only=True,
    )

    prompt = serializers.CharField(
        source="prompt_snapshot",
        read_only=True,
    )

    kind = serializers.CharField(
        source="kind_snapshot",
        read_only=True,
    )

    primary_dimension = serializers.CharField(
        source="primary_dimension_snapshot",
        read_only=True,
    )

    choices = serializers.JSONField(
        source="choice_snapshot",
        read_only=True,
    )

    is_answered = serializers.SerializerMethodField()

    class Meta:
        model = ReflectionSessionQuestion

        fields = (
            "id",
            "question_id",
            "position",
            "prompt",
            "kind",
            "primary_dimension",
            "choices",
            "is_answered",
        )

        read_only_fields = fields

    def get_is_answered(self, obj):
        return hasattr(obj, "answer")


class ReflectionSessionSerializer(serializers.ModelSerializer):
    questions = serializers.SerializerMethodField()

    class Meta:
        model = ReflectionSession

        fields = (
            "public_id",
            "source_kind",
            "status",
            "question_count",
            "answered_count",
            "opened_at",
            "expires_at",
            "completed_at",
            "questions",
        )

        read_only_fields = fields

    def get_questions(self, obj):
        questions = getattr(obj, "ordered_questions", None)

        if questions is None:
            questions = (
                obj.session_questions
                .select_related("question")
                .order_by("position", "id")
            )

        return ReflectionQuestionPayloadSerializer(
            questions,
            many=True,
            context=self.context,
        ).data


class ReflectionSessionCreateSerializer(serializers.Serializer):
    question_count = serializers.IntegerField(
        min_value=1,
        max_value=5,
        required=False,
        default=3,
    )

    def create(self, validated_data):
        request = self.context["request"]

        return create_reflection_session(
            user=request.user,
            question_count=validated_data["question_count"],
        )


class ReflectionAnswerCreateSerializer(
    serializers.Serializer
):
    session_question_public_id = serializers.UUIDField()

    selected_choice_public_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        min_length=1,
    )

    def validate_selected_choice_public_ids(
        self,
        value,
    ):
        """
        Reject duplicate choice identifiers.
        """

        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                "Duplicate reflection choices are not allowed."
            )

        return value

    def create(
        self,
        validated_data,
    ):
        request = self.context["request"]

        try:
            assignment = (
                ReflectionSessionQuestion.objects
                .select_related(
                    "session",
                    "question",
                )
                .get(
                    public_id=validated_data[
                        "session_question_public_id"
                    ],
                    session__user=request.user,
                )
            )
        except ReflectionSessionQuestion.DoesNotExist:
            raise serializers.ValidationError(
                {
                    "session_question_public_id": (
                        "Reflection question was not found."
                    ),
                }
            )

        try:
            return submit_reflection_answer(
                user=request.user,
                session_question=assignment,
                selected_choice_public_ids=(
                    validated_data[
                        "selected_choice_public_ids"
                    ]
                ),
            )
        except serializers.ValidationError:
            raise
        except Exception as exc:
            message = str(
                exc
            ).strip()

            raise serializers.ValidationError(
                {
                    "detail": (
                        message
                        or "Unable to submit the reflection answer."
                    ),
                }
            )


class ReflectionAnswerSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = ReflectionAnswer

        fields = (
            "public_id",
            "selected_choice_codes",
            "submitted_at",
        )

        read_only_fields = fields


class MonthlyInsightDimensionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthlyInsightDimension

        fields = (
            "dimension",
            "score",
            "previous_score",
            "trend",
            "confidence",
            "sample_count",
            "explanation_key",
            "explanation_params",
        )

        read_only_fields = fields


class MonthlyInsightReportListSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthlyInsightReport

        fields = (
            "public_id",
            "year",
            "month",
            "status",
            "is_sufficient",
            "overall_score",
            "overall_trend",
            "journey_days_count",
            "journey_entries_count",
            "reflection_answers_count",
            "generated_at",
        )

        read_only_fields = fields


class MonthlyInsightReportDetailSerializer(serializers.ModelSerializer):
    dimensions = MonthlyInsightDimensionSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = MonthlyInsightReport

        fields = (
            "public_id",
            "year",
            "month",
            "period_start",
            "period_end",
            "timezone_name",
            "status",
            "version",
            "is_sufficient",
            "journey_days_count",
            "journey_entries_count",
            "reflection_sessions_count",
            "reflection_answers_count",
            "overall_score",
            "previous_overall_score",
            "overall_trend",
            "dimension_scores",
            "dimension_trends",
            "dimensions",
            "highlights",
            "growth_areas",
            "reflection_summary",
            "journey_summary",
            "generated_at",
        )

        read_only_fields = fields


class ReflectionEligibilitySerializer(serializers.Serializer):
    is_available = serializers.BooleanField(read_only=True)
    can_start_new_session = serializers.BooleanField(read_only=True)
    has_open_session = serializers.BooleanField(read_only=True)
    reason = serializers.CharField(read_only=True)
    recommended_question_count = serializers.IntegerField(read_only=True)
    journey_entries = serializers.IntegerField(read_only=True)
    active_days_in_month = serializers.IntegerField(read_only=True)

    open_session_public_id = serializers.UUIDField(
        read_only=True,
        allow_null=True,
    )

    open_session_expires_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
    )


class DailyReflectionPromptDecisionSerializer(serializers.Serializer):
    prompt_public_id = serializers.UUIDField()

    decision = serializers.ChoiceField(
        choices=DailyReflectionPromptDecision.choices,
    )


class DailyReflectionPromptSerializer(
    serializers.Serializer
):
    should_present = serializers.BooleanField()
    reason = serializers.CharField()

    prompt_public_id = serializers.UUIDField(
        allow_null=True
    )

    local_date = serializers.DateField(
        allow_null=True
    )
    timezone_name = serializers.CharField(
        allow_null=True
    )
    status = serializers.CharField(
        allow_null=True
    )

    session_public_id = serializers.UUIDField(
        allow_null=True
    )
    session_question_public_id = (
        serializers.UUIDField(
            allow_null=True
        )
    )

    question_public_id = serializers.UUIDField(
        allow_null=True
    )
    question_code = serializers.CharField(
        allow_null=True
    )

    prompt = serializers.CharField(
        allow_null=True
    )
    kind = serializers.CharField(
        allow_null=True
    )

    choices = serializers.ListField(
        child=serializers.DictField(),
        default=list,
    )

    prompt_count = serializers.IntegerField()
    deferred_count = serializers.IntegerField()

    source_language = serializers.CharField()
    display_language = serializers.CharField()
    is_translated = serializers.BooleanField()
    translation_cached = serializers.BooleanField()