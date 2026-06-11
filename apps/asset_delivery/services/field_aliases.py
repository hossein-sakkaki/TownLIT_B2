# apps/asset_delivery/services/field_aliases.py

FIELD_ALIAS_MAP = {
    ("accounts", "customuser", "avatar"): "image_name",
    ("conversation", "dialogue", "avatar"): "group_image",
}


def resolve_field_alias(app_label: str, model: str, field_name: str) -> str:
    """
    Map public aliases to real model fields.
    """

    key = (
        (app_label or "").strip().lower(),
        (model or "").strip().lower(),
        (field_name or "").strip().lower(),
    )
    return FIELD_ALIAS_MAP.get(key, field_name)

