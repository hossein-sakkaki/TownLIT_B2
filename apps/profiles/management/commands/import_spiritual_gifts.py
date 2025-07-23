from django.core.management.base import BaseCommand
from apps.profiles.models import SpiritualGift
from apps.profiles.gift_constants import GIFT_CHOICES, GIFT_DESCRIPTIONS
from django.utils.translation import gettext as _


class Command(BaseCommand):
    help = 'Import spiritual gifts into the database'

    def handle(self, *args, **kwargs):
        for gift_value, gift_name in GIFT_CHOICES:
            description = GIFT_DESCRIPTIONS.get(gift_value, _('No description available'))
            SpiritualGift.objects.get_or_create(name=gift_value, description=description)
        self.stdout.write(self.style.SUCCESS('Successfully imported spiritual gifts with descriptions'))
        
# docker compose exec backend python manage.py import_spiritual_gifts