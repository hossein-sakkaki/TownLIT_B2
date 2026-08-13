# apps/creative_editor/management/commands/seed_creative_editor.py

from __future__ import annotations

import hashlib

from pathlib import Path

from django.conf import settings
from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.db import transaction

from fontTools.ttLib import TTFont

from apps.creative_editor.models import (
    CreativeFont,
    StickerPack,
)
from apps.creative_editor.services.font_resolver import (
    clear_font_caches,
)
from apps.creative_editor.services.font_coverage import (
    clear_font_coverage_caches,
)


# ---------------------------------------------------------------------
# Current migration policy
# ---------------------------------------------------------------------
#
# During the current Creative Font migration we intentionally remove
# every CreativeFont record that is not part of FONT_SEEDS so
# development and production converge to exactly the same catalog.
#
# In the future, once the migration period is over, this can be changed
# to False and old records can instead be retained/deactivated/versioned.
#
PRUNE_UNSEEDED_FONTS = True


# ---------------------------------------------------------------------
# Shared license metadata
# ---------------------------------------------------------------------

OFL_LICENSE_NAME = (
    "SIL Open Font License 1.1"
)

OFL_LICENSE_URL = (
    "https://openfontlicense.org/"
)

OFL_LICENSE_REFERENCE = (
    "Bundled OFL font asset"
)


# ---------------------------------------------------------------------
# Authoritative Creative Font Catalog
# ---------------------------------------------------------------------

CREATIVE_FONT_SEEDS = [
    {
        "key": "alfa-slab-one-regular",
        "display_name": "Alfa Slab One",
        "binary_filename": "AlfaSlabOne-Regular.ttf",
        "category": CreativeFont.Category.DISPLAY,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "ALFA",
        "sort_order": 10,
    },
    {
        "key": "amiri-regular",
        "display_name": "Amiri",
        "binary_filename": "Amiri-Regular.ttf",
        "category": CreativeFont.Category.SERIF,
        "supports_ltr": True,
        "supports_rtl": True,
        "preview_text": "خدا محبت است",
        "sort_order": 20,
    },
    {
        "key": "anton-regular",
        "display_name": "Anton",
        "binary_filename": "Anton-Regular.ttf",
        "category": CreativeFont.Category.DISPLAY,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "BOLD MOMENT",
        "sort_order": 30,
    },
    {
        "key": "bungee-regular",
        "display_name": "Bungee",
        "binary_filename": "Bungee-Regular.ttf",
        "category": CreativeFont.Category.DISPLAY,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "BUNGEE",
        "sort_order": 40,
    },
    {
        "key": "great-vibes-regular",
        "display_name": "Great Vibes",
        "binary_filename": "GreatVibes-Regular.ttf",
        "category": CreativeFont.Category.HANDWRITING,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "Great Vibes",
        "sort_order": 50,
    },
    {
        "key": "kalam-regular",
        "display_name": "Kalam",
        "binary_filename": "Kalam-Regular.ttf",
        "category": CreativeFont.Category.HANDWRITING,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "Write your story",
        "sort_order": 60,
    },
    {
        "key": "knewave-regular",
        "display_name": "Knewave",
        "binary_filename": "Knewave-Regular.ttf",
        "category": CreativeFont.Category.HANDWRITING,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "CREATE",
        "sort_order": 70,
    },
    {
        "key": "lobster-regular",
        "display_name": "Lobster",
        "binary_filename": "Lobster-Regular.ttf",
        "category": CreativeFont.Category.DISPLAY,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "Beautiful Moment",
        "sort_order": 80,
    },
    {
        "key": "marcellus-regular",
        "display_name": "Marcellus",
        "binary_filename": "Marcellus-Regular.ttf",
        "category": CreativeFont.Category.SERIF,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "A Meaningful Journey",
        "sort_order": 90,
    },
    {
        "key": "sacramento-regular",
        "display_name": "Sacramento",
        "binary_filename": "Sacramento-Regular.ttf",
        "category": CreativeFont.Category.HANDWRITING,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "Remember this moment",
        "sort_order": 100,
    },

    # -----------------------------------------------------------------
    # Second Creative Font Collection
    # -----------------------------------------------------------------

    {
        "key": "josefin-sans-regular",
        "display_name": "Josefin Sans",
        "binary_filename": "JosefinSans-Regular.ttf",
        "category": CreativeFont.Category.SANS_SERIF,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "Modern Story",
        "sort_order": 110,
    },
    {
        "key": "mali-regular",
        "display_name": "Mali",
        "binary_filename": "Mali-Regular.ttf",
        "category": CreativeFont.Category.HANDWRITING,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "Creative Story",
        "sort_order": 120,
    },
    {
        "key": "aref-ruqaa-ink-regular",
        "display_name": "Aref Ruqaa Ink",
        "binary_filename": "ArefRuqaaInk-Regular.ttf",
        "category": CreativeFont.Category.HANDWRITING,
        "supports_ltr": True,
        "supports_rtl": True,
        "preview_text": "الحياة جميلة",
        "sort_order": 130,
    },
    {
        "key": "noto-nastaliq-urdu-regular",
        "display_name": "Noto Nastaliq Urdu",
        "binary_filename": "NotoNastaliqUrdu-Regular.ttf",
        "category": CreativeFont.Category.HANDWRITING,
        "supports_ltr": True,
        "supports_rtl": True,
        "preview_text": "زندگی زیباست",
        "sort_order": 140,
    },
    {
        "key": "pacifico-regular",
        "display_name": "Pacifico",
        "binary_filename": "Pacifico-Regular.ttf",
        "category": CreativeFont.Category.HANDWRITING,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "Wonderful Day",
        "sort_order": 150,
    },
    {
        "key": "cinzel-decorative-regular",
        "display_name": "Cinzel Decorative",
        "binary_filename": "CinzelDecorative-Regular.ttf",
        "category": CreativeFont.Category.DISPLAY,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "TIMELESS",
        "sort_order": 160,
    },
    {
        "key": "londrina-sketch-regular",
        "display_name": "Londrina Sketch",
        "binary_filename": "LondrinaSketch-Regular.ttf",
        "category": CreativeFont.Category.DISPLAY,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "SKETCH",
        "sort_order": 170,
    },
    {
        "key": "monoton-regular",
        "display_name": "Monoton",
        "binary_filename": "Monoton-Regular.ttf",
        "category": CreativeFont.Category.DISPLAY,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "NEON",
        "sort_order": 180,
    },
    {
        "key": "press-start-2p-regular",
        "display_name": "Press Start 2P",
        "binary_filename": "PressStart2P-Regular.ttf",
        "category": CreativeFont.Category.MONOSPACE,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "SYSTEM READY",
        "sort_order": 190,
    },
    {
        "key": "yatra-one-regular",
        "display_name": "Yatra One",
        "binary_filename": "YatraOne-Regular.ttf",
        "category": CreativeFont.Category.DISPLAY,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "यात्रा",
        "sort_order": 200,
    },
]

# ---------------------------------------------------------------------
# Hidden Global Font Fallback Catalog
# ---------------------------------------------------------------------

FALLBACK_FONT_SEEDS = [
    {
        "key": "noto-sans-regular",
        "display_name": "Noto Sans",
        "binary_filename": "NotoSans-Regular.ttf",
        "category": CreativeFont.Category.SANS_SERIF,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "TownLIT",
        "is_user_selectable": False,
        "sort_order": 1990,
    },
    {
        "key": "noto-sans-arabic-regular",
        "display_name": "Noto Sans Arabic",
        "binary_filename": "NotoSansArabic-Regular.ttf",
        "category": CreativeFont.Category.SANS_SERIF,
        "supports_ltr": True,
        "supports_rtl": True,
        "preview_text": "خدا محبت است",
        "is_user_selectable": False,
        "sort_order": 1010,
    },
    {
        "key": "noto-sans-hebrew-regular",
        "display_name": "Noto Sans Hebrew",
        "binary_filename": "NotoSansHebrew-Regular.ttf",
        "category": CreativeFont.Category.SANS_SERIF,
        "supports_ltr": False,
        "supports_rtl": True,
        "preview_text": "שלום",
        "is_user_selectable": False,
        "sort_order": 1020,
    },
    {
        "key": "noto-sans-devanagari-regular",
        "display_name": "Noto Sans Devanagari",
        "binary_filename": "NotoSansDevanagari-Regular.ttf",
        "category": CreativeFont.Category.SANS_SERIF,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "नमस्ते",
        "is_user_selectable": False,
        "sort_order": 1030,
    },
    {
        "key": "noto-sans-bengali-regular",
        "display_name": "Noto Sans Bengali",
        "binary_filename": "NotoSansBengali-Regular.ttf",
        "category": CreativeFont.Category.SANS_SERIF,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "বাংলা",
        "is_user_selectable": False,
        "sort_order": 1040,
    },
    {
        "key": "noto-sans-gurmukhi-regular",
        "display_name": "Noto Sans Gurmukhi",
        "binary_filename": "NotoSansGurmukhi-Regular.ttf",
        "category": CreativeFont.Category.SANS_SERIF,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "ਪੰਜਾਬੀ",
        "is_user_selectable": False,
        "sort_order": 1050,
    },
    {
        "key": "noto-sans-gujarati-regular",
        "display_name": "Noto Sans Gujarati",
        "binary_filename": "NotoSansGujarati-Regular.ttf",
        "category": CreativeFont.Category.SANS_SERIF,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "ગુજરાતી",
        "is_user_selectable": False,
        "sort_order": 1060,
    },
    {
        "key": "noto-sans-oriya-regular",
        "display_name": "Noto Sans Oriya",
        "binary_filename": "NotoSansOriya-Regular.ttf",
        "category": CreativeFont.Category.SANS_SERIF,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "ଓଡ଼ିଆ",
        "is_user_selectable": False,
        "sort_order": 1070,
    },
    {
        "key": "noto-sans-tamil-regular",
        "display_name": "Noto Sans Tamil",
        "binary_filename": "NotoSansTamil-Regular.ttf",
        "category": CreativeFont.Category.SANS_SERIF,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "தமிழ்",
        "is_user_selectable": False,
        "sort_order": 1080,
    },
    {
        "key": "noto-sans-telugu-regular",
        "display_name": "Noto Sans Telugu",
        "binary_filename": "NotoSansTelugu-Regular.ttf",
        "category": CreativeFont.Category.SANS_SERIF,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "తెలుగు",
        "is_user_selectable": False,
        "sort_order": 1090,
    },
    {
        "key": "noto-sans-kannada-regular",
        "display_name": "Noto Sans Kannada",
        "binary_filename": "NotoSansKannada_SemiCondensed-Regular.ttf",
        "category": CreativeFont.Category.SANS_SERIF,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "ಕನ್ನಡ",
        "is_user_selectable": False,
        "sort_order": 1100,
    },
    {
        "key": "noto-sans-malayalam-regular",
        "display_name": "Noto Sans Malayalam",
        "binary_filename": "NotoSansMalayalam-Regular.ttf",
        "category": CreativeFont.Category.SANS_SERIF,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "മലയാളം",
        "is_user_selectable": False,
        "sort_order": 1110,
    },
    {
        "key": "noto-sans-sinhala-regular",
        "display_name": "Noto Sans Sinhala",
        "binary_filename": "NotoSansSinhala-Regular.ttf",
        "category": CreativeFont.Category.SANS_SERIF,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "සිංහල",
        "is_user_selectable": False,
        "sort_order": 1120,
    },
    {
        "key": "noto-sans-thai-regular",
        "display_name": "Noto Sans Thai",
        "binary_filename": "NotoSansThai-Regular.ttf",
        "category": CreativeFont.Category.SANS_SERIF,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "ภาษาไทย",
        "is_user_selectable": False,
        "sort_order": 1130,
    },
    {
        "key": "noto-sans-lao-regular",
        "display_name": "Noto Sans Lao",
        "binary_filename": "NotoSansLao-Regular.ttf",
        "category": CreativeFont.Category.SANS_SERIF,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "ພາສາລາວ",
        "is_user_selectable": False,
        "sort_order": 1140,
    },
    {
        "key": "noto-sans-khmer-regular",
        "display_name": "Noto Sans Khmer",
        "binary_filename": "NotoSansKhmer-Regular.ttf",
        "category": CreativeFont.Category.SANS_SERIF,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "ភាសាខ្មែរ",
        "is_user_selectable": False,
        "sort_order": 1150,
    },
    {
        "key": "noto-sans-myanmar-regular",
        "display_name": "Noto Sans Myanmar",
        "binary_filename": "NotoSansMyanmar-Regular.ttf",
        "category": CreativeFont.Category.SANS_SERIF,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "မြန်မာ",
        "is_user_selectable": False,
        "sort_order": 1160,
    },
    {
        "key": "noto-sans-armenian-regular",
        "display_name": "Noto Sans Armenian",
        "binary_filename": "NotoSansArmenian-Regular.ttf",
        "category": CreativeFont.Category.SANS_SERIF,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "Հայերեն",
        "is_user_selectable": False,
        "sort_order": 1170,
    },
    {
        "key": "noto-sans-georgian-regular",
        "display_name": "Noto Sans Georgian",
        "binary_filename": "NotoSansGeorgian-Regular.ttf",
        "category": CreativeFont.Category.SANS_SERIF,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "ქართული",
        "is_user_selectable": False,
        "sort_order": 1180,
    },
    {
        "key": "noto-sans-ethiopic-regular",
        "display_name": "Noto Sans Ethiopic",
        "binary_filename": "NotoSansEthiopic-Regular.ttf",
        "category": CreativeFont.Category.SANS_SERIF,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "አማርኛ",
        "is_user_selectable": False,
        "sort_order": 1190,
    },
    {
        "key": "noto-sans-cjk-sc-regular",
        "display_name": "Noto Sans CJK SC",
        "binary_filename": "NotoSansCJKsc-Regular.otf",
        "category": CreativeFont.Category.SANS_SERIF,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "中文 日本語 한국어",
        "is_user_selectable": False,
        "sort_order": 1200,
    },
    {
        "key": "noto-sans-symbols-2-regular",
        "display_name": "Noto Sans Symbols 2",
        "binary_filename": "NotoSansSymbols2-Regular.ttf",
        "category": CreativeFont.Category.OTHER,
        "supports_ltr": True,
        "supports_rtl": False,
        "preview_text": "★ → ✓ ∞",
        "is_user_selectable": False,
        "sort_order": 2000,
    },
]

# ---------------------------------------------------------------------
# Complete Authoritative Font Catalog
# ---------------------------------------------------------------------

FONT_SEEDS = [
    *CREATIVE_FONT_SEEDS,
    *FALLBACK_FONT_SEEDS,
]


# ---------------------------------------------------------------------
# Sticker Packs
# ---------------------------------------------------------------------

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
        "Seed authoritative Creative Editor fonts "
        "and sticker packs."
    )

    def handle(
        self,
        *args,
        **options,
    ) -> None:
        self.stdout.write(
            "Validating Creative Editor font assets..."
        )

        validated_fonts = (
            self._validate_font_assets()
        )

        with transaction.atomic():
            if PRUNE_UNSEEDED_FONTS:
                self._remove_unseeded_fonts()

            self._seed_fonts(
                validated_fonts
            )

            self._seed_packs()

        clear_font_caches()
        clear_font_coverage_caches()

        selectable_count = sum(
            1
            for item in validated_fonts
            if item.get(
                "is_user_selectable",
                True,
            )
        )

        fallback_count = (
            len(validated_fonts)
            - selectable_count
        )

        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Creative Editor seed completed. "
                    f"{selectable_count} selectable fonts, "
                    f"{fallback_count} hidden fallback fonts."
                )
            )
        )

    # MARK: - Font Directory

    def _font_directory(
        self,
    ) -> Path:
        configured = getattr(
            settings,
            "CREATIVE_EDITOR_FONT_DIR",
            None,
        )

        if not configured:
            raise CommandError(
                (
                    "CREATIVE_EDITOR_FONT_DIR "
                    "is not configured."
                )
            )

        directory = Path(
            configured
        ).resolve()

        if not directory.is_dir():
            raise CommandError(
                (
                    "Creative Editor font directory "
                    f"does not exist: {directory}"
                )
            )

        return directory

    # MARK: - Font Validation

    def _validate_font_assets(
        self,
    ) -> list[dict]:
        directory = (
            self._font_directory()
        )

        validated = []

        seen_keys = set()
        seen_filenames = set()

        for seed in FONT_SEEDS:
            key = str(
                seed["key"]
            ).strip()

            filename = str(
                seed["binary_filename"]
            ).strip()

            is_user_selectable = bool(
                seed.get(
                    "is_user_selectable",
                    True,
                )
            )

            if (
                not is_user_selectable
                and not filename
            ):
                raise CommandError(
                    (
                        "Hidden Creative Font fallback "
                        f"'{key}' requires a bundled binary."
                    )
                )
    
            if key in seen_keys:
                raise CommandError(
                    (
                        "Duplicate Creative Font key "
                        f"in seed: {key}"
                    )
                )

            if filename in seen_filenames:
                raise CommandError(
                    (
                        "Duplicate Creative Font binary "
                        f"in seed: {filename}"
                    )
                )

            seen_keys.add(
                key
            )

            seen_filenames.add(
                filename
            )

            path = (
                directory
                / filename
            ).resolve()

            try:
                path.relative_to(
                    directory
                )

            except ValueError as exc:
                raise CommandError(
                    (
                        "Unsafe Creative Font path "
                        f"for '{key}'."
                    )
                ) from exc

            if not path.is_file():
                raise CommandError(
                    (
                        "Missing Creative Font binary "
                        f"for '{key}': {path}"
                    )
                )

            sha256 = self._sha256(
                path
            )

            metadata = (
                self._read_font_metadata(
                    path
                )
            )

            postscript_name = metadata[
                "postscript_name"
            ]

            validated_item = {
                **seed,
                "postscript_name":
                    postscript_name,
                "asset_sha256":
                    sha256,
            }

            validated.append(
                validated_item
            )

            self.stdout.write(
                self.style.SUCCESS(
                    (
                        "Validated font: "
                        f"{key} "
                        f"[{postscript_name}] "
                        f"sha256={sha256}"
                    )
                )
            )

        return validated

    # MARK: - Binary Metadata

    @staticmethod
    def _sha256(
        path: Path,
    ) -> str:
        digest = hashlib.sha256()

        with path.open(
            "rb"
        ) as file_obj:
            for chunk in iter(
                lambda:
                    file_obj.read(
                        1024 * 1024
                    ),
                b"",
            ):
                digest.update(
                    chunk
                )

        return digest.hexdigest()

    @staticmethod
    def _read_font_metadata(
        path: Path,
    ) -> dict[str, str]:
        font = TTFont(
            str(path),
            lazy=True,
        )

        try:
            postscript_names = []

            for record in (
                font["name"].names
            ):
                if record.nameID != 6:
                    continue

                try:
                    value = (
                        record
                        .toUnicode()
                        .strip()
                    )

                except Exception:
                    continue

                if (
                    value
                    and value
                    not in postscript_names
                ):
                    postscript_names.append(
                        value
                    )

            if not postscript_names:
                raise CommandError(
                    (
                        "Font has no PostScript name: "
                        f"{path.name}"
                    )
                )

            if len(postscript_names) != 1:
                raise CommandError(
                    (
                        "Font exposes multiple "
                        "PostScript names: "
                        f"{path.name} -> "
                        f"{postscript_names}"
                    )
                )

            return {
                "postscript_name":
                    postscript_names[0],
            }

        except KeyError as exc:
            raise CommandError(
                (
                    "Font does not contain a valid "
                    f"name table: {path.name}"
                )
            ) from exc

        finally:
            font.close()

    # MARK: - Migration Cleanup

    def _remove_unseeded_fonts(
        self,
    ) -> None:
        authoritative_keys = {
            item["key"]
            for item in FONT_SEEDS
        }

        queryset = (
            CreativeFont.objects
            .exclude(
                key__in=
                    authoritative_keys
            )
        )

        existing_keys = list(
            queryset
            .values_list(
                "key",
                flat=True,
            )
            .order_by(
                "key"
            )
        )

        if not existing_keys:
            self.stdout.write(
                (
                    "No unseeded Creative Editor "
                    "fonts found."
                )
            )

            return

        for key in existing_keys:
            self.stdout.write(
                self.style.WARNING(
                    (
                        "Removing unseeded font: "
                        f"{key}"
                    )
                )
            )

        queryset.delete()

        self.stdout.write(
            self.style.WARNING(
                (
                    "Removed "
                    f"{len(existing_keys)} "
                    "unseeded Creative Font records."
                )
            )
        )

    # MARK: - Font Seed

    def _seed_fonts(
        self,
        fonts: list[dict],
    ) -> None:
        for item in fonts:
            key = item[
                "key"
            ]

            defaults = {
                "display_name":
                    item[
                        "display_name"
                    ],
                "postscript_name":
                    item[
                        "postscript_name"
                    ],
                "category":
                    item[
                        "category"
                    ],
                "source":
                    CreativeFont
                    .Source
                    .BUNDLED,
                "binary_filename":
                    item[
                        "binary_filename"
                    ],
                "asset_version":
                    "1",
                "asset_sha256":
                    item[
                        "asset_sha256"
                    ],
                    
                "supports_ltr": item["supports_ltr"],
                "supports_rtl": item["supports_rtl"],
                "supports_bold": False,
                "supports_italic": False,
                "is_user_selectable": item.get(
                    "is_user_selectable",
                    True,
                ),
                "minimum_size": 12,
                "maximum_size": 160,
                    
                "preview_text":
                    item[
                        "preview_text"
                    ],
                "license_name":
                    OFL_LICENSE_NAME,
                "license_url":
                    OFL_LICENSE_URL,
                "license_reference":
                    OFL_LICENSE_REFERENCE,
                "copyright_notice":
                    "",
                "is_active":
                    True,
                "sort_order":
                    item[
                        "sort_order"
                    ],
            }

            font, created = (
                CreativeFont.objects
                .update_or_create(
                    key=key,
                    defaults=defaults,
                )
            )

            font.full_clean()
            font.save()

            action = (
                "Created"
                if created
                else "Updated"
            )

            self.stdout.write(
                self.style.SUCCESS(
                    (
                        f"{action} font: "
                        f"{font.key} "
                        f"[{font.postscript_name}]"
                    )
                )
            )

    # MARK: - Sticker Pack Seed

    def _seed_packs(
        self,
    ) -> None:
        for item in PACK_SEEDS:
            name = item[
                "name"
            ]

            defaults = {
                field_name:
                    value
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
                (
                    f"{action} sticker pack: "
                    f"{pack.name}"
                )
            )

# sudo docker compose exec backend python manage.py seed_creative_editor