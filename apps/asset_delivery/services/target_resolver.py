# apps/asset_delivery/services/target_resolver.py

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, FieldDoesNotExist


def get_target_by_content_type(content_type_id: int, object_id: int):
    ct = ContentType.objects.get(id=content_type_id)
    Model = ct.model_class()
    if Model is None:
        raise ValueError("Invalid content_type_id.")
    return Model.objects.get(pk=object_id)


def get_target_by_app_model(app_label: str, model: str, object_id: int):
    Model = apps.get_model(app_label, model)
    if Model is None:
        raise ValueError("Invalid app_label/model.")
    return Model.objects.get(pk=object_id)


def get_target_by_slug(app_label: str, model: str, slug: str):
    Model = apps.get_model(app_label, model)
    if Model is None:
        raise ValueError("Invalid app_label/model.")

    try:
        Model._meta.get_field("slug")
    except FieldDoesNotExist:
        raise ValueError("Target model does not support slug lookup.")

    return Model.objects.get(slug=slug)
