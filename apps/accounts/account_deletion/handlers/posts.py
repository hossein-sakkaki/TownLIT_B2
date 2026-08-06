#
#  apps/accounts/account_deletion/handlers/posts.py
#  TownLIT
#
#  Created by Hossein Sakkaki on 2026-08-04.
#  Last Update by Hossein Sakkaki on 2026-08-04.
#

from __future__ import annotations

import logging
from collections.abc import Iterable

from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Q

from apps.accounts.account_deletion.context import (
    AccountDeletionContext,
)
from apps.accounts.account_deletion.registry import (
    account_deletion_registry,
)
from apps.posts.models.comment import Comment
from apps.posts.models.journey import (
    Journey,
    JourneyEntry,
    JourneyEntryView,
)
from apps.posts.models.moment import Moment
from apps.posts.models.pray import Prayer
from apps.posts.models.reaction import Reaction
from apps.posts.models.testimony import Testimony
from apps.profiles.models.guest import GuestUser
from apps.profiles.models.member import Member


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Owner targets
# ---------------------------------------------------------------------
def _profile_owner_targets(
    context: AccountDeletionContext,
) -> list[tuple[int, int]]:
    """
    Return every Member and Guest profile linked to the user.

    Both profile types are checked because migrated users may retain
    historical profile rows and content from their previous path.
    """
    targets: list[tuple[int, int]] = []

    for model in (
        Member,
        GuestUser,
    ):
        content_type = ContentType.objects.get_for_model(
            model,
            for_concrete_model=False,
        )

        profile_ids = (
            model.objects
            .filter(user_id=context.user.id)
            .values_list("id", flat=True)
        )

        targets.extend(
            (
                content_type.id,
                profile_id,
            )
            for profile_id in profile_ids
        )

    return targets


def _owner_query(
    targets: Iterable[tuple[int, int]],
) -> Q:
    """
    Build a polymorphic ownership query.
    """
    query = Q()

    for content_type_id, object_id in targets:
        query |= Q(
            content_type_id=content_type_id,
            object_id=object_id,
        )

    return query


def _target_pairs_for_queryset(
    queryset,
) -> list[tuple[int, int]]:
    """
    Return ContentType/object ID pairs for interaction cleanup.
    """
    model = queryset.model

    content_type = ContentType.objects.get_for_model(
        model,
        for_concrete_model=False,
    )

    object_ids = queryset.values_list(
        "id",
        flat=True,
    )

    return [
        (
            content_type.id,
            object_id,
        )
        for object_id in object_ids
    ]


def _interaction_target_query(
    targets: Iterable[tuple[int, int]],
) -> Q:
    """
    Build a query matching Comment/Reaction generic targets.
    """
    query = Q()

    for content_type_id, object_id in targets:
        query |= Q(
            content_type_id=content_type_id,
            object_id=object_id,
        )

    return query


# ---------------------------------------------------------------------
# Moment JSON asset cleanup
# ---------------------------------------------------------------------
def _normalize_storage_key(
    value,
) -> str | None:
    """
    Return a private storage key or None.
    """
    if not isinstance(value, str):
        return None

    normalized = value.strip()

    if not normalized:
        return None

    lowered = normalized.lower()

    if (
        lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("data:")
    ):
        return None

    return normalized.lstrip("/") or None


def _extract_storage_keys(
    value,
) -> set[str]:
    """
    Extract storage keys from Moment image metadata.
    """
    keys: set[str] = set()

    if isinstance(value, str):
        normalized = _normalize_storage_key(
            value
        )

        if normalized:
            keys.add(normalized)

        return keys

    if isinstance(value, list):
        for item in value:
            keys.update(
                _extract_storage_keys(item)
            )

        return keys

    if not isinstance(value, dict):
        return keys

    for field_name, field_value in value.items():
        normalized_field = str(
            field_name or ""
        ).strip().lower()

        if normalized_field in {
            "key",
            "path",
            "storage_key",
            "source_key",
            "output_key",
        }:
            normalized = _normalize_storage_key(
                field_value
            )

            if normalized:
                keys.add(normalized)

            continue

        if normalized_field == "variants":
            keys.update(
                _extract_storage_keys(
                    field_value
                )
            )

    return keys


def _moment_json_asset_keys(
    moments,
) -> set[str]:
    """
    Collect JSON-backed Moment asset keys.
    """
    keys: set[str] = set()

    for moment in moments.iterator(
        chunk_size=100,
    ):
        image_items = (
            moment.image_items
            if isinstance(
                moment.image_items,
                list,
            )
            else []
        )

        keys.update(
            _extract_storage_keys(
                image_items
            )
        )

    return keys


def _delete_storage_keys(
    storage_keys: set[str],
) -> None:
    """
    Delete storage objects after database commit.
    """
    for storage_key in sorted(storage_keys):
        try:
            default_storage.delete(
                storage_key
            )
        except Exception:
            logger.exception(
                "[AccountDeletion] Moment asset deletion failed "
                "storage_key=%s",
                storage_key,
            )


# ---------------------------------------------------------------------
# User-authored comments
# ---------------------------------------------------------------------
def _delete_user_comments(
    *,
    user_id: int,
) -> int:
    """
    Delete comments written by the user without cascading into replies
    written by other users.

    Replies authored by other users are converted to root comments.
    """
    authored_comment_ids = list(
        Comment.objects
        .filter(name_id=user_id)
        .values_list("id", flat=True)
    )

    if not authored_comment_ids:
        return 0

    Comment.objects.filter(
        recomment_id__in=authored_comment_ids,
    ).exclude(
        name_id=user_id,
    ).update(
        recomment=None,
    )

    deleted_count, _ = (
        Comment.objects
        .filter(id__in=authored_comment_ids)
        .delete()
    )

    return deleted_count


# ---------------------------------------------------------------------
# Testimony tags
# ---------------------------------------------------------------------
def _remove_testimony_user_tags(
    context: AccountDeletionContext,
) -> int:
    """
    Remove user tags from testimonies owned by other accounts.
    """
    tagged_testimonies = (
        Testimony.objects
        .filter(user_tags=context.user)
        .only("id")
        .distinct()
    )

    removed_count = tagged_testimonies.count()

    for testimony in tagged_testimonies.iterator(
        chunk_size=100,
    ):
        testimony.user_tags.remove(
            context.user
        )

    return removed_count


# ---------------------------------------------------------------------
# Owned interaction cleanup
# ---------------------------------------------------------------------
def _delete_owned_content_interactions(
    *,
    target_pairs: list[tuple[int, int]],
) -> tuple[int, int]:
    """
    Delete all comments and reactions attached to owned content.
    """
    if not target_pairs:
        return 0, 0

    target_query = _interaction_target_query(
        target_pairs
    )

    deleted_comments, _ = (
        Comment.objects
        .filter(target_query)
        .delete()
    )

    deleted_reactions, _ = (
        Reaction.objects
        .filter(target_query)
        .delete()
    )

    return (
        deleted_comments,
        deleted_reactions,
    )


# ---------------------------------------------------------------------
# Deletion handler
# ---------------------------------------------------------------------
@account_deletion_registry.register(
    key="posts",
    order=600,
)
def purge_post_data(
    context: AccountDeletionContext,
) -> None:
    """
    Permanently remove owned posts and user-created interactions.
    """
    user = context.user

    owner_targets = _profile_owner_targets(
        context
    )

    owner_filter = _owner_query(
        owner_targets
    )

    removed_tag_count = (
        _remove_testimony_user_tags(
            context
        )
    )

    journey_view_count, _ = (
        JourneyEntryView.objects
        .filter(viewer_id=user.id)
        .delete()
    )

    authored_reaction_count, _ = (
        Reaction.objects
        .filter(name_id=user.id)
        .delete()
    )

    authored_comment_count = (
        _delete_user_comments(
            user_id=user.id,
        )
    )

    if not owner_targets:
        logger.info(
            "[AccountDeletion] Post cleanup completed without "
            "linked profiles user_id=%s tags=%s views=%s "
            "authored_reactions=%s authored_comments=%s",
            user.id,
            removed_tag_count,
            journey_view_count,
            authored_reaction_count,
            authored_comment_count,
        )

        return

    owned_moments = Moment.objects.filter(
        owner_filter
    )

    owned_prayers = Prayer.objects.filter(
        owner_filter
    )

    owned_testimonies = Testimony.objects.filter(
        owner_filter
    )

    owned_journeys = Journey.objects.filter(
        owner_filter
    )

    owned_journey_entries = JourneyEntry.objects.filter(
        journey__in=owned_journeys
    )

    moment_json_keys = _moment_json_asset_keys(
        owned_moments
    )

    interaction_targets: list[
        tuple[int, int]
    ] = []

    interaction_targets.extend(
        _target_pairs_for_queryset(
            owned_moments
        )
    )

    interaction_targets.extend(
        _target_pairs_for_queryset(
            owned_prayers
        )
    )

    interaction_targets.extend(
        _target_pairs_for_queryset(
            owned_testimonies
        )
    )

    interaction_targets.extend(
        _target_pairs_for_queryset(
            owned_journey_entries
        )
    )

    owned_comment_count, owned_reaction_count = (
        _delete_owned_content_interactions(
            target_pairs=interaction_targets,
        )
    )

    journey_count, _ = (
        owned_journeys.delete()
    )

    testimony_count, _ = (
        owned_testimonies.delete()
    )

    prayer_count, _ = (
        owned_prayers.delete()
    )

    moment_count, _ = (
        owned_moments.delete()
    )

    if moment_json_keys:
        transaction.on_commit(
            lambda keys=set(moment_json_keys): (
                _delete_storage_keys(keys)
            )
        )

    logger.info(
        "[AccountDeletion] Post cleanup completed "
        "user_id=%s owners=%s tags=%s views=%s "
        "authored_reactions=%s authored_comments=%s "
        "owned_reactions=%s owned_comments=%s "
        "journeys=%s testimonies=%s prayers=%s moments=%s "
        "moment_json_assets=%s",
        user.id,
        len(owner_targets),
        removed_tag_count,
        journey_view_count,
        authored_reaction_count,
        authored_comment_count,
        owned_reaction_count,
        owned_comment_count,
        journey_count,
        testimony_count,
        prayer_count,
        moment_count,
        len(moment_json_keys),
    )