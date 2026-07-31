# apps/creative_editor/serializers/assets.py

from __future__ import annotations

from rest_framework import serializers

from apps.creative_editor.models import (
    CreativeBackgroundPreset,
    CreativeFont,
    StickerAsset,
    StickerPack,
)

def asset_target(obj, field_name: str, kind: str) -> dict:
    """
    Build an Asset Delivery target.
    """

    return {
        "app_label": obj._meta.app_label,
        "model": obj._meta.model_name,
        "object_id": obj.pk,
        "field_name": field_name,
        "kind": kind,
    }


class CreativeFontSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id")

    class Meta:
        model = CreativeFont

        fields = (
            "id",
            "key",
            "display_name",
            "postscript_name",
            "category",
            "source",
            "supports_ltr",
            "supports_rtl",
            "supports_bold",
            "supports_italic",
            "minimum_size",
            "maximum_size",
            "preview_text",
            "metadata",
        )


class StickerAssetSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id")
    asset = serializers.SerializerMethodField()

    class Meta:
        model = StickerAsset

        fields = (
            "id",
            "title",
            "slug",
            "description",
            "width",
            "height",
            "aspect_ratio",
            "dominant_color",
            "blurhash",
            "is_featured",
            "asset",
            "metadata",
        )

    def get_asset(self, obj) -> dict:
        return asset_target(
            obj,
            "image",
            "image",
        )


class StickerPackSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id")
    stickers = serializers.SerializerMethodField()

    class Meta:
        model = StickerPack

        fields = (
            "id",
            "name",
            "slug",
            "description",
            "cover_color",
            "is_featured",
            "metadata",
            "stickers",
        )

    def get_stickers(self, obj):
        items = [
            sticker
            for sticker in obj.stickers.all()
            if sticker.is_active and sticker.is_converted
        ]

        return StickerAssetSerializer(
            items,
            many=True,
            context=self.context,
        ).data


class CreativeBackgroundPresetSerializer(
    serializers.ModelSerializer
):
    id = serializers.UUIDField(
        source="public_id",
    )

    background = serializers.SerializerMethodField()

    class Meta:
        model = CreativeBackgroundPreset

        fields = (
            "id",
            "key",
            "title",
            "description",
            "background_type",
            "background",
            "supported_consumers",
            "is_featured",
            "metadata",
        )

    def get_background(
        self,
        obj: CreativeBackgroundPreset,
    ) -> dict:
        return obj.as_document_background()
    

class CreativeEditorBootstrapSerializer(serializers.Serializer):
    fonts = CreativeFontSerializer(many=True)

    sticker_packs = StickerPackSerializer(
        many=True,
    )

    backgrounds = CreativeBackgroundPresetSerializer(
        many=True,
    )

    limits = serializers.DictField()
    capabilities = serializers.DictField()