# apps/audio_catalog/management/commands/seed_audio_catalog.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.db import transaction

from apps.audio_catalog.models import (
    AudioCatalog,
    AudioCategory,
    AudioContributor,
    AudioGenre,
    AudioMood,
    AudioTag,
    RightsParty,
)


# -------------------------------------------------
# Catalogs
# -------------------------------------------------
CATALOGS = (
    {
        "slug": "townlit-originals",
        "name": "TownLIT Originals",
        "description": (
            "Original music owned, commissioned, directed, "
            "or produced by TownLIT for use across TownLIT."
        ),
        "visibility": AudioCatalog.Visibility.AUTHENTICATED,
        "is_active": True,
        "sort_order": 10,
    },
    {
        "slug": "townlit-ai-originals",
        "name": "TownLIT AI Originals",
        "description": (
            "Music created with AI-assisted production workflows "
            "under TownLIT direction and documented provider terms."
        ),
        "visibility": AudioCatalog.Visibility.AUTHENTICATED,
        "is_active": True,
        "sort_order": 20,
    },
    {
        "slug": "licensed-music",
        "name": "Licensed Music",
        "description": (
            "Music licensed from third-party creators, providers, "
            "labels, publishers, or music libraries."
        ),
        "visibility": AudioCatalog.Visibility.AUTHENTICATED,
        "is_active": True,
        "sort_order": 30,
    },
    {
        "slug": "public-domain-and-open-license",
        "name": "Public Domain and Open License",
        "description": (
            "Music verified as public domain or distributed under "
            "a compatible open license."
        ),
        "visibility": AudioCatalog.Visibility.AUTHENTICATED,
        "is_active": True,
        "sort_order": 40,
    },
    {
        "slug": "internal-testing",
        "name": "Internal Testing",
        "description": (
            "Private music assets used only for development, "
            "quality assurance, conversion, and playback testing."
        ),
        "visibility": AudioCatalog.Visibility.PRIVATE,
        "is_active": True,
        "sort_order": 900,
    },
)


# -------------------------------------------------
# Categories
# -------------------------------------------------
CATEGORIES = (
    {
        "slug": "worship-and-faith",
        "name": "Worship and Faith",
        "description": (
            "Music for worship, prayer, testimony, scripture, "
            "devotion, and faith-centered content."
        ),
        "icon": "hands.sparkles",
        "sort_order": 10,
    },
    {
        "slug": "inspirational",
        "name": "Inspirational",
        "description": (
            "Uplifting and encouraging music for hopeful, "
            "motivational, and meaningful content."
        ),
        "icon": "sparkles",
        "sort_order": 20,
    },
    {
        "slug": "cinematic",
        "name": "Cinematic",
        "description": (
            "Narrative, dramatic, atmospheric, and trailer-style "
            "music for visual storytelling."
        ),
        "icon": "film",
        "sort_order": 30,
    },
    {
        "slug": "ambient-and-background",
        "name": "Ambient and Background",
        "description": (
            "Subtle background music designed to support content "
            "without overwhelming speech or visuals."
        ),
        "icon": "waveform",
        "sort_order": 40,
    },
    {
        "slug": "acoustic-and-organic",
        "name": "Acoustic and Organic",
        "description": (
            "Natural and human-centered music featuring acoustic "
            "and organic instrumentation."
        ),
        "icon": "guitars",
        "sort_order": 50,
    },
    {
        "slug": "electronic-and-modern",
        "name": "Electronic and Modern",
        "description": (
            "Contemporary electronic, digital, synth-based, and "
            "modern production styles."
        ),
        "icon": "waveform.path.ecg",
        "sort_order": 60,
    },
    {
        "slug": "celebration-and-events",
        "name": "Celebration and Events",
        "description": (
            "Music for celebrations, milestones, gatherings, "
            "announcements, and community events."
        ),
        "icon": "party.popper",
        "sort_order": 70,
    },
    {
        "slug": "reflection-and-wellness",
        "name": "Reflection and Wellness",
        "description": (
            "Calm music for reflection, rest, wellness, peaceful "
            "moments, and contemplative content."
        ),
        "icon": "leaf",
        "sort_order": 80,
    },
    {
        "slug": "family-and-lifestyle",
        "name": "Family and Lifestyle",
        "description": (
            "Friendly and approachable music for family, everyday "
            "life, relationships, and lifestyle content."
        ),
        "icon": "house",
        "sort_order": 90,
    },
    {
        "slug": "youth-and-energetic",
        "name": "Youth and Energetic",
        "description": (
            "Bright, active, youthful, and energetic music for "
            "dynamic social content."
        ),
        "icon": "bolt",
        "sort_order": 100,
    },
    {
        "slug": "documentary-and-educational",
        "name": "Documentary and Educational",
        "description": (
            "Music for teaching, documentary, informational, "
            "historical, and educational content."
        ),
        "icon": "book",
        "sort_order": 110,
    },
    {
        "slug": "seasonal-and-holiday",
        "name": "Seasonal and Holiday",
        "description": (
            "Music connected to seasons, holidays, annual events, "
            "and special occasions."
        ),
        "icon": "calendar",
        "sort_order": 120,
    },
)


# -------------------------------------------------
# Genres
# -------------------------------------------------
GENRES = (
    ("ambient", "Ambient", "Atmospheric and spacious soundscapes."),
    ("acoustic", "Acoustic", "Music led by natural acoustic instruments."),
    ("alternative", "Alternative", "Non-mainstream contemporary music styles."),
    ("blues", "Blues", "Blues-inspired harmony, rhythm, and expression."),
    ("choral", "Choral", "Music centered on choir or vocal ensemble textures."),
    ("christian-contemporary", "Christian Contemporary", "Modern Christian and faith-centered music."),
    ("cinematic", "Cinematic", "Music designed for narrative and visual impact."),
    ("classical", "Classical", "Music influenced by classical composition traditions."),
    ("country", "Country", "Country-inspired acoustic and vocal music."),
    ("electronic", "Electronic", "Music produced primarily with electronic instruments."),
    ("folk", "Folk", "Traditional and contemporary folk-inspired music."),
    ("funk", "Funk", "Rhythm-focused music with strong grooves."),
    ("gospel", "Gospel", "Gospel-inspired spiritual and vocal music."),
    ("hip-hop", "Hip-Hop", "Beat-driven hip-hop and rap-influenced production."),
    ("indie", "Indie", "Independent contemporary music aesthetics."),
    ("jazz", "Jazz", "Jazz harmony, improvisation, and instrumentation."),
    ("lo-fi", "Lo-Fi", "Relaxed music with intentionally soft or textured production."),
    ("meditation", "Meditation", "Slow and minimal music for calm and reflection."),
    ("neo-classical", "Neo-Classical", "Modern music influenced by classical forms and instruments."),
    ("orchestral", "Orchestral", "Music featuring orchestral instrumentation and arrangement."),
    ("pop", "Pop", "Accessible and contemporary popular music."),
    ("r-and-b", "R&B", "Rhythm and blues-inspired contemporary music."),
    ("reggae", "Reggae", "Reggae-inspired rhythm and production."),
    ("rock", "Rock", "Guitar and rhythm-driven rock music."),
    ("singer-songwriter", "Singer-Songwriter", "Personal song-focused acoustic or contemporary music."),
    ("soul", "Soul", "Expressive vocal and instrumental soul music."),
    ("soundtrack", "Soundtrack", "Music created to accompany narrative content."),
    ("synthwave", "Synthwave", "Retro-inspired electronic and synthesizer music."),
    ("world", "World", "Music influenced by diverse global traditions."),
    ("worship", "Worship", "Music intended for worship and devotional settings."),
)


# -------------------------------------------------
# Moods
# -------------------------------------------------
MOODS = (
    ("peaceful", "Peaceful", "Calm, gentle, and settled."),
    ("hopeful", "Hopeful", "Positive and expectant."),
    ("uplifting", "Uplifting", "Encouraging and emotionally elevating."),
    ("joyful", "Joyful", "Happy, celebratory, and bright."),
    ("reflective", "Reflective", "Thoughtful and contemplative."),
    ("reverent", "Reverent", "Respectful, sacred, and worshipful."),
    ("prayerful", "Prayerful", "Quiet, devotional, and spiritually focused."),
    ("inspirational", "Inspirational", "Motivational and meaningful."),
    ("emotional", "Emotional", "Expressive and deeply felt."),
    ("tender", "Tender", "Soft, warm, and caring."),
    ("warm", "Warm", "Comforting and welcoming."),
    ("gentle", "Gentle", "Light, delicate, and non-intrusive."),
    ("dreamy", "Dreamy", "Soft, floating, and imaginative."),
    ("atmospheric", "Atmospheric", "Spacious and environment-focused."),
    ("dramatic", "Dramatic", "Intense and narratively expressive."),
    ("epic", "Epic", "Large-scale, powerful, and triumphant."),
    ("triumphant", "Triumphant", "Victorious and confident."),
    ("energetic", "Energetic", "Active, driving, and lively."),
    ("playful", "Playful", "Lighthearted and fun."),
    ("romantic", "Romantic", "Affectionate and emotionally intimate."),
    ("melancholic", "Melancholic", "Sad, reflective, or bittersweet."),
    ("mysterious", "Mysterious", "Uncertain, curious, and suspenseful."),
    ("serious", "Serious", "Focused, grounded, and weighty."),
    ("neutral", "Neutral", "Balanced background music with limited emotional direction."),
)


# -------------------------------------------------
# Tags
# -------------------------------------------------
TAGS = (
    ("worship", "Worship", "Worship-focused content."),
    ("prayer", "Prayer", "Prayer and devotional content."),
    ("scripture", "Scripture", "Scripture reading or Bible-centered content."),
    ("testimony", "Testimony", "Personal testimony and transformation stories."),
    ("faith", "Faith", "Faith-centered themes."),
    ("grace", "Grace", "Themes of grace and mercy."),
    ("hope", "Hope", "Hopeful themes and messages."),
    ("love", "Love", "Love, care, and compassion."),
    ("peace", "Peace", "Peaceful themes and environments."),
    ("healing", "Healing", "Healing and restoration."),
    ("restoration", "Restoration", "Renewal and restoration."),
    ("gratitude", "Gratitude", "Thanksgiving and appreciation."),
    ("reflection", "Reflection", "Thoughtful and reflective content."),
    ("devotional", "Devotional", "Personal devotion and spiritual practice."),
    ("church", "Church", "Church and congregational contexts."),
    ("community", "Community", "Community and fellowship."),
    ("fellowship", "Fellowship", "Relationships and Christian fellowship."),
    ("ministry", "Ministry", "Ministry and service."),
    ("mission", "Mission", "Mission and outreach."),
    ("encouragement", "Encouragement", "Encouraging and supportive content."),
    ("motivation", "Motivation", "Motivational content."),
    ("inspirational", "Inspirational", "Inspirational messages and visuals."),
    ("celebration", "Celebration", "Celebrations and milestones."),
    ("wedding", "Wedding", "Wedding and marriage content."),
    ("family", "Family", "Family-centered content."),
    ("friendship", "Friendship", "Friendship and relationships."),
    ("children", "Children", "Children and family-friendly content."),
    ("youth", "Youth", "Youth-focused content."),
    ("education", "Education", "Educational and teaching content."),
    ("documentary", "Documentary", "Documentary and factual storytelling."),
    ("storytelling", "Storytelling", "Narrative and story-driven content."),
    ("background", "Background", "General background music."),
    ("voiceover-friendly", "Voiceover Friendly", "Suitable beneath spoken narration."),
    ("instrumental", "Instrumental", "Music without primary vocals."),
    ("vocal", "Vocal", "Music containing vocals."),
    ("choir", "Choir", "Choir or ensemble vocals."),
    ("piano", "Piano", "Piano-led music."),
    ("acoustic-guitar", "Acoustic Guitar", "Acoustic guitar-led music."),
    ("electric-guitar", "Electric Guitar", "Electric guitar-led music."),
    ("strings", "Strings", "String-focused arrangement."),
    ("orchestra", "Orchestra", "Orchestral instrumentation."),
    ("synth", "Synth", "Synthesizer-driven production."),
    ("percussion", "Percussion", "Percussion-focused production."),
    ("soft", "Soft", "Soft and restrained."),
    ("calm", "Calm", "Calm and relaxing."),
    ("slow", "Slow", "Slow tempo or pacing."),
    ("mid-tempo", "Mid-Tempo", "Moderate tempo."),
    ("upbeat", "Upbeat", "Bright and active."),
    ("energetic", "Energetic", "High energy."),
    ("dramatic", "Dramatic", "Dramatic and emotionally intense."),
    ("cinematic", "Cinematic", "Cinematic production."),
    ("epic", "Epic", "Large and powerful."),
    ("minimal", "Minimal", "Minimal arrangement."),
    ("modern", "Modern", "Contemporary production."),
    ("organic", "Organic", "Natural and organic texture."),
    ("ambient", "Ambient", "Ambient and atmospheric."),
    ("meditative", "Meditative", "Meditative and contemplative."),
    ("christmas", "Christmas", "Christmas and Advent content."),
    ("easter", "Easter", "Easter and resurrection content."),
    ("seasonal", "Seasonal", "Seasonal and holiday content."),
    ("ai-assisted", "AI Assisted", "Created with an AI-assisted workflow."),
    ("townlit-original", "TownLIT Original", "Original TownLIT-controlled production."),
    ("licensed", "Licensed", "Third-party licensed music."),
    ("public-domain", "Public Domain", "Verified public-domain material."),
)


# -------------------------------------------------
# Contributors
# -------------------------------------------------
CONTRIBUTORS = (
    {
        "external_reference": "townlit-brand",
        "display_name": "TownLIT",
        "legal_name": "TownLIT Society",
        "kind": AudioContributor.Kind.ORGANIZATION,
        "website_url": "https://townlit.com",
        "metadata": {
            "seed_managed": True,
            "organization_role": "brand",
            "public_name": "TownLIT",
            "legal_name": "TownLIT Society",
            "country_code": "CA",
        },
        "is_active": True,
    },
    {
        "external_reference": "townlit-originals",
        "display_name": "TownLIT Originals",
        "legal_name": "TownLIT Society",
        "kind": AudioContributor.Kind.ORGANIZATION,
        "website_url": "https://townlit.com",
        "metadata": {
            "seed_managed": True,
            "organization_role": "music_imprint",
            "controlled_by": "TownLIT Society",
            "default_credit": "TownLIT Original",
        },
        "is_active": True,
    },
    {
        "external_reference": "townlit-ai-production",
        "display_name": "TownLIT AI Production",
        "legal_name": "TownLIT Society",
        "kind": AudioContributor.Kind.ORGANIZATION,
        "website_url": "https://townlit.com",
        "metadata": {
            "seed_managed": True,
            "organization_role": "ai_assisted_production",
            "controlled_by": "TownLIT Society",
            "requires_provider_credit": True,
            "requires_generation_record": True,
            "requires_provider_terms_snapshot": True,
            "requires_prompt_hash_when_available": True,
            "default_credit": "A TownLIT AI-assisted production",
        },
        "is_active": True,
    },
)


# -------------------------------------------------
# Rights parties
# -------------------------------------------------
RIGHTS_PARTIES = (
    {
        "external_reference": "townlit-society",
        "display_name": "TownLIT",
        "legal_name": "TownLIT Society",
        "kind": RightsParty.Kind.ORGANIZATION,
        "country_code": "CA",
        "website_url": "https://townlit.com",
        "contact_email": "",
        "metadata": {
            "seed_managed": True,
            "public_name": "TownLIT",
            "legal_entity": "TownLIT Society",
            "jurisdiction": "Canada",
            "role": "rights_owner_and_licensee",
        },
    },
    {
        "external_reference": "townlit-originals-rights",
        "display_name": "TownLIT Originals",
        "legal_name": "TownLIT Society",
        "kind": RightsParty.Kind.ORGANIZATION,
        "country_code": "CA",
        "website_url": "https://townlit.com",
        "contact_email": "",
        "metadata": {
            "seed_managed": True,
            "public_name": "TownLIT Originals",
            "legal_entity": "TownLIT Society",
            "role": "music_imprint",
            "controlled_by": "TownLIT Society",
        },
    },
)


@dataclass
class SeedStats:
    """
    Track command changes.
    """

    created: dict[str, int] = field(default_factory=dict)
    updated: dict[str, int] = field(default_factory=dict)
    preserved: dict[str, int] = field(default_factory=dict)

    def add(
        self,
        bucket: str,
        model_name: str,
    ) -> None:
        target = getattr(
            self,
            bucket,
        )

        target[model_name] = (
            target.get(
                model_name,
                0,
            )
            + 1
        )


class Command(BaseCommand):
    """
    Seed the base TownLIT audio catalog configuration.
    """

    help = (
        "Create or synchronize TownLIT audio catalogs, "
        "taxonomies, contributors, and rights parties."
    )

    def add_arguments(
        self,
        parser,
    ):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Show the changes and roll back the transaction."
            ),
        )

        parser.add_argument(
            "--update",
            action="store_true",
            help=(
                "Update existing seed-managed records to the "
                "current command definitions."
            ),
        )

    def handle(
        self,
        *args,
        **options,
    ):
        dry_run = bool(
            options["dry_run"]
        )

        update_existing = bool(
            options["update"]
        )

        stats = SeedStats()

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "Seeding TownLIT audio catalog..."
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "Dry-run mode enabled. "
                    "No database changes will be committed."
                )
            )

        if update_existing:
            self.stdout.write(
                self.style.WARNING(
                    "Update mode enabled. Existing seeded values "
                    "may be synchronized."
                )
            )

        try:
            with transaction.atomic():
                self._seed_catalogs(
                    stats=stats,
                    update_existing=update_existing,
                )

                self._seed_taxonomy(
                    model=AudioCategory,
                    records=CATEGORIES,
                    model_name="Audio categories",
                    stats=stats,
                    update_existing=update_existing,
                )

                self._seed_taxonomy(
                    model=AudioGenre,
                    records=self._taxonomy_records(
                        GENRES
                    ),
                    model_name="Audio genres",
                    stats=stats,
                    update_existing=update_existing,
                )

                self._seed_taxonomy(
                    model=AudioMood,
                    records=self._taxonomy_records(
                        MOODS
                    ),
                    model_name="Audio moods",
                    stats=stats,
                    update_existing=update_existing,
                )

                self._seed_taxonomy(
                    model=AudioTag,
                    records=self._taxonomy_records(
                        TAGS
                    ),
                    model_name="Audio tags",
                    stats=stats,
                    update_existing=update_existing,
                )

                self._seed_contributors(
                    stats=stats,
                    update_existing=update_existing,
                )

                self._seed_rights_parties(
                    stats=stats,
                    update_existing=update_existing,
                )

                if dry_run:
                    transaction.set_rollback(
                        True
                    )

        except Exception as exc:
            raise CommandError(
                f"Audio catalog seed failed: {exc}"
            ) from exc

        self._print_summary(
            stats=stats,
            dry_run=dry_run,
        )

    @staticmethod
    def _taxonomy_records(
        source,
    ) -> tuple[dict[str, Any], ...]:
        """
        Convert compact taxonomy tuples to seed records.
        """

        return tuple(
            {
                "slug": slug,
                "name": name,
                "description": description,
                "sort_order": (
                    index
                    * 10
                ),
            }
            for index, (
                slug,
                name,
                description,
            ) in enumerate(
                source,
                start=1,
            )
        )

    def _seed_catalogs(
        self,
        *,
        stats: SeedStats,
        update_existing: bool,
    ) -> None:
        for record in CATALOGS:
            lookup = {
                "slug": record["slug"],
            }

            defaults = {
                key: value
                for key, value in record.items()
                if key != "slug"
            }

            self._create_or_update(
                model=AudioCatalog,
                lookup=lookup,
                defaults=defaults,
                model_name="Audio catalogs",
                stats=stats,
                update_existing=update_existing,
            )

    def _seed_taxonomy(
        self,
        *,
        model,
        records,
        model_name: str,
        stats: SeedStats,
        update_existing: bool,
    ) -> None:
        for record in records:
            lookup = {
                "slug": record["slug"],
            }

            defaults = {
                "name": record["name"],
                "description": record.get(
                    "description",
                    "",
                ),
                "sort_order": record.get(
                    "sort_order",
                    0,
                ),
                "is_active": True,
            }

            if model is AudioCategory:
                defaults["icon"] = record.get(
                    "icon",
                    "",
                )

            self._create_or_update(
                model=model,
                lookup=lookup,
                defaults=defaults,
                model_name=model_name,
                stats=stats,
                update_existing=update_existing,
            )

    def _seed_contributors(
        self,
        *,
        stats: SeedStats,
        update_existing: bool,
    ) -> None:
        for record in CONTRIBUTORS:
            self._create_or_update_external_entity(
                model=AudioContributor,
                record=record,
                model_name="Audio contributors",
                stats=stats,
                update_existing=update_existing,
            )

    def _seed_rights_parties(
        self,
        *,
        stats: SeedStats,
        update_existing: bool,
    ) -> None:
        for record in RIGHTS_PARTIES:
            self._create_or_update_external_entity(
                model=RightsParty,
                record=record,
                model_name="Rights parties",
                stats=stats,
                update_existing=update_existing,
            )

    def _create_or_update_external_entity(
        self,
        *,
        model,
        record: dict[str, Any],
        model_name: str,
        stats: SeedStats,
        update_existing: bool,
    ) -> None:
        """
        Resolve entities by stable external reference.

        A display-name fallback prevents duplicates when the
        entity was created manually before this command existed.
        """

        external_reference = record[
            "external_reference"
        ]

        instance = (
            model.objects
            .filter(
                external_reference=external_reference,
            )
            .first()
        )

        if instance is None:
            instance = (
                model.objects
                .filter(
                    display_name=record[
                        "display_name"
                    ],
                    legal_name=record.get(
                        "legal_name",
                        "",
                    ),
                )
                .first()
            )

        defaults = dict(
            record
        )

        if instance is None:
            model.objects.create(
                **defaults
            )

            stats.add(
                "created",
                model_name,
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Created {model_name}: "
                    f"{record['display_name']}"
                )
            )

            return

        changed_fields: list[str] = []

        # Always attach the stable reference when it is missing.
        if (
            not instance.external_reference
            and external_reference
        ):
            instance.external_reference = (
                external_reference
            )

            changed_fields.append(
                "external_reference"
            )

        if update_existing:
            for field_name, value in defaults.items():
                if field_name == "external_reference":
                    continue

                if (
                    getattr(
                        instance,
                        field_name,
                    )
                    != value
                ):
                    setattr(
                        instance,
                        field_name,
                        value,
                    )

                    changed_fields.append(
                        field_name
                    )

        if changed_fields:
            update_fields = list(
                dict.fromkeys(
                    changed_fields
                )
            )

            if hasattr(
                instance,
                "updated_at",
            ):
                update_fields.append(
                    "updated_at"
                )

            instance.save(
                update_fields=update_fields
            )

            stats.add(
                "updated",
                model_name,
            )

            self.stdout.write(
                self.style.WARNING(
                    f"Updated {model_name}: "
                    f"{record['display_name']}"
                )
            )

            return

        stats.add(
            "preserved",
            model_name,
        )

    def _create_or_update(
        self,
        *,
        model,
        lookup: dict[str, Any],
        defaults: dict[str, Any],
        model_name: str,
        stats: SeedStats,
        update_existing: bool,
    ) -> None:
        instance = (
            model.objects
            .filter(
                **lookup
            )
            .first()
        )

        label = (
            defaults.get(
                "name"
            )
            or defaults.get(
                "display_name"
            )
            or str(
                lookup
            )
        )

        if instance is None:
            model.objects.create(
                **lookup,
                **defaults,
            )

            stats.add(
                "created",
                model_name,
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Created {model_name}: {label}"
                )
            )

            return

        if not update_existing:
            stats.add(
                "preserved",
                model_name,
            )

            return

        changed_fields: list[str] = []

        for field_name, value in defaults.items():
            if (
                getattr(
                    instance,
                    field_name,
                )
                != value
            ):
                setattr(
                    instance,
                    field_name,
                    value,
                )

                changed_fields.append(
                    field_name
                )

        if not changed_fields:
            stats.add(
                "preserved",
                model_name,
            )

            return

        if hasattr(
            instance,
            "updated_at",
        ):
            changed_fields.append(
                "updated_at"
            )

        instance.save(
            update_fields=changed_fields
        )

        stats.add(
            "updated",
            model_name,
        )

        self.stdout.write(
            self.style.WARNING(
                f"Updated {model_name}: {label}"
            )
        )

    def _print_summary(
        self,
        *,
        stats: SeedStats,
        dry_run: bool,
    ) -> None:
        self.stdout.write("")

        heading = (
            "Dry-run summary"
            if dry_run
            else "Audio catalog seed completed"
        )

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                heading
            )
        )

        all_names = sorted(
            set(
                stats.created
            )
            | set(
                stats.updated
            )
            | set(
                stats.preserved
            )
        )

        if not all_names:
            self.stdout.write(
                self.style.WARNING(
                    "No seed records were processed."
                )
            )

            return

        for model_name in all_names:
            created = stats.created.get(
                model_name,
                0,
            )

            updated = stats.updated.get(
                model_name,
                0,
            )

            preserved = stats.preserved.get(
                model_name,
                0,
            )

            self.stdout.write(
                (
                    f"{model_name}: "
                    f"created={created}, "
                    f"updated={updated}, "
                    f"preserved={preserved}"
                )
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "All dry-run database changes were rolled back."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "TownLIT audio catalog base data is ready."
                )
            )
            
            
# sudo docker compose exec backend python manage.py seed_audio_catalog --dry-run
  
# sudo docker compose exec backend python manage.py seed_audio_catalog
  
# sudo docker compose exec backend python manage.py seed_audio_catalog --update