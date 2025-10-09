from django.core.management.base import BaseCommand
from apps.accounts.models import SocialMediaType
from apps.accounts.constants import SOCIAL_MEDIA_DATA


class Command(BaseCommand):
    help = "Seed the SocialMediaType table with predefined data"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("Starting to seed the SocialMediaType table..."))
        
        created_count = 0
        updated_count = 0

        for item in SOCIAL_MEDIA_DATA:
            try:
                social_media, created = SocialMediaType.objects.update_or_create(
                    name=item["name"],
                    defaults={
                        "icon_class": item["icon_class"],
                        "icon_svg": item["icon_svg"],
                        "is_active": True,
                    },
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"Error processing {item['name']}: {str(e)}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded SocialMediaType table: {created_count} created, {updated_count} updated."
            )
        )


# docker compose exec backend python manage.py seed_social_media