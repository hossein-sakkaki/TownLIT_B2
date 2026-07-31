# apps/posts/admin/filters.py

from django.contrib.admin import SimpleListFilter
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from apps.posts.models.testimony import Testimony
from apps.subtitles.models import VideoTranscript


CONTENT_TARGET_APP_LABELS = (
    "posts",
    "profiles",
    "profilesOrg",
)


class ContentAppFilter(SimpleListFilter):
    """
    Filter generic targets by ContentType app label.
    """

    title = "Content App"
    parameter_name = "ct_app"

    def lookups(self, request, model_admin):
        app_labels = (
            ContentType.objects
            .filter(app_label__in=CONTENT_TARGET_APP_LABELS)
            .values_list("app_label", flat=True)
            .distinct()
            .order_by("app_label")
        )

        return [(app_label, app_label) for app_label in app_labels]

    def queryset(self, request, queryset):
        app_label = self.value()

        if not app_label:
            return queryset

        return queryset.filter(content_type__app_label=app_label)


class ContentModelFilter(SimpleListFilter):
    """
    Filter generic targets by ContentType app label and model name.
    """

    title = "Content Model"
    parameter_name = "ct_model"

    def lookups(self, request, model_admin):
        content_types = (
            ContentType.objects
            .filter(app_label__in=CONTENT_TARGET_APP_LABELS)
            .order_by("app_label", "model")
        )

        return [
            (
                f"{content_type.app_label}.{content_type.model}",
                f"{content_type.app_label}.{content_type.model}",
            )
            for content_type in content_types
        ]

    def queryset(self, request, queryset):
        value = self.value()

        if not value:
            return queryset

        try:
            app_label, model_name = value.split(".", 1)
        except ValueError:
            return queryset

        return queryset.filter(
            content_type__app_label=app_label,
            content_type__model=model_name,
        )


class HasMessageFilter(SimpleListFilter):
    """
    Filter reactions based on whether they have a message.
    """

    title = "Has message"
    parameter_name = "has_msg"

    def lookups(self, request, model_admin):
        return [
            ("yes", "Yes"),
            ("no", "No"),
        ]

    def queryset(self, request, queryset):
        value = self.value()

        if value == "yes":
            return queryset.filter(
                message__isnull=False,
            ).exclude(message="")

        if value == "no":
            return queryset.filter(
                Q(message="") | Q(message__isnull=True)
            )

        return queryset


class HasRecommentFilter(SimpleListFilter):
    """
    Filter comments by whether they are replies.
    """

    title = "Is reply"
    parameter_name = "is_reply"

    def lookups(self, request, model_admin):
        return [
            ("yes", "Yes"),
            ("no", "No"),
        ]

    def queryset(self, request, queryset):
        value = self.value()

        if value == "yes":
            return queryset.filter(recomment__isnull=False)

        if value == "no":
            return queryset.filter(recomment__isnull=True)

        return queryset


class OfficialVideoFilter(SimpleListFilter):
    """
    Filter generic relations targeting OfficialVideo.
    """

    title = "Official Video only"
    parameter_name = "is_official_video"

    def lookups(self, request, model_admin):
        return [
            ("yes", "Yes (OfficialVideo)"),
            ("no", "No (Others)"),
        ]

    def queryset(self, request, queryset):
        value = self.value()

        official_video_condition = {
            "content_type__app_label": "main",
            "content_type__model": "officialvideo",
        }

        if value == "yes":
            return queryset.filter(**official_video_condition)

        if value == "no":
            return queryset.exclude(**official_video_condition)

        return queryset


class TestimonyVideoReviewStatusFilter(SimpleListFilter):
    """
    Filter video testimonies by transcript review status.
    """

    title = "Video review status"
    parameter_name = "video_review_status"

    def lookups(self, request, model_admin):
        return [
            ("approved", "Approved"),
            ("needs_review", "Needs review"),
            ("rejected", "Rejected"),
            ("pending", "Pending"),
            ("no_transcript", "No transcript"),
        ]

    def queryset(self, request, queryset):
        value = self.value()

        if not value:
            return queryset

        video_testimonies = queryset.filter(type=Testimony.TYPE_VIDEO)
        testimony_content_type = ContentType.objects.get_for_model(
            Testimony,
            for_concrete_model=False,
        )

        transcript_object_ids = VideoTranscript.objects.filter(
            content_type=testimony_content_type,
        ).values("object_id")

        if value == "no_transcript":
            return video_testimonies.exclude(
                pk__in=transcript_object_ids,
            )

        matching_object_ids = VideoTranscript.objects.filter(
            content_type=testimony_content_type,
            content_review_status=value,
        ).values("object_id")

        return video_testimonies.filter(pk__in=matching_object_ids)