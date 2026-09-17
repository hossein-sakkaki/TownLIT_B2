# apps/profiles/migrations/0080_remove_legacy_organization_relations.py

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        (
            'profiles',
            '0079_alter_guestuser_register_date_and_more',
        ),
    ]

    operations = []