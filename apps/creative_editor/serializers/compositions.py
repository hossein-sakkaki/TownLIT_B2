# apps/creative_editor/serializers/compositions.py

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import serializers

from apps.creative_editor.models import (
    CreativeComposition,
    CreativeCompositionMedia,
    CreativeRenderJob,
)
from apps.creative_editor.serializers.assets import asset_target
from apps.creative_editor.services.compositions import (
    create_composition,
    update_composition,
)
from apps.creative_editor.services.document import (
    validate_document_references,
)
from apps.creative_editor.services.video_policy import (
    inspect_uploaded_creative_video,
    validate_creative_video_duration,
)


class CreativeSourceReferenceSerializer(serializers.Serializer):
    app_label = serializers.CharField(max_length=100)
    model = serializers.CharField(max_length=100)
    object_id = serializers.IntegerField(min_value=1)
    field_name = serializers.CharField(max_length=80)


class CreativeCompositionMediaWriteSerializer(
    serializers.ModelSerializer
):
    id = serializers.UUIDField(
        source="public_id",
        required=False,
        write_only=True,
    )

    source_reference = CreativeSourceReferenceSerializer(
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = CreativeCompositionMedia

        fields = (
            "id",
            "media_type",
            "source_mode",
            "source_image",
            "source_video",
            "source_reference",
            "metadata",
        )

        extra_kwargs = {
            "media_type": {
                "required": False,
            },
            "source_mode": {
                "required": False,
            },
            "source_image": {
                "required": False,
                "allow_null": True,
            },
            "source_video": {
                "required": False,
                "allow_null": True,
            },
        }

    def validate(self, attrs):
        media_type = attrs.get(
            "media_type",
            CreativeCompositionMedia.MediaType.IMAGE,
        )

        source_mode = attrs.get(
            "source_mode",
            CreativeCompositionMedia.SourceMode.UPLOAD,
        )

        source_image = attrs.get(
            "source_image"
        )

        source_video = attrs.get(
            "source_video"
        )

        source_reference = attrs.get(
            "source_reference",
            serializers.empty,
        )

        if media_type not in {
            CreativeCompositionMedia.MediaType.IMAGE,
            CreativeCompositionMedia.MediaType.VIDEO,
        }:
            raise serializers.ValidationError(
                {
                    "media_type": (
                        "Unsupported creative media type."
                    ),
                }
            )

        if source_mode == CreativeCompositionMedia.SourceMode.UPLOAD:
            if (
                source_reference is not serializers.empty
                and source_reference
            ):
                raise serializers.ValidationError(
                    {
                        "source_reference": (
                            "Uploaded media cannot use "
                            "a content reference."
                        ),
                    }
                )

            if media_type == CreativeCompositionMedia.MediaType.IMAGE:
                if not source_image:
                    raise serializers.ValidationError(
                        {
                            "source_image": (
                                "Uploaded image media requires "
                                "a source image."
                            ),
                        }
                    )

                if source_video:
                    raise serializers.ValidationError(
                        {
                            "source_video": (
                                "Image media cannot contain "
                                "a source video."
                            ),
                        }
                    )

            elif media_type == CreativeCompositionMedia.MediaType.VIDEO:
                if not source_video:
                    raise serializers.ValidationError(
                        {
                            "source_video": (
                                "Uploaded video media requires "
                                "a source video."
                            ),
                        }
                    )

                if source_image:
                    raise serializers.ValidationError(
                        {
                            "source_image": (
                                "Video media cannot contain "
                                "a source image."
                            ),
                        }
                    )

                try:
                    inspection = inspect_uploaded_creative_video(
                        source_video
                    )

                    validate_creative_video_duration(
                        inspection.duration_ms
                    )

                except DjangoValidationError as exc:
                    raise serializers.ValidationError(
                        exc.message_dict
                        if hasattr(
                            exc,
                            "message_dict",
                        )
                        else exc.messages
                    )

                attrs["duration_ms"] = (
                    inspection.duration_ms
                )

        elif (
            source_mode
            == CreativeCompositionMedia.SourceMode.CONTENT_REFERENCE
        ):
            if source_image or source_video:
                raise serializers.ValidationError(
                    {
                        "source_image": (
                            "Content reference media cannot "
                            "use an uploaded source."
                        ),
                    }
                )

            if (
                source_reference is serializers.empty
                or not source_reference
            ):
                raise serializers.ValidationError(
                    {
                        "source_reference": (
                            "Content reference media requires "
                            "a source reference."
                        ),
                    }
                )

            if media_type == CreativeCompositionMedia.MediaType.VIDEO:
                raise serializers.ValidationError(
                    {
                        "source_reference": (
                            "Video content references are not "
                            "enabled in this phase."
                        ),
                    }
                )

        else:
            raise serializers.ValidationError(
                {
                    "source_mode": (
                        "Unsupported creative media source mode."
                    ),
                }
            )

        return attrs

    def create(self, validated_data):
        composition = self.context["composition"]
        request = self.context["request"]

        source_reference = validated_data.pop(
            "source_reference",
            serializers.empty,
        )

        media = CreativeCompositionMedia(
            composition=composition,
            **validated_data,
        )

        if media.source_mode == CreativeCompositionMedia.SourceMode.UPLOAD:
            media.source_content_type = None
            media.source_object_id = None
            media.source_field_name = ""

            if media.media_type == CreativeCompositionMedia.MediaType.IMAGE:
                media.source_video = None
                media.source_video_is_converted = False
                media.source_image_is_converted = False

            elif media.media_type == CreativeCompositionMedia.MediaType.VIDEO:
                media.source_image = None
                media.source_image_is_converted = False
                media.source_video_is_converted = False

        else:
            media.source_image = None
            media.source_video = None
            media.source_image_is_converted = False
            media.source_video_is_converted = False

            self._apply_source_reference(
                media=media,
                source_reference=source_reference,
                viewer=request.user,
            )

        try:
            media.full_clean()
            media.save()

        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict
                if hasattr(
                    exc,
                    "message_dict",
                )
                else exc.messages
            )

        return media

    def _apply_source_reference(
        self,
        *,
        media: CreativeCompositionMedia,
        source_reference,
        viewer,
    ) -> None:
        app_label = source_reference[
            "app_label"
        ].strip().lower()

        model = source_reference[
            "model"
        ].strip().lower()

        try:
            content_type = (
                ContentType.objects.get_by_natural_key(
                    app_label,
                    model,
                )
            )

        except ContentType.DoesNotExist:
            raise serializers.ValidationError(
                {
                    "source_reference": (
                        "Invalid app_label or model."
                    ),
                }
            )

        model_class = content_type.model_class()

        if model_class is None:
            raise serializers.ValidationError(
                {
                    "source_reference": (
                        "Source model is unavailable."
                    ),
                }
            )

        object_id = source_reference[
            "object_id"
        ]

        target = model_class.objects.filter(
            pk=object_id
        ).first()

        if target is None:
            raise serializers.ValidationError(
                {
                    "source_reference": (
                        "Source object does not exist."
                    ),
                }
            )

        field_name = source_reference[
            "field_name"
        ].strip()

        field = getattr(
            target,
            field_name,
            None,
        )

        if not field or not getattr(
            field,
            "name",
            None,
        ):
            raise serializers.ValidationError(
                {
                    "source_reference": (
                        "Source media field is unavailable."
                    ),
                }
            )

        authorization = getattr(
            target,
            "can_deliver_asset",
            None,
        )

        if not callable(authorization):
            raise serializers.ValidationError(
                {
                    "source_reference": (
                        "Source target does not support "
                        "secure asset delivery."
                    ),
                }
            )

        allowed = bool(
            authorization(
                viewer=viewer,
                field_name=field_name,
                intent="creative_editor_source",
            )
        )

        if not allowed:
            raise serializers.ValidationError(
                {
                    "source_reference": (
                        "You cannot use this source asset."
                    ),
                }
            )

        media.source_image = None
        media.source_video = None
        media.source_image_is_converted = False
        media.source_video_is_converted = False
        media.source_content_type = content_type
        media.source_object_id = object_id
        media.source_field_name = field_name

class CreativeCompositionMediaSerializer(
    serializers.ModelSerializer
):
    id = serializers.UUIDField(
        source="public_id"
    )

    source_reference = serializers.SerializerMethodField()
    source_asset = serializers.SerializerMethodField()
    is_ready = serializers.SerializerMethodField()
    width = serializers.SerializerMethodField()
    height = serializers.SerializerMethodField()
    duration_ms = serializers.SerializerMethodField()

    class Meta:
        model = CreativeCompositionMedia

        fields = (
            "id",
            "media_type",
            "source_mode",
            "source_reference",
            "source_asset",
            "width",
            "height",
            "duration_ms",
            "is_ready",
            "is_active",
            "metadata",
            "created_at",
            "updated_at",
        )

    def get_source_reference(self, obj):
        if not (
            obj.source_content_type_id
            and obj.source_object_id
            and obj.source_field_name
        ):
            return None

        return {
            "app_label": obj.source_content_type.app_label,
            "model": obj.source_content_type.model,
            "object_id": obj.source_object_id,
            "field_name": obj.source_field_name,
        }

    def get_source_asset(self, obj):
        if obj.source_mode == obj.SourceMode.UPLOAD:
            if obj.media_type == obj.MediaType.IMAGE and obj.source_image:
                return asset_target(
                    obj,
                    "source_image",
                    "image",
                )

            if obj.media_type == obj.MediaType.VIDEO and obj.source_video:
                return asset_target(
                    obj,
                    "source_video",
                    "video",
                )

            return None

        if (
            obj.source_mode == obj.SourceMode.CONTENT_REFERENCE
            and obj.source_content_type_id
            and obj.source_object_id
            and obj.source_field_name
        ):
            target = obj.source_content_object

            if target is None:
                return None

            return asset_target(
                target,
                obj.source_field_name,
                (
                    "video"
                    if obj.media_type == obj.MediaType.VIDEO
                    else "image"
                ),
            )

        return None
    
    def get_duration_ms(self, obj):
        if obj.duration_ms:
            return obj.duration_ms

        metadata = self._asset_metadata(obj)

        return metadata.get(
            "duration_ms"
        )

    def get_is_ready(self, obj) -> bool:
        return obj.is_available()

    def get_width(self, obj):
        if obj.width:
            return obj.width

        metadata = self._asset_metadata(obj)

        return metadata.get(
            "width"
        )

    def get_height(self, obj):
        if obj.height:
            return obj.height

        metadata = self._asset_metadata(obj)

        return metadata.get(
            "height"
        )

    def _asset_metadata(self, obj) -> dict:
        if obj.source_mode == obj.SourceMode.UPLOAD:
            assets = obj.media_assets or {}

            field_name = (
                "source_video"
                if obj.media_type == obj.MediaType.VIDEO
                else "source_image"
            )

            payload = assets.get(
                field_name
            ) or {}

            return (
                payload
                if isinstance(payload, dict)
                else {}
            )

        target = obj.source_content_object

        if target is None:
            return {}

        assets = getattr(
            target,
            "media_assets",
            None,
        ) or {}

        payload = assets.get(
            obj.source_field_name
        ) or {}

        return (
            payload
            if isinstance(payload, dict)
            else {}
        )
        

class CreativeCompositionWriteSerializer(serializers.ModelSerializer):
    expected_revision = serializers.IntegerField(
        min_value=1,
        write_only=True,
        required=False,
    )

    source_reference = CreativeSourceReferenceSerializer(
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = CreativeComposition

        fields = (
            "title",
            "visibility",
            "source_mode",
            "source_image",
            "source_reference",
            "canvas_width",
            "canvas_height",
            "format_version",
            "document",
            "expected_revision",
            "metadata",
        )

        extra_kwargs = {
            "source_image": {
                "required": False,
                "allow_null": True,
            },
            "document": {
                "required": True,
            },
        }

    def validate_document(self, value):
        try:
            validate_document_references(
                value,
                composition=self.instance,
                require_media_ready=False,
            )

        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                detail = exc.message_dict

                if set(detail.keys()) == {"document"}:
                    detail = detail["document"]

                raise serializers.ValidationError(detail)

            raise serializers.ValidationError(exc.messages)

        return value

    def validate(self, attrs):
        source_mode = attrs.get(
            "source_mode",
            getattr(
                self.instance,
                "source_mode",
                CreativeComposition.SourceMode.GENERATED_BACKGROUND,
            ),
        )

        source_image_marker = serializers.empty
        source_image = attrs.get("source_image", source_image_marker)

        source_reference = attrs.get(
            "source_reference",
            serializers.empty,
        )

        effective_source_image = (
            getattr(self.instance, "source_image", None)
            if source_image is source_image_marker
            else source_image
        )

        effective_has_reference = (
            self._instance_has_source_reference()
            if source_reference is serializers.empty
            else bool(source_reference)
        )

        self._validate_explicit_source_conflicts(
            attrs=attrs,
            source_mode=source_mode,
            source_reference=source_reference,
        )

        if (
            source_mode == CreativeComposition.SourceMode.UPLOAD
            and not effective_source_image
        ):
            raise serializers.ValidationError(
                {
                    "source_image": (
                        "Uploaded source mode requires a source image."
                    ),
                }
            )

        if (
            source_mode == CreativeComposition.SourceMode.CONTENT_REFERENCE
            and not effective_has_reference
        ):
            raise serializers.ValidationError(
                {
                    "source_reference": (
                        "Content reference mode requires a source reference."
                    ),
                }
            )

        if self.instance is not None and "expected_revision" not in attrs:
            raise serializers.ValidationError(
                {
                    "expected_revision": (
                        "Expected revision is required "
                        "when updating a composition."
                    ),
                }
            )

        document = attrs.get(
            "document",
            getattr(
                self.instance,
                "document",
                {},
            ),
        )

        document_version = (
            document.get("version")
            if isinstance(document, dict)
            else None
        )

        if (
            document_version == 2
            and source_mode
            != CreativeComposition.SourceMode.GENERATED_BACKGROUND
        ):
            raise serializers.ValidationError(
                {
                    "source_mode": (
                        "Document v2 uses composition media "
                        "layers instead of the legacy "
                        "composition source."
                    ),
                }
            )
            
        return attrs

    def create(self, validated_data):
        validated_data.pop("expected_revision", None)

        source_reference = validated_data.pop(
            "source_reference",
            serializers.empty,
        )

        source_mode = validated_data.get(
            "source_mode",
            CreativeComposition.SourceMode.GENERATED_BACKGROUND,
        )

        self._normalize_source_fields(
            validated_data=validated_data,
            source_mode=source_mode,
            source_reference=source_reference,
        )

        try:
            return create_composition(
                owner=self.context["request"].user,
                validated_data=validated_data,
            )

        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict
                if hasattr(exc, "message_dict")
                else exc.messages
            )

    def update(self, instance, validated_data):
        expected_revision = validated_data.pop("expected_revision")

        source_reference = validated_data.pop(
            "source_reference",
            serializers.empty,
        )

        source_mode = validated_data.get(
            "source_mode",
            instance.source_mode,
        )

        self._normalize_source_fields(
            validated_data=validated_data,
            source_mode=source_mode,
            source_reference=source_reference,
        )

        try:
            result = update_composition(
                composition=instance,
                expected_revision=expected_revision,
                validated_data=validated_data,
            )

        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict
                if hasattr(exc, "message_dict")
                else exc.messages
            )

        return result.composition

    def _validate_explicit_source_conflicts(
        self,
        *,
        attrs: dict,
        source_mode: str,
        source_reference,
    ) -> None:
        source_image_was_supplied = "source_image" in attrs
        source_image = attrs.get("source_image")

        source_reference_was_supplied = (
            source_reference is not serializers.empty
        )

        if source_mode == CreativeComposition.SourceMode.UPLOAD:
            if source_reference_was_supplied and source_reference:
                raise serializers.ValidationError(
                    {
                        "source_reference": (
                            "Uploaded source mode cannot use "
                            "a content reference."
                        ),
                    }
                )

            return

        if source_mode == CreativeComposition.SourceMode.CONTENT_REFERENCE:
            if source_image_was_supplied and source_image:
                raise serializers.ValidationError(
                    {
                        "source_image": (
                            "Content reference mode cannot use "
                            "an uploaded source."
                        ),
                    }
                )

            return

        if source_mode == CreativeComposition.SourceMode.GENERATED_BACKGROUND:
            if source_image_was_supplied and source_image:
                raise serializers.ValidationError(
                    {
                        "source_image": (
                            "Generated background mode cannot use "
                            "an uploaded source."
                        ),
                    }
                )

            if source_reference_was_supplied and source_reference:
                raise serializers.ValidationError(
                    {
                        "source_reference": (
                            "Generated background mode cannot use "
                            "a content reference."
                        ),
                    }
                )

    def _normalize_source_fields(
        self,
        *,
        validated_data: dict,
        source_mode: str,
        source_reference,
    ) -> None:
        """
        Keep source fields mutually exclusive.
        """

        if source_mode == CreativeComposition.SourceMode.UPLOAD:
            self._clear_source_reference(validated_data)

            if "source_image" in validated_data:
                validated_data["source_image_is_converted"] = False

            return

        if source_mode == CreativeComposition.SourceMode.CONTENT_REFERENCE:
            validated_data["source_image"] = None
            validated_data["source_image_is_converted"] = False

            if source_reference is not serializers.empty:
                self._apply_source_reference(
                    validated_data,
                    source_reference,
                )

            return

        validated_data["source_image"] = None
        validated_data["source_image_is_converted"] = False

        self._clear_source_reference(validated_data)

    def _instance_has_source_reference(self) -> bool:
        return bool(
            self.instance
            and self.instance.source_content_type_id
            and self.instance.source_object_id
            and str(self.instance.source_field_name or "").strip()
        )

    def _clear_source_reference(
        self,
        validated_data: dict,
    ) -> None:
        validated_data["source_content_type"] = None
        validated_data["source_object_id"] = None
        validated_data["source_field_name"] = ""

    def _apply_source_reference(
        self,
        validated_data: dict,
        source_reference,
    ) -> None:
        """
        Resolve and normalize a source target.
        """

        if not source_reference:
            self._clear_source_reference(validated_data)
            return

        app_label = source_reference["app_label"].strip().lower()
        model = source_reference["model"].strip().lower()

        try:
            content_type = ContentType.objects.get_by_natural_key(
                app_label,
                model,
            )

        except ContentType.DoesNotExist:
            raise serializers.ValidationError(
                {
                    "source_reference": "Invalid app_label or model.",
                }
            )

        model_class = content_type.model_class()

        if model_class is None:
            raise serializers.ValidationError(
                {
                    "source_reference": "Source model is unavailable.",
                }
            )

        object_id = source_reference[
            "object_id"
        ]

        target = model_class.objects.filter(
            pk=object_id
        ).first()

        if target is None:
            raise serializers.ValidationError(
                {
                    "source_reference": (
                        "Source object does not exist."
                    ),
                }
            )

        field_name = source_reference[
            "field_name"
        ].strip()

        field = getattr(
            target,
            field_name,
            None,
        )

        if not field or not getattr(
            field,
            "name",
            None,
        ):
            raise serializers.ValidationError(
                {
                    "source_reference": (
                        "Source media field is unavailable."
                    ),
                }
            )

        authorization = getattr(
            target,
            "can_deliver_asset",
            None,
        )

        if not callable(authorization):
            raise serializers.ValidationError(
                {
                    "source_reference": (
                        "Source target does not support "
                        "secure asset delivery."
                    ),
                }
            )

        if not authorization(
            viewer=self.context["request"].user,
            field_name=field_name,
            intent="creative_editor_source",
        ):
            raise serializers.ValidationError(
                {
                    "source_reference": (
                        "You cannot use this source asset."
                    ),
                }
            )

        validated_data["source_content_type"] = (
            content_type
        )

        validated_data["source_object_id"] = (
            object_id
        )

        validated_data["source_field_name"] = (
            field_name
        )

        if not model_class.objects.filter(pk=object_id).exists():
            raise serializers.ValidationError(
                {
                    "source_reference": "Source object does not exist.",
                }
            )

        validated_data["source_content_type"] = content_type
        validated_data["source_object_id"] = object_id
        validated_data["source_field_name"] = (
            source_reference["field_name"].strip()
        )


class CreativeCompositionSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id")
    source_reference = serializers.SerializerMethodField()
    source_asset = serializers.SerializerMethodField()
    rendered_asset = serializers.SerializerMethodField()
    thumbnail_asset = serializers.SerializerMethodField()
    has_current_render = serializers.SerializerMethodField()

    class Meta:
        model = CreativeComposition

        fields = (
            "id",
            "title",
            "status",
            "visibility",
            "source_mode",
            "source_reference",
            "source_asset",
            "canvas_width",
            "canvas_height",
            "format_version",
            "revision",
            "document",
            "document_sha256",
            "rendered_revision",
            "rendered_at",
            "render_error",
            "rendered_asset",
            "thumbnail_asset",
            "has_current_render",
            "metadata",
            "is_active",
            "created_at",
            "updated_at",
        )

    def get_source_reference(self, obj):
        if not (
            obj.source_content_type_id
            and obj.source_object_id
            and obj.source_field_name
        ):
            return None

        return {
            "app_label": obj.source_content_type.app_label,
            "model": obj.source_content_type.model,
            "object_id": obj.source_object_id,
            "field_name": obj.source_field_name,
        }

    def get_source_asset(self, obj):
        if obj.source_mode == obj.SourceMode.UPLOAD and obj.source_image:
            return asset_target(
                obj,
                "source_image",
                "image",
            )

        if (
            obj.source_mode == obj.SourceMode.CONTENT_REFERENCE
            and obj.source_content_type_id
            and obj.source_object_id
            and obj.source_field_name
        ):
            target = obj.source_content_object

            if target is None:
                return None

            return asset_target(
                target,
                obj.source_field_name,
                "image",
            )

        return None

    def get_rendered_asset(self, obj):
        field_name = obj.rendered_field_name

        if not field_name:
            return None

        return asset_target(
            obj,
            field_name,
            obj.rendered_media_type or "image",
        )
        
    def get_thumbnail_asset(self, obj):
        if not obj.thumbnail:
            return None

        return asset_target(
            obj,
            "thumbnail",
            "thumbnail",
        )

    def get_has_current_render(self, obj) -> bool:
        return obj.has_current_render()


class CreativeRenderJobSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id")

    composition_id = serializers.UUIDField(
        source="composition.public_id",
    )

    is_active = serializers.BooleanField(read_only=True)
    is_terminal = serializers.BooleanField(read_only=True)

    class Meta:
        model = CreativeRenderJob

        fields = (
            "id",
            "composition_id",
            "requested_revision",
            "document_sha256",
            "status",
            "progress",
            "stage",
            "message",
            "error",
            "attempt",
            "max_attempts",
            "heartbeat_at",
            "started_at",
            "finished_at",
            "duration_ms",
            "is_active",
            "is_terminal",
            "created_at",
            "updated_at",
        )