# apps/journey_insights/views.py

from django.db.models import Prefetch
from django.utils import timezone

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.pagination import ConfigurablePagination
from apps.journey_insights.constants import ReflectionSessionStatus
from apps.journey_insights.models import (
    MonthlyInsightReport,
    ReflectionSession,
    ReflectionSessionQuestion,
)
from apps.journey_insights.serializers import (
    DailyReflectionPromptDecisionSerializer,
    DailyReflectionPromptSerializer,
    MonthlyInsightReportDetailSerializer,
    MonthlyInsightReportListSerializer,
    ReflectionAnswerCreateSerializer,
    ReflectionAnswerSerializer,
    ReflectionEligibilitySerializer,
    ReflectionSessionCreateSerializer,
    ReflectionSessionSerializer,
)
from apps.journey_insights.services.daily_prompt import (
    apply_daily_reflection_decision,
    get_current_daily_reflection_prompt,
    prepare_daily_reflection_for_journey_creation,
)
from apps.journey_insights.services.eligibility import (
    get_reflection_eligibility,
)


class ReflectionSessionViewSet(
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    serializer_class = ReflectionSessionSerializer
    lookup_field = "public_id"

    def get_queryset(self):
        question_queryset = (
            ReflectionSessionQuestion.objects
            .select_related("question")
            .order_by("position", "id")
        )

        return (
            ReflectionSession.objects
            .filter(user=self.request.user)
            .prefetch_related(
                Prefetch(
                    "session_questions",
                    queryset=question_queryset,
                    to_attr="ordered_questions",
                )
            )
            .order_by("-opened_at", "-id")
        )

    @action(detail=False, methods=["get"], url_path="eligibility")
    def eligibility(self, request):
        result = get_reflection_eligibility(user=request.user)

        serializer = ReflectionEligibilitySerializer(
            instance=result.as_dict(),
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )
        
    @action(
        detail=False,
        methods=["get"],
        url_path="daily-prompt/prepare-for-journey",
    )
    def prepare_daily_prompt_for_journey(self, request):
        timezone_name = (
            request.query_params
            .get("timezone", "")
            .strip()
        )

        result = prepare_daily_reflection_for_journey_creation(
            user=request.user,
            timezone_name=timezone_name,
        )

        serializer = DailyReflectionPromptSerializer(
            instance=result.as_dict(),
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="start")
    def start(self, request):
        serializer = ReflectionSessionCreateSerializer(
            data=request.data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)

        session = serializer.save()
        session = self.get_queryset().get(pk=session.pk)

        return Response(
            ReflectionSessionSerializer(
                session,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="answer")
    def answer(self, request):
        serializer = ReflectionAnswerCreateSerializer(
            data=request.data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)
        answer = serializer.save()

        return Response(
            ReflectionAnswerSerializer(answer).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="current")
    def current(self, request):
        session = (
            self.get_queryset()
            .filter(
                status=ReflectionSessionStatus.OPEN,
                expires_at__gt=timezone.now(),
            )
            .order_by("-opened_at", "-id")
            .first()
        )

        if session is None:
            raise NotFound(
                "No active reflection session was found."
            )

        return Response(
            ReflectionSessionSerializer(
                session,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="daily-prompt/decision",
    )
    def daily_prompt_decision(self, request):
        input_serializer = DailyReflectionPromptDecisionSerializer(
            data=request.data,
        )

        input_serializer.is_valid(raise_exception=True)

        result = apply_daily_reflection_decision(
            user=request.user,
            prompt_public_id=(
                input_serializer.validated_data["prompt_public_id"]
            ),
            decision=input_serializer.validated_data["decision"],
        )

        output_serializer = DailyReflectionPromptSerializer(
            instance=result.as_dict(),
        )

        return Response(
            output_serializer.data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="daily-prompt/current",
    )
    def current_daily_prompt(self, request):
        result = get_current_daily_reflection_prompt(
            user=request.user,
        )

        serializer = DailyReflectionPromptSerializer(
            instance=result.as_dict(),
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class MonthlyInsightPagination(ConfigurablePagination):
    page_size = 12
    max_page_size = 24


class MonthlyInsightReportViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    pagination_class = MonthlyInsightPagination
    lookup_field = "public_id"

    def get_queryset(self):
        return (
            MonthlyInsightReport.objects
            .filter(user=self.request.user)
            .prefetch_related("dimensions")
            .order_by("-year", "-month", "-id")
        )

    def get_serializer_class(self):
        if self.action == "list":
            return MonthlyInsightReportListSerializer

        return MonthlyInsightReportDetailSerializer

    @action(detail=False, methods=["get"], url_path="latest")
    def latest(self, request):
        report = self.get_queryset().filter(status="ready").first()

        if report is None:
            raise NotFound(
                "No monthly insight report was found."
            )

        return Response(
            MonthlyInsightReportDetailSerializer(
                report,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )