# apps/asset_delivery/services/field_aliases.py

FIELD_ALIAS_MAP = {
    # User avatar/profile image
    (
        "accounts",
        "customuser",
        "avatar",
    ): "image_name",
    (
        "accounts",
        "customuser",
        "image",
    ): "image_name",
    (
        "accounts",
        "customuser",
        "photo",
    ): "image_name",
    (
        "accounts",
        "customuser",
        "thumbnail",
    ): "image_name",

    # Dialogue / group cover image
    (
        "conversation",
        "dialogue",
        "avatar",
    ): "group_image",
    (
        "conversation",
        "dialogue",
        "image",
    ): "group_image",
    (
        "conversation",
        "dialogue",
        "cover",
    ): "group_image",
    (
        "conversation",
        "dialogue",
        "group_image",
    ): "group_image",
    (
        "conversation",
        "dialogue",
        "thumbnail",
    ): "group_image",

    # Audio catalog track variant
    (
        "audio_catalog",
        "musictrackvariant",
        "audio",
    ): "audio_file",
    (
        "audio_catalog",
        "musictrackvariant",
        "file",
    ): "audio_file",
    (
        "audio_catalog",
        "musictrackvariant",
        "waveform",
    ): "waveform_file",

    # Audio catalog artwork
    (
        "audio_catalog",
        "musicartwork",
        "artwork",
    ): "image",
    (
        "audio_catalog",
        "musicartwork",
        "thumbnail",
    ): "image",
    (
        "audio_catalog",
        "musicartwork",
        "cover",
    ): "image",
}


def resolve_field_alias(
    app_label: str,
    model: str,
    field_name: str,
) -> str:
    """
    Map public aliases to real model fields.
    """

    key = (
        (app_label or "").strip().lower(),
        (model or "").strip().lower(),
        (field_name or "").strip().lower(),
    )

    return FIELD_ALIAS_MAP.get(
        key,
        field_name,
    )