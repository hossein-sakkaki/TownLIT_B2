# apps/sanctuary/constants/target_models.py

from __future__ import annotations

from apps.sanctuary.constants.targets import (
    ACCOUNT,
    CONTENT,
    MESSENGER_GROUP,
    ORGANIZATION,
)


# ---------------------------------------------------------------------
# Supported Sanctuary target models
# ---------------------------------------------------------------------
#
# Keys use Django ContentType natural keys:
#
#     app_label.model_name
#
# Keep this registry explicit. A model must not become a Sanctuary
# target merely because it exists in django_content_type.
#
# Comment and reply targets use posts.comment.
# Individual Messenger messages require their own dedicated moderation flow.
# ---------------------------------------------------------------------

CONTENT_TARGET_MODELS = frozenset(
    {
        "posts.moment",
        "posts.prayer",
        "posts.testimony",
        "posts.journeyentry",
        "posts.comment",
    }
)

ACCOUNT_TARGET_MODELS = frozenset(
    {
        "accounts.customuser",
    }
)

ORGANIZATION_TARGET_MODELS = frozenset(
    {
        "profilesorg.organization",
    }
)

MESSENGER_GROUP_TARGET_MODELS = frozenset(
    {
        "conversation.dialogue",
    }
)


SANCTUARY_TARGET_MODEL_MAP = {
    CONTENT: CONTENT_TARGET_MODELS,
    ACCOUNT: ACCOUNT_TARGET_MODELS,
    ORGANIZATION: ORGANIZATION_TARGET_MODELS,
    MESSENGER_GROUP: MESSENGER_GROUP_TARGET_MODELS,
}


def normalize_content_type_key(
    value: str | None,
) -> str:
    """
    Normalize a Django ContentType natural key.
    """
    return str(
        value or ""
    ).strip().lower()


def content_type_key(
    content_type,
) -> str:
    """
    Return the normalized natural key for a ContentType instance.
    """
    app_label = getattr(
        content_type,
        "app_label",
        "",
    )

    model = getattr(
        content_type,
        "model",
        "",
    )

    return normalize_content_type_key(
        f"{app_label}.{model}"
    )


def allowed_target_models_for(
    request_type: str | None,
) -> frozenset[str]:
    """
    Return the models explicitly allowed for a request type.
    """
    normalized_request_type = str(
        request_type or ""
    ).strip()

    return SANCTUARY_TARGET_MODEL_MAP.get(
        normalized_request_type,
        frozenset(),
    )


def is_allowed_target_model(
    *,
    request_type: str | None,
    content_type,
) -> bool:
    """
    Return True when the ContentType is allowed for the request type.
    """
    allowed_models = allowed_target_models_for(
        request_type
    )

    if not allowed_models:
        return False

    return content_type_key(
        content_type
    ) in allowed_models