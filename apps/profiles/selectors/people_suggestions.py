# apps/profiles/selectors/people_suggestions.py
# apps/profiles/selectors/people_suggestions.py

from django.db.models import (
    Q,
    Count,
    Case,
    When,
    Value,
    IntegerField,
    F,
    OuterRef,
    Subquery,
)
from django.db.models.functions import Coalesce
from django.contrib.auth import get_user_model

from apps.profiles.models import Friendship
from apps.profiles.selectors.friends import get_friend_user_ids

CustomUser = get_user_model()


def get_people_suggestions_queryset(viewer):
    """
    Ranked suggestions for Square → People tab.

    Ranking signals:

        mutual friends (strongest)
        same country
        same language
        same denomination branch
        same denomination family
        townlit verified

    Mutual friends calculation is symmetric-safe.
    """

    if not viewer or not viewer.is_authenticated:
        return CustomUser.objects.none()

    # ----------------------------------------------------
    # Exclusions
    # ----------------------------------------------------
    friend_ids = set(get_friend_user_ids(viewer))

    sent_requests = set(
        Friendship.objects.filter(
            from_user=viewer,
            status="pending"
        ).values_list("to_user_id", flat=True)
    )

    received_requests = set(
        Friendship.objects.filter(
            to_user=viewer,
            status="pending"
        ).values_list("from_user_id", flat=True)
    )

    excluded_ids = friend_ids | sent_requests | received_requests | {viewer.id}

    # ----------------------------------------------------
    # Base queryset
    # ----------------------------------------------------
    qs = (
        CustomUser.objects
        .filter(is_active=True, is_deleted=False)
        .exclude(id__in=excluded_ids)
        .select_related("label", "member_profile")
    )

    # ----------------------------------------------------
    # Mutual friends (SYMMETRIC SAFE)
    # ----------------------------------------------------
    friend_ids_list = list(friend_ids)

    if friend_ids_list:

        mutual_count_sq = (
            Friendship.objects
            .filter(status="accepted", is_active=True)
            .filter(
                Q(from_user_id__in=friend_ids_list, to_user_id=OuterRef("pk")) |
                Q(to_user_id__in=friend_ids_list, from_user_id=OuterRef("pk"))
            )
            .annotate(
                mf_id=Case(
                    When(from_user_id__in=friend_ids_list, then=F("from_user_id")),
                    default=F("to_user_id"),
                    output_field=IntegerField(),
                ),
                grp=Value(1, output_field=IntegerField()),
            )
            .values("grp")
            .annotate(cnt=Count("mf_id", distinct=True))
            .values("cnt")[:1]
        )

        qs = qs.annotate(
            mutual_friends=Coalesce(Subquery(mutual_count_sq), Value(0))
        )

    else:
        qs = qs.annotate(
            mutual_friends=Value(0, output_field=IntegerField())
        )

    # ----------------------------------------------------
    # Viewer signals
    # ----------------------------------------------------
    viewer_country = viewer.country
    viewer_language = viewer.primary_language

    viewer_member = getattr(viewer, "member_profile", None)

    viewer_branch = None
    viewer_family = None

    if viewer_member:
        viewer_branch = viewer_member.denomination_branch
        viewer_family = viewer_member.denomination_family

    # ----------------------------------------------------
    # Shared signals
    # ----------------------------------------------------
    qs = qs.annotate(

        same_country=Case(
            When(country=viewer_country, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ) if viewer_country else Value(0, output_field=IntegerField()),

        same_language=Case(
            When(primary_language=viewer_language, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ) if viewer_language else Value(0, output_field=IntegerField()),

        same_branch=Case(
            When(member_profile__denomination_branch=viewer_branch, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ) if viewer_branch else Value(0, output_field=IntegerField()),

        same_family=Case(
            When(member_profile__denomination_family=viewer_family, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ) if viewer_family else Value(0, output_field=IntegerField()),

        townlit_verified=Case(
            When(member_profile__is_townlit_verified=True, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
    )

    # ----------------------------------------------------
    # Final ranking score
    # ----------------------------------------------------
    qs = qs.annotate(
        score=
        F("mutual_friends") * 20 +
        F("same_branch") * 8 +
        F("same_family") * 5 +
        F("same_country") * 4 +
        F("same_language") * 3 +
        F("townlit_verified") * 2
    )

    # ----------------------------------------------------
    # Order
    # ----------------------------------------------------
    qs = qs.order_by("-score", "-register_date")

    return qs