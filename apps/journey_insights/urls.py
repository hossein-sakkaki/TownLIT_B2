# apps/journey_insights/urls.py

from django.urls import path

from apps.journey_insights.views import (
    MonthlyInsightReportViewSet,
    ReflectionSessionViewSet,
)


app_name = "journey_insights"


reflection_eligibility = ReflectionSessionViewSet.as_view({"get": "eligibility"})
reflection_daily_prompt_prepare_for_journey = ReflectionSessionViewSet.as_view({"get": "prepare_daily_prompt_for_journey"})
reflection_daily_prompt_decision = ReflectionSessionViewSet.as_view({"post": "daily_prompt_decision"})
reflection_daily_prompt_current = ReflectionSessionViewSet.as_view({"get": "current_daily_prompt"})
reflection_start = ReflectionSessionViewSet.as_view({"post": "start"})
reflection_current = ReflectionSessionViewSet.as_view({"get": "current"})
reflection_answer = ReflectionSessionViewSet.as_view({"post": "answer"})
reflection_detail = ReflectionSessionViewSet.as_view({"get": "retrieve"})

report_list = MonthlyInsightReportViewSet.as_view({"get": "list"})
report_latest = MonthlyInsightReportViewSet.as_view({"get": "latest"})
report_detail = MonthlyInsightReportViewSet.as_view({"get": "retrieve"})


urlpatterns = [
    path("reflections/eligibility/", reflection_eligibility, name="reflection-eligibility"),
    path("reflections/start/", reflection_start, name="reflection-start"),
    path("reflections/current/", reflection_current, name="reflection-current"),
    path("reflections/answer/", reflection_answer, name="reflection-answer"),
    path("reflections/daily-prompt/prepare-for-journey/", reflection_daily_prompt_prepare_for_journey, name="reflection-daily-prompt-prepare-for-journey"),
    path("reflections/daily-prompt/decision/", reflection_daily_prompt_decision, name="reflection-daily-prompt-decision"),
    path("reflections/daily-prompt/current/", reflection_daily_prompt_current, name="reflection-daily-prompt-current"),
    path("reflections/<uuid:public_id>/", reflection_detail, name="reflection-detail"),
    path("monthly-reports/", report_list, name="monthly-report-list"),
    path("monthly-reports/latest/", report_latest, name="monthly-report-latest"),
    path("monthly-reports/<uuid:public_id>/", report_detail, name="monthly-report-detail"),
]