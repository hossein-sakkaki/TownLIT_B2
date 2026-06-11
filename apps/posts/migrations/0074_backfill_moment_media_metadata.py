# apps/posts/migrations/0074_backfill_moment_media_metadata.py

from django.db import migrations
import uuid


def backfill_moment_media_metadata(apps, schema_editor):
    Moment = apps.get_model("posts", "Moment")

    for moment in Moment.objects.all().iterator():
        changed_fields = []

        image_name = getattr(moment.image, "name", "") or ""
        video_name = getattr(moment.video, "name", "") or ""

        if video_name:
            if moment.media_kind != "video":
                moment.media_kind = "video"
                changed_fields.append("media_kind")

            if moment.image_items != []:
                moment.image_items = []
                changed_fields.append("image_items")

            if moment.cover_image_id:
                moment.cover_image_id = None
                changed_fields.append("cover_image_id")

        elif image_name:
            if moment.media_kind != "image":
                moment.media_kind = "image"
                changed_fields.append("media_kind")

            existing_items = moment.image_items if isinstance(moment.image_items, list) else []

            if not existing_items:
                item_id = uuid.uuid4().hex
                moment.image_items = [
                    {
                        "id": item_id,
                        "key": image_name.lstrip("/"),
                        "file_name": image_name.split("/")[-1],
                        "mime_type": "",
                        "size": 0,
                        "order": 0,
                        "is_cover": True,
                    }
                ]
                moment.cover_image_id = item_id
                changed_fields.extend(["image_items", "cover_image_id"])

            elif not moment.cover_image_id:
                first = existing_items[0]
                moment.cover_image_id = str(first.get("id") or uuid.uuid4().hex)
                changed_fields.append("cover_image_id")

            if moment.is_converted is not True:
                moment.is_converted = True
                changed_fields.append("is_converted")

        if changed_fields:
            moment.save(update_fields=list(set(changed_fields)))


def reverse_backfill_moment_media_metadata(apps, schema_editor):
    # Keep metadata on rollback to avoid losing cover choices.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("posts", "0073_moment_audio_payload_moment_cover_image_id_and_more"),
    ]

    operations = [
        migrations.RunPython(
            backfill_moment_media_metadata,
            reverse_backfill_moment_media_metadata,
        ),
    ]