# apps/creative_editor/management/commands/seed_creative_backgrounds.py

from __future__ import annotations

from copy import deepcopy
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.creative_editor.models import (
    CreativeBackgroundPreset,
)


# =========================================================
# Shared consumers
# =========================================================

ALL_CONSUMERS: list[str] = []

JOURNEY_FOCUSED_CONSUMERS: list[str] = [
    "journey",
]

STORYTELLING_CONSUMERS: list[str] = [
    "journey",
    "moment",
    "testimony",
    "announcement",
]


# =========================================================
# TownLIT design palette
# =========================================================

TOWNLIT_COLORS = {
    # Brand
    "primary": "#0F52BAFF",
    "accent": "#3BAA75FF",
    "secondary": "#F8F6F0FF",
    "bright": "#FDFDFDFF",
    "glory": "#F6C860FF",
    "dark": "#2B2C30FF",
    "dark_background": "#121212FF",
    "black": "#050505FF",
    "highlight": "#7FDBDAFF",

    # Functional
    "success": "#3BAA75FF",
    "danger": "#C40233FF",
    "warning": "#F4A429FF",
    "admin": "#7A5CA2FF",
    "vip": "#A23BECFF",

    # Revelation-inspired existing tokens
    "jasper": "#D73F09FF",
    "agate": "#F0E3C3FF",
    "turquoise": "#48D1CCFF",

    # Neutral family
    "dark_softer": "#EEECE6FF",
    "dark_soft": "#D2D0CDFF",
    "dark_strong": "#A6A6A3FF",
    "dark_stronger": "#6F6F6FFF",
}


# =========================================================
# Revelation 21 stone palette
#
# These are curated UI approximations for TownLIT.
# Historical translations and mineral identifications vary.
# =========================================================

REVELATION_STONES = {
    "jasper": {
        "title": "Jasper",
        "color": "#D73F09FF",
        "light": "#F47A4FFF",
        "dark": "#7B2108FF",
        "description": (
            "A rich earthy-red interpretation of Jasper."
        ),
    },
    "sapphire": {
        "title": "Sapphire",
        "color": "#0F52BAFF",
        "light": "#4D8BE7FF",
        "dark": "#082B68FF",
        "description": (
            "A deep luminous blue inspired by Sapphire."
        ),
    },
    "chalcedony": {
        "title": "Chalcedony",
        "color": "#B9DDE6FF",
        "light": "#E8F6F8FF",
        "dark": "#659BA9FF",
        "description": (
            "A soft blue-grey interpretation of Chalcedony."
        ),
    },
    "emerald": {
        "title": "Emerald",
        "color": "#3BAA75FF",
        "light": "#78D7A5FF",
        "dark": "#1D6545FF",
        "description": (
            "A vivid green inspired by Emerald."
        ),
    },
    "sardonyx": {
        "title": "Sardonyx",
        "color": "#B96A55FF",
        "light": "#E9B3A3FF",
        "dark": "#67372DFF",
        "description": (
            "Warm layered rose and earth tones inspired by Sardonyx."
        ),
    },
    "carnelian": {
        "title": "Carnelian",
        "color": "#C84A2AFF",
        "light": "#F18A64FF",
        "dark": "#762515FF",
        "description": (
            "A glowing red-orange interpretation of Carnelian."
        ),
    },
    "chrysolite": {
        "title": "Chrysolite",
        "color": "#A8C64AFF",
        "light": "#D9E989FF",
        "dark": "#61752AFF",
        "description": (
            "A green-gold interpretation of Chrysolite."
        ),
    },
    "beryl": {
        "title": "Beryl",
        "color": "#7FDBDAFF",
        "light": "#B9F1EFFF",
        "dark": "#378D8CFF",
        "description": (
            "A clear aqua interpretation of Beryl."
        ),
    },
    "topaz": {
        "title": "Topaz",
        "color": "#F4A429FF",
        "light": "#FFD486FF",
        "dark": "#A75F08FF",
        "description": (
            "A warm amber-gold interpretation of Topaz."
        ),
    },
    "chrysoprase": {
        "title": "Chrysoprase",
        "color": "#66C98CFF",
        "light": "#A8E8BDFF",
        "dark": "#34754DFF",
        "description": (
            "A fresh apple-green interpretation of Chrysoprase."
        ),
    },
    "jacinth": {
        "title": "Jacinth",
        "color": "#A23BECFF",
        "light": "#D18BFFFF",
        "dark": "#5D168FFF",
        "description": (
            "A radiant violet interpretation of Jacinth."
        ),
    },
    "amethyst": {
        "title": "Amethyst",
        "color": "#7A5CA2FF",
        "light": "#B79AD5FF",
        "dark": "#44305FFF",
        "description": (
            "A contemplative purple inspired by Amethyst."
        ),
    },
}


# =========================================================
# Builders
# =========================================================

def solid_preset(
    *,
    key: str,
    title: str,
    color: str,
    description: str,
    sort_order: int,
    family: str,
    tags: list[str],
    is_featured: bool = False,
    supported_consumers: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_metadata = {
        "family": family,
        "presentation": "solid",
        "palette": [color],
        "tags": tags,
        **(metadata or {}),
    }

    return {
        "key": key,
        "title": title,
        "description": description,
        "background_type": "color",
        "color": color,
        "colors": [],
        "angle": 90.0,
        "supported_consumers": (
            supported_consumers
            if supported_consumers is not None
            else deepcopy(ALL_CONSUMERS)
        ),
        "metadata": resolved_metadata,
        "is_featured": is_featured,
        "is_active": True,
        "sort_order": sort_order,
    }


def gradient_preset(
    *,
    key: str,
    title: str,
    colors: list[str],
    angle: float,
    description: str,
    sort_order: int,
    family: str,
    tags: list[str],
    is_featured: bool = False,
    supported_consumers: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_metadata = {
        "family": family,
        "presentation": "gradient",
        "palette": list(colors),
        "tags": tags,
        **(metadata or {}),
    }

    return {
        "key": key,
        "title": title,
        "description": description,
        "background_type": "gradient",
        "color": "",
        "colors": colors,
        "angle": float(angle),
        "supported_consumers": (
            supported_consumers
            if supported_consumers is not None
            else deepcopy(ALL_CONSUMERS)
        ),
        "metadata": resolved_metadata,
        "is_featured": is_featured,
        "is_active": True,
        "sort_order": sort_order,
    }


# =========================================================
# Catalog
# =========================================================

def build_background_presets() -> list[dict[str, Any]]:
    presets: list[dict[str, Any]] = []

    # -----------------------------------------------------
    # 1. TownLIT essentials
    # -----------------------------------------------------

    presets.extend(
        [
            solid_preset(
                key="townlit-sapphire",
                title="TownLIT Sapphire",
                color=TOWNLIT_COLORS["primary"],
                description=(
                    "TownLIT primary sapphire blue."
                ),
                sort_order=10,
                family="townlit",
                tags=[
                    "brand",
                    "blue",
                    "bold",
                    "sapphire",
                ],
                is_featured=True,
            ),
            solid_preset(
                key="townlit-emerald",
                title="TownLIT Emerald",
                color=TOWNLIT_COLORS["accent"],
                description=(
                    "TownLIT emerald accent green."
                ),
                sort_order=20,
                family="townlit",
                tags=[
                    "brand",
                    "green",
                    "fresh",
                    "emerald",
                ],
                is_featured=True,
            ),
            solid_preset(
                key="townlit-pearl",
                title="TownLIT Pearl",
                color=TOWNLIT_COLORS["secondary"],
                description=(
                    "A warm pearl background for calm and reflective content."
                ),
                sort_order=30,
                family="townlit",
                tags=[
                    "brand",
                    "light",
                    "neutral",
                    "pearl",
                ],
                is_featured=True,
            ),
            solid_preset(
                key="townlit-glory",
                title="TownLIT Glory",
                color=TOWNLIT_COLORS["glory"],
                description=(
                    "TownLIT glory gold."
                ),
                sort_order=40,
                family="townlit",
                tags=[
                    "brand",
                    "gold",
                    "warm",
                    "glory",
                ],
                is_featured=True,
            ),
            solid_preset(
                key="townlit-onyx",
                title="TownLIT Onyx",
                color=TOWNLIT_COLORS["dark"],
                description=(
                    "A refined dark surface inspired by Onyx."
                ),
                sort_order=50,
                family="townlit",
                tags=[
                    "brand",
                    "dark",
                    "neutral",
                    "onyx",
                ],
                is_featured=True,
            ),
            solid_preset(
                key="townlit-black",
                title="TownLIT Black",
                color=TOWNLIT_COLORS["black"],
                description=(
                    "A deep near-black creative background."
                ),
                sort_order=60,
                family="townlit",
                tags=[
                    "brand",
                    "black",
                    "dark",
                    "minimal",
                ],
            ),
            solid_preset(
                key="townlit-highlight",
                title="TownLIT Highlight",
                color=TOWNLIT_COLORS["highlight"],
                description=(
                    "A bright Beryl-inspired highlight surface."
                ),
                sort_order=70,
                family="townlit",
                tags=[
                    "brand",
                    "aqua",
                    "bright",
                    "beryl",
                ],
            ),
            solid_preset(
                key="townlit-ruby",
                title="TownLIT Ruby",
                color=TOWNLIT_COLORS["danger"],
                description=(
                    "A strong ruby red creative background."
                ),
                sort_order=80,
                family="townlit",
                tags=[
                    "brand",
                    "red",
                    "dramatic",
                    "ruby",
                ],
            ),
            solid_preset(
                key="townlit-topaz",
                title="TownLIT Topaz",
                color=TOWNLIT_COLORS["warning"],
                description=(
                    "A warm Topaz-inspired amber background."
                ),
                sort_order=90,
                family="townlit",
                tags=[
                    "brand",
                    "amber",
                    "warm",
                    "topaz",
                ],
            ),
            solid_preset(
                key="townlit-amethyst",
                title="TownLIT Amethyst",
                color=TOWNLIT_COLORS["admin"],
                description=(
                    "TownLIT contemplative Amethyst purple."
                ),
                sort_order=100,
                family="townlit",
                tags=[
                    "brand",
                    "purple",
                    "calm",
                    "amethyst",
                ],
            ),
        ]
    )

    # -----------------------------------------------------
    # 2. Revelation 21 foundations — twelve solid stones
    # -----------------------------------------------------

    stone_sort_order = 200

    for stone_key, stone in REVELATION_STONES.items():
        presets.append(
            solid_preset(
                key=f"revelation-{stone_key}",
                title=stone["title"],
                color=stone["color"],
                description=stone["description"],
                sort_order=stone_sort_order,
                family="revelation_stones",
                tags=[
                    "revelation-21",
                    "foundation-stone",
                    stone_key,
                    "biblical",
                    "solid",
                ],
                is_featured=stone_key in {
                    "jasper",
                    "sapphire",
                    "emerald",
                    "beryl",
                    "amethyst",
                },
                metadata={
                    "biblical_reference": (
                        "Revelation 21:19-20"
                    ),
                    "stone_key": stone_key,
                    "light_variant": stone["light"],
                    "dark_variant": stone["dark"],
                    "color_interpretation": (
                        "TownLIT UI approximation"
                    ),
                },
            )
        )

        stone_sort_order += 10

    # -----------------------------------------------------
    # 3. TownLIT signature gradients
    # -----------------------------------------------------

    presets.extend(
        [
            gradient_preset(
                key="townlit-signature",
                title="TownLIT Signature",
                colors=[
                    "#071A33FF",
                    TOWNLIT_COLORS["primary"],
                    TOWNLIT_COLORS["glory"],
                ],
                angle=135,
                description=(
                    "TownLIT sapphire, midnight and glory gold."
                ),
                sort_order=400,
                family="townlit_signature",
                tags=[
                    "brand",
                    "signature",
                    "blue",
                    "gold",
                    "premium",
                ],
                is_featured=True,
            ),
            gradient_preset(
                key="townlit-glory-light",
                title="Glory Light",
                colors=[
                    "#E6C15DFF",
                    "#F8D878FF",
                    "#F6C860FF",
                    "#E2A93BFF",
                    "#FFD451FF",
                ],
                angle=135,
                description=(
                    "A luminous multi-stop TownLIT glory gradient."
                ),
                sort_order=410,
                family="townlit_signature",
                tags=[
                    "brand",
                    "glory",
                    "gold",
                    "light",
                    "celebration",
                ],
                is_featured=True,
            ),
            gradient_preset(
                key="townlit-living-emerald",
                title="Living Emerald",
                colors=[
                    "#A6F2C0FF",
                    "#52D89DFF",
                    "#3BAA75FF",
                    "#267A54FF",
                ],
                angle=135,
                description=(
                    "A living green gradient based on TownLIT accent colors."
                ),
                sort_order=420,
                family="townlit_signature",
                tags=[
                    "brand",
                    "emerald",
                    "green",
                    "living",
                    "fresh",
                ],
                is_featured=True,
            ),
            gradient_preset(
                key="townlit-pearl-dawn",
                title="Pearl Dawn",
                colors=[
                    "#F9F8F4FF",
                    "#F5F1EAFF",
                    "#EEE6DBFF",
                    "#F4F1EBFF",
                    "#F9F8F4FF",
                ],
                angle=290,
                description=(
                    "A soft pearl and ivory gradient for reflective stories."
                ),
                sort_order=430,
                family="townlit_signature",
                tags=[
                    "brand",
                    "pearl",
                    "light",
                    "calm",
                    "reflective",
                ],
                is_featured=True,
            ),
            gradient_preset(
                key="townlit-midnight-glory",
                title="Midnight Glory",
                colors=[
                    "#050505FF",
                    "#121212FF",
                    "#2B2C30FF",
                    "#6D5523FF",
                    "#F6C860FF",
                ],
                angle=145,
                description=(
                    "Deep black and Onyx lifted by TownLIT glory gold."
                ),
                sort_order=440,
                family="townlit_signature",
                tags=[
                    "brand",
                    "black",
                    "gold",
                    "cinematic",
                    "premium",
                ],
                is_featured=True,
            ),
            gradient_preset(
                key="townlit-sapphire-light",
                title="Sapphire Light",
                colors=[
                    "#071A33FF",
                    "#0F52BAFF",
                    "#4D8BE7FF",
                    "#7FDBDAFF",
                ],
                angle=45,
                description=(
                    "A radiant blue journey from midnight to Beryl light."
                ),
                sort_order=450,
                family="townlit_signature",
                tags=[
                    "brand",
                    "blue",
                    "aqua",
                    "radiant",
                    "sapphire",
                ],
                is_featured=True,
            ),
            gradient_preset(
                key="townlit-royal-purple",
                title="Royal Promise",
                colors=[
                    "#2B183DFF",
                    "#7A5CA2FF",
                    "#A23BECFF",
                    "#F6C860FF",
                ],
                angle=135,
                description=(
                    "Amethyst, Jacinth and Glory in a royal gradient."
                ),
                sort_order=460,
                family="townlit_signature",
                tags=[
                    "brand",
                    "purple",
                    "gold",
                    "royal",
                    "promise",
                ],
            ),
            gradient_preset(
                key="townlit-ruby-glory",
                title="Ruby Glory",
                colors=[
                    "#5D071EFF",
                    "#C40233FF",
                    "#D73F09FF",
                    "#F6C860FF",
                ],
                angle=135,
                description=(
                    "Ruby, Jasper and Glory in a dramatic warm gradient."
                ),
                sort_order=470,
                family="townlit_signature",
                tags=[
                    "brand",
                    "ruby",
                    "jasper",
                    "gold",
                    "dramatic",
                ],
            ),
        ]
    )

    # -----------------------------------------------------
    # 4. Revelation stone gradients
    # -----------------------------------------------------

    stone_gradient_order = 600

    for stone_key, stone in REVELATION_STONES.items():
        presets.append(
            gradient_preset(
                key=f"revelation-{stone_key}-radiance",
                title=f"{stone['title']} Radiance",
                colors=[
                    stone["dark"],
                    stone["color"],
                    stone["light"],
                ],
                angle=135,
                description=(
                    f"A layered {stone['title']} gradient "
                    "inspired by the foundations of the New Jerusalem."
                ),
                sort_order=stone_gradient_order,
                family="revelation_radiance",
                tags=[
                    "revelation-21",
                    "foundation-stone",
                    stone_key,
                    "biblical",
                    "radiance",
                    "gradient",
                ],
                is_featured=stone_key in {
                    "sapphire",
                    "emerald",
                    "topaz",
                    "jacinth",
                },
                metadata={
                    "biblical_reference": (
                        "Revelation 21:19-20"
                    ),
                    "stone_key": stone_key,
                    "color_interpretation": (
                        "TownLIT UI approximation"
                    ),
                },
            )
        )

        stone_gradient_order += 10

    # -----------------------------------------------------
    # 5. Curated stone combinations
    # -----------------------------------------------------

    presets.extend(
        [
            gradient_preset(
                key="foundations-first-light",
                title="First Foundation",
                colors=[
                    REVELATION_STONES["jasper"]["dark"],
                    REVELATION_STONES["jasper"]["color"],
                    REVELATION_STONES["sapphire"]["color"],
                ],
                angle=135,
                description=(
                    "Jasper and Sapphire in a bold foundation gradient."
                ),
                sort_order=800,
                family="revelation_combinations",
                tags=[
                    "revelation-21",
                    "jasper",
                    "sapphire",
                    "foundation",
                    "bold",
                ],
                is_featured=True,
                metadata={
                    "biblical_reference": (
                        "Revelation 21:19"
                    ),
                    "stones": [
                        "jasper",
                        "sapphire",
                    ],
                },
            ),
            gradient_preset(
                key="foundations-living-water",
                title="Living Water",
                colors=[
                    REVELATION_STONES["sapphire"]["dark"],
                    REVELATION_STONES["beryl"]["color"],
                    REVELATION_STONES["chalcedony"]["light"],
                ],
                angle=45,
                description=(
                    "Sapphire, Beryl and Chalcedony in a luminous water palette."
                ),
                sort_order=810,
                family="revelation_combinations",
                tags=[
                    "revelation-21",
                    "sapphire",
                    "beryl",
                    "chalcedony",
                    "water",
                    "peaceful",
                ],
                is_featured=True,
                metadata={
                    "biblical_reference": (
                        "Revelation 21:19-20"
                    ),
                    "stones": [
                        "sapphire",
                        "beryl",
                        "chalcedony",
                    ],
                },
            ),
            gradient_preset(
                key="foundations-garden",
                title="New Jerusalem Garden",
                colors=[
                    REVELATION_STONES["emerald"]["dark"],
                    REVELATION_STONES["chrysoprase"]["color"],
                    REVELATION_STONES["chrysolite"]["light"],
                ],
                angle=90,
                description=(
                    "Emerald, Chrysoprase and Chrysolite in a living green gradient."
                ),
                sort_order=820,
                family="revelation_combinations",
                tags=[
                    "revelation-21",
                    "emerald",
                    "chrysoprase",
                    "chrysolite",
                    "green",
                    "living",
                ],
                is_featured=True,
                metadata={
                    "biblical_reference": (
                        "Revelation 21:19-20"
                    ),
                    "stones": [
                        "emerald",
                        "chrysoprase",
                        "chrysolite",
                    ],
                },
            ),
            gradient_preset(
                key="foundations-burning-light",
                title="Burning Light",
                colors=[
                    REVELATION_STONES["carnelian"]["dark"],
                    REVELATION_STONES["jasper"]["color"],
                    REVELATION_STONES["topaz"]["light"],
                ],
                angle=135,
                description=(
                    "Carnelian, Jasper and Topaz in a warm radiant gradient."
                ),
                sort_order=830,
                family="revelation_combinations",
                tags=[
                    "revelation-21",
                    "carnelian",
                    "jasper",
                    "topaz",
                    "warm",
                    "radiant",
                ],
                metadata={
                    "biblical_reference": (
                        "Revelation 21:19-20"
                    ),
                    "stones": [
                        "carnelian",
                        "jasper",
                        "topaz",
                    ],
                },
            ),
            gradient_preset(
                key="foundations-royal-crown",
                title="Royal Crown",
                colors=[
                    REVELATION_STONES["amethyst"]["dark"],
                    REVELATION_STONES["jacinth"]["color"],
                    TOWNLIT_COLORS["glory"],
                ],
                angle=135,
                description=(
                    "Amethyst, Jacinth and Glory gold in a royal composition."
                ),
                sort_order=840,
                family="revelation_combinations",
                tags=[
                    "revelation-21",
                    "amethyst",
                    "jacinth",
                    "gold",
                    "royal",
                ],
                is_featured=True,
                metadata={
                    "biblical_reference": (
                        "Revelation 21:20"
                    ),
                    "stones": [
                        "amethyst",
                        "jacinth",
                    ],
                },
            ),
            gradient_preset(
                key="foundations-pearl-gate",
                title="Pearl Gate",
                colors=[
                    "#FFFFFFFF",
                    TOWNLIT_COLORS["secondary"],
                    REVELATION_STONES["chalcedony"]["light"],
                    TOWNLIT_COLORS["glory"],
                ],
                angle=135,
                description=(
                    "Pearl, Chalcedony light and Glory gold."
                ),
                sort_order=850,
                family="revelation_combinations",
                tags=[
                    "revelation-21",
                    "pearl",
                    "chalcedony",
                    "gold",
                    "light",
                ],
                is_featured=True,
                metadata={
                    "biblical_reference": (
                        "Revelation 21:21"
                    ),
                    "theme": "pearl_gates",
                },
            ),
            gradient_preset(
                key="foundations-city-light",
                title="City of Light",
                colors=[
                    "#FDFDFDFF",
                    "#F8F6F0FF",
                    "#F8D878FF",
                    "#F6C860FF",
                    "#0F52BAFF",
                ],
                angle=145,
                description=(
                    "Pearl light, Glory gold and Sapphire blue."
                ),
                sort_order=860,
                family="revelation_combinations",
                tags=[
                    "revelation-21",
                    "city",
                    "light",
                    "glory",
                    "sapphire",
                ],
                is_featured=True,
                metadata={
                    "biblical_reference": (
                        "Revelation 21:23"
                    ),
                    "theme": "city_light",
                },
            ),
        ]
    )

    # -----------------------------------------------------
    # 6. Modern editorial gradients
    # -----------------------------------------------------

    presets.extend(
        [
            gradient_preset(
                key="editorial-ocean-prayer",
                title="Ocean Prayer",
                colors=[
                    "#06172CFF",
                    "#0F52BAFF",
                    "#48D1CCFF",
                    "#B9F1EFFF",
                ],
                angle=45,
                description=(
                    "A serene blue and turquoise editorial gradient."
                ),
                sort_order=1000,
                family="editorial",
                tags=[
                    "ocean",
                    "prayer",
                    "blue",
                    "turquoise",
                    "calm",
                ],
                is_featured=True,
                supported_consumers=deepcopy(
                    STORYTELLING_CONSUMERS
                ),
            ),
            gradient_preset(
                key="editorial-sunrise-worship",
                title="Sunrise Worship",
                colors=[
                    "#4B1834FF",
                    "#C84A2AFF",
                    "#F4A429FF",
                    "#F8D878FF",
                ],
                angle=135,
                description=(
                    "A warm sunrise gradient for worship and celebration."
                ),
                sort_order=1010,
                family="editorial",
                tags=[
                    "sunrise",
                    "worship",
                    "warm",
                    "orange",
                    "gold",
                ],
                is_featured=True,
                supported_consumers=deepcopy(
                    STORYTELLING_CONSUMERS
                ),
            ),
            gradient_preset(
                key="editorial-quiet-faith",
                title="Quiet Faith",
                colors=[
                    "#2B2C30FF",
                    "#6F6F6FFF",
                    "#D2D0CDFF",
                    "#EEECE6FF",
                ],
                angle=90,
                description=(
                    "A quiet neutral gradient for reflective content."
                ),
                sort_order=1020,
                family="editorial",
                tags=[
                    "neutral",
                    "quiet",
                    "faith",
                    "minimal",
                    "reflective",
                ],
                supported_consumers=deepcopy(
                    STORYTELLING_CONSUMERS
                ),
            ),
            gradient_preset(
                key="editorial-hope-bloom",
                title="Hope Bloom",
                colors=[
                    "#1D6545FF",
                    "#3BAA75FF",
                    "#78D7A5FF",
                    "#F8F6F0FF",
                ],
                angle=45,
                description=(
                    "Emerald green opening into a soft pearl light."
                ),
                sort_order=1030,
                family="editorial",
                tags=[
                    "hope",
                    "green",
                    "pearl",
                    "fresh",
                    "uplifting",
                ],
                is_featured=True,
                supported_consumers=deepcopy(
                    STORYTELLING_CONSUMERS
                ),
            ),
            gradient_preset(
                key="editorial-testimony-fire",
                title="Testimony Fire",
                colors=[
                    "#3B0815FF",
                    "#C40233FF",
                    "#D73F09FF",
                    "#F6C860FF",
                ],
                angle=135,
                description=(
                    "A bold red, Jasper and Glory gradient."
                ),
                sort_order=1040,
                family="editorial",
                tags=[
                    "testimony",
                    "fire",
                    "red",
                    "jasper",
                    "glory",
                ],
                supported_consumers=[
                    "journey",
                    "testimony",
                ],
            ),
            gradient_preset(
                key="editorial-night-vision",
                title="Night Vision",
                colors=[
                    "#050505FF",
                    "#121212FF",
                    "#0F2F5FFF",
                    "#0F52BAFF",
                ],
                angle=45,
                description=(
                    "A cinematic dark-to-Sapphire gradient."
                ),
                sort_order=1050,
                family="editorial",
                tags=[
                    "night",
                    "cinematic",
                    "dark",
                    "sapphire",
                    "modern",
                ],
                supported_consumers=deepcopy(
                    STORYTELLING_CONSUMERS
                ),
            ),
            gradient_preset(
                key="editorial-sacred-purple",
                title="Sacred Purple",
                colors=[
                    "#261634FF",
                    "#44305FFF",
                    "#7A5CA2FF",
                    "#D18BFFFF",
                ],
                angle=135,
                description=(
                    "A deep Amethyst and Jacinth editorial gradient."
                ),
                sort_order=1060,
                family="editorial",
                tags=[
                    "purple",
                    "amethyst",
                    "jacinth",
                    "sacred",
                    "contemplative",
                ],
                supported_consumers=deepcopy(
                    STORYTELLING_CONSUMERS
                ),
            ),
            gradient_preset(
                key="editorial-desert-grace",
                title="Desert Grace",
                colors=[
                    "#6D432BFF",
                    "#B96A55FF",
                    "#F0E3C3FF",
                    "#F8F6F0FF",
                ],
                angle=135,
                description=(
                    "Sardonyx earth tones opening into Agate and Pearl."
                ),
                sort_order=1070,
                family="editorial",
                tags=[
                    "desert",
                    "grace",
                    "sardonyx",
                    "agate",
                    "earth",
                ],
                supported_consumers=deepcopy(
                    STORYTELLING_CONSUMERS
                ),
            ),
            gradient_preset(
                key="editorial-heavenly-aqua",
                title="Heavenly Aqua",
                colors=[
                    "#1F6F75FF",
                    "#48D1CCFF",
                    "#7FDBDAFF",
                    "#E8F6F8FF",
                ],
                angle=45,
                description=(
                    "Turquoise, Beryl and Chalcedony light."
                ),
                sort_order=1080,
                family="editorial",
                tags=[
                    "aqua",
                    "turquoise",
                    "beryl",
                    "chalcedony",
                    "light",
                ],
                is_featured=True,
                supported_consumers=deepcopy(
                    STORYTELLING_CONSUMERS
                ),
            ),
            gradient_preset(
                key="editorial-golden-hour",
                title="Golden Hour",
                colors=[
                    "#7C4D0DFF",
                    "#E2A93BFF",
                    "#F6C860FF",
                    "#FFE5B4FF",
                ],
                angle=135,
                description=(
                    "A warm golden-hour gradient for joyful moments."
                ),
                sort_order=1090,
                family="editorial",
                tags=[
                    "gold",
                    "warm",
                    "joy",
                    "golden-hour",
                    "celebration",
                ],
                is_featured=True,
                supported_consumers=deepcopy(
                    STORYTELLING_CONSUMERS
                ),
            ),
        ]
    )

    return presets


BACKGROUND_PRESETS = build_background_presets()


# =========================================================
# Command
# =========================================================

class Command(BaseCommand):
    help = (
        "Create or update the curated TownLIT creative "
        "background catalog."
    )

    @transaction.atomic
    def handle(
        self,
        *args,
        **options,
    ):
        created_count = 0
        updated_count = 0
        unchanged_count = 0

        seen_keys: set[str] = set()

        for payload in BACKGROUND_PRESETS:
            key = str(
                payload["key"]
            ).strip().lower()

            if not key:
                raise ValueError(
                    "Creative background key cannot be empty."
                )

            if key in seen_keys:
                raise ValueError(
                    (
                        "Duplicate creative background "
                        f"seed key: {key}"
                    )
                )

            seen_keys.add(key)

            existing = (
                CreativeBackgroundPreset
                .objects
                .filter(
                    key=key,
                )
                .first()
            )

            created = existing is None

            background = (
                CreativeBackgroundPreset(
                    key=key,
                )
                if created
                else existing
            )

            assert background is not None

            previous_state = (
                None
                if created
                else self._comparable_state(
                    background
                )
            )

            self._apply_payload(
                background=background,
                payload=payload,
            )

            
            # Validate before writing anything to the database.
            background.full_clean()

            current_state = self._comparable_state(
                background
            )

            if (
                not created
                and previous_state == current_state
            ):
                unchanged_count += 1
                continue

            background.save()

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Creative backgrounds synchronized. "
                    f"Total defaults: {len(BACKGROUND_PRESETS)}. "
                    f"Created: {created_count}. "
                    f"Updated: {updated_count}. "
                    f"Unchanged: {unchanged_count}."
                )
            )
        )

    @staticmethod
    def _apply_payload(
        *,
        background:
            CreativeBackgroundPreset,
        payload: dict[str, Any],
    ) -> None:
        background.key = str(
            payload["key"]
        ).strip().lower()

        background.title = str(
            payload["title"]
        ).strip()

        background.description = str(
            payload.get(
                "description",
                "",
            )
        ).strip()

        background.background_type = str(
            payload["background_type"]
        ).strip()

        background.color = str(
            payload.get(
                "color",
                "",
            )
        ).strip()

        background.colors = deepcopy(
            payload.get(
                "colors",
                [],
            )
        )

        background.angle = float(
            payload.get(
                "angle",
                90.0,
            )
        )

        background.supported_consumers = deepcopy(
            payload.get(
                "supported_consumers",
                [],
            )
        )

        background.metadata = deepcopy(
            payload.get(
                "metadata",
                {},
            )
        )

        background.is_featured = bool(
            payload.get(
                "is_featured",
                False,
            )
        )

        background.is_active = bool(
            payload.get(
                "is_active",
                True,
            )
        )

        background.sort_order = int(
            payload.get(
                "sort_order",
                0,
            )
        )

    @staticmethod
    def _comparable_state(
        background:
            CreativeBackgroundPreset,
    ) -> dict[str, Any]:
        return {
            "key": background.key,
            "title": background.title,
            "description": background.description,
            "background_type": (
                background.background_type
            ),
            "color": background.color,
            "colors": deepcopy(
                background.colors
            ),
            "angle": float(
                background.angle
            ),
            "supported_consumers": deepcopy(
                background.supported_consumers
            ),
            "metadata": deepcopy(
                background.metadata
            ),
            "is_featured": bool(
                background.is_featured
            ),
            "is_active": bool(
                background.is_active
            ),
            "sort_order": int(
                background.sort_order
            ),
        }
        
        
# docker compose exec backend python manage.py seed_creative_backgrounds