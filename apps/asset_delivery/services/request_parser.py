# apps/asset_delivery/services/request_parser.py

def parse_target_lookup(data):
    """
    Parse target lookup from query params or request data.
    """

    content_type_id = data.get("content_type_id")
    object_id = data.get("object_id")
    app_label = data.get("app_label")
    model = data.get("model")
    slug = data.get("slug")

    if content_type_id and object_id:
        return {
            "mode": "content_type",
            "content_type_id": int(content_type_id),
            "object_id": int(object_id),
        }

    if app_label and model and object_id:
        return {
            "mode": "app_model_object",
            "app_label": app_label.strip(),
            "model": model.strip(),
            "object_id": int(object_id),
        }

    if app_label and model and slug:
        return {
            "mode": "app_model_slug",
            "app_label": app_label.strip(),
            "model": model.strip(),
            "slug": slug.strip(),
        }

    raise ValueError(
        "Provide (content_type_id, object_id) OR "
        "(app_label, model, object_id) OR "
        "(app_label, model, slug)."
    )
    
    
    
