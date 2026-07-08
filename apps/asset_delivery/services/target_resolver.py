# apps/asset_delivery/services/target_resolver.py

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist


APP_MODEL_ALIASES = {
    # iOS / legacy semantic labels -> real Django app/model
    ("moments", "moment"): ("posts", "moment"),
    ("moment", "moment"): ("posts", "moment"),

    ("prayers", "prayer"): ("posts", "prayer"),
    ("prayer", "prayer"): ("posts", "prayer"),
    ("pray", "prayer"): ("posts", "prayer"),

    ("testimonies", "testimony"): ("posts", "testimony"),
    ("testimony", "testimony"): ("posts", "testimony"),

    # Optional compatibility if client sends post/post-style labels.
    ("posts", "moment"): ("posts", "moment"),
    ("posts", "prayer"): ("posts", "prayer"),
    ("posts", "testimony"): ("posts", "testimony"),
}


def normalize_app_model(app_label: str, model: str) -> tuple[str, str]:
    normalized_app = (app_label or "").strip().lower()
    normalized_model = (model or "").strip().lower()

    return APP_MODEL_ALIASES.get(
        (normalized_app, normalized_model),
        (normalized_app, normalized_model),
    )


def get_target_by_content_type(content_type_id: int, object_id: int):
    ct = ContentType.objects.get(id=content_type_id)
    Model = ct.model_class()

    if Model is None:
        raise ValueError("Invalid content_type_id.")

    return Model.objects.get(pk=object_id)


def get_target_by_app_model(app_label: str, model: str, object_id: int):
    app_label, model = normalize_app_model(app_label, model)

    try:
        Model = apps.get_model(app_label, model)
    except LookupError:
        raise ValueError(
            f"Invalid app_label/model: {app_label}.{model}"
        )

    if Model is None:
        raise ValueError("Invalid app_label/model.")

    return Model.objects.get(pk=object_id)


def get_target_by_slug(app_label: str, model: str, slug: str):
    app_label, model = normalize_app_model(app_label, model)

    try:
        Model = apps.get_model(app_label, model)
    except LookupError:
        raise ValueError(
            f"Invalid app_label/model: {app_label}.{model}"
        )

    if Model is None:
        raise ValueError("Invalid app_label/model.")

    try:
        Model._meta.get_field("slug")
    except FieldDoesNotExist:
        raise ValueError("Target model does not support slug lookup.")

    return Model.objects.get(slug=slug)