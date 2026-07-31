# apps/creative_editor/management/commands/seed_creative_editor.py

from __future__ import annotations

from django.core.management.base import (
    BaseCommand,
)

from apps.creative_editor.models import (
    CreativeFont,
    StickerPack,
)


FONT_SEEDS = [
    {
        "key": "townlit-sans-regular",
        "display_name": "TownLIT Sans",
        "postscript_name": "DejaVuSans",
        "category": CreativeFont.Category.SANS_SERIF,
        "source": CreativeFont.Source.SYSTEM,
        "supports_ltr": True,
        "supports_rtl": True,
        "supports_bold": True,
        "supports_italic": False,
        "minimum_size": 12,
        "maximum_size": 160,
        "preview_text": "Create something meaningful",
        "sort_order": 10,
    },
    {
        "key": "townlit-sans-bold",
        "display_name": "TownLIT Sans Bold",
        "postscript_name": "DejaVuSans-Bold",
        "category": CreativeFont.Category.SANS_SERIF,
        "source": CreativeFont.Source.SYSTEM,
        "supports_ltr": True,
        "supports_rtl": True,
        "supports_bold": True,
        "supports_italic": False,
        "minimum_size": 12,
        "maximum_size": 180,
        "preview_text": "Faith over fear",
        "sort_order": 20,
    },
    {
        "key": "townlit-serif",
        "display_name": "TownLIT Serif",
        "postscript_name": "DejaVuSerif",
        "category": CreativeFont.Category.SERIF,
        "source": CreativeFont.Source.SYSTEM,
        "supports_ltr": True,
        "supports_rtl": True,
        "supports_bold": True,
        "supports_italic": False,
        "minimum_size": 12,
        "maximum_size": 170,
        "preview_text": "Grace and truth",
        "sort_order": 30,
    },
    {
        "key": "townlit-serif-bold",
        "display_name": "TownLIT Serif Bold",
        "postscript_name": "DejaVuSerif-Bold",
        "category": CreativeFont.Category.SERIF,
        "source": CreativeFont.Source.SYSTEM,
        "supports_ltr": True,
        "supports_rtl": True,
        "supports_bold": True,
        "supports_italic": False,
        "minimum_size": 12,
        "maximum_size": 180,
        "preview_text": "Grace and truth",
        "sort_order": 40,
    },
    {
        "key": "townlit-display",
        "display_name": "TownLIT Display",
        "postscript_name": "DejaVuSerif-Bold",
        "category": CreativeFont.Category.DISPLAY,
        "source": CreativeFont.Source.SYSTEM,
        "supports_ltr": True,
        "supports_rtl": True,
        "supports_bold": True,
        "supports_italic": False,
        "minimum_size": 16,
        "maximum_size": 190,
        "preview_text": "LIGHT",
        "sort_order": 50,
    },
    {
        "key": "townlit-mono",
        "display_name": "TownLIT Mono",
        "postscript_name": "DejaVuSansMono",
        "category": CreativeFont.Category.MONOSPACE,
        "source": CreativeFont.Source.SYSTEM,
        "supports_ltr": True,
        "supports_rtl": True,
        "supports_bold": True,
        "supports_italic": True,
        "minimum_size": 12,
        "maximum_size": 160,
        "preview_text": "Walk in the light",
        "sort_order": 60,
    },
    {
        "key": "townlit-mono-bold",
        "display_name": "TownLIT Mono Bold",
        "postscript_name": "DejaVuSansMono-Bold",
        "category": CreativeFont.Category.MONOSPACE,
        "source": CreativeFont.Source.SYSTEM,
        "supports_ltr": True,
        "supports_rtl": True,
        "supports_bold": True,
        "supports_italic": False,
        "minimum_size": 12,
        "maximum_size": 170,
        "preview_text": "Walk in the light",
        "sort_order": 70,
    },
    {
        "key": "townlit-mono-italic",
        "display_name": "TownLIT Mono Italic",
        "postscript_name": "DejaVuSansMono-Oblique",
        "category": CreativeFont.Category.MONOSPACE,
        "source": CreativeFont.Source.SYSTEM,
        "supports_ltr": True,
        "supports_rtl": True,
        "supports_bold": False,
        "supports_italic": True,
        "minimum_size": 12,
        "maximum_size": 170,
        "preview_text": "Be still and know",
        "sort_order": 80,
    },
    {
        "key": "townlit-arabic",
        "display_name": "TownLIT Persian & Arabic",
        "postscript_name": "DejaVuSans",
        "category": CreativeFont.Category.SANS_SERIF,
        "source": CreativeFont.Source.SYSTEM,
        "supports_ltr": False,
        "supports_rtl": True,
        "supports_bold": True,
        "supports_italic": False,
        "minimum_size": 14,
        "maximum_size": 180,
        "preview_text": "خدا محبت است",
        "sort_order": 90,
    },
]


PACK_SEEDS = [
    {
        "name": "TownLIT Essentials",
        "description": (
            "Core TownLIT symbols and community stickers."
        ),
        "cover_color": "#D8A94A",
        "is_featured": True,
        "is_active": True,
        "sort_order": 10,
    },
    {
        "name": "Faith",
        "description": (
            "Faith, hope, prayer, and encouragement."
        ),
        "cover_color": "#315B8A",
        "is_featured": True,
        "is_active": True,
        "sort_order": 20,
    },
    {
        "name": "Celebration",
        "description": (
            "Celebration and joyful moments."
        ),
        "cover_color": "#D98C5F",
        "is_featured": False,
        "is_active": True,
        "sort_order": 30,
    },
]


class Command(
    BaseCommand
):
    help = (
        "Seed Creative Editor fonts and sticker packs."
    )

    def handle(
        self,
        *args,
        **options,
    ):
        self._seed_fonts()
        self._seed_packs()

        self.stdout.write(
            self.style.SUCCESS(
                "Creative Editor seed completed."
            )
        )

    def _seed_fonts(
        self,
    ) -> None:
        for item in FONT_SEEDS:
            key = item["key"]

            defaults = {
                name: value
                for name, value in item.items()
                if name != "key"
            }

            font, created = (
                CreativeFont.objects
                .update_or_create(
                    key=key,
                    defaults=defaults,
                )
            )

            action = (
                "Created"
                if created
                else "Updated"
            )

            self.stdout.write(
                f"{action} font: {font.key}"
            )

    def _seed_packs(
        self,
    ) -> None:
        for item in PACK_SEEDS:
            name = item["name"]

            defaults = {
                field_name: value
                for field_name, value
                in item.items()
                if field_name != "name"
            }

            pack, created = (
                StickerPack.objects
                .update_or_create(
                    name=name,
                    defaults=defaults,
                )
            )

            action = (
                "Created"
                if created
                else "Updated"
            )

            self.stdout.write(
                f"{action} sticker pack: "
                f"{pack.name}"
            )
            

# sudo docker compose exec backend python manage.py seed_creative_editor