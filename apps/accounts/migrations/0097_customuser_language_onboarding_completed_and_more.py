#
#  apps/accounts/migrations/0097_customuser_language_onboarding_completed_and_more.py
#  TownLIT
#
#  Created by Hossein Sakkaki on 2026-07-30.
#  Last Update by Hossein Sakkaki on 2026-07-31.
#

from django.db import migrations, models
from django.db.models import F, Q

import utils.common.utils
import validators.mediaValidators.image_validators
import validators.security_validators


def normalize_existing_user_languages(apps, schema_editor):
    CustomUser = apps.get_model("accounts", "CustomUser")

    # Normalize legacy blank values.
    CustomUser.objects.filter(primary_language="").update(
        primary_language=None,
    )
    CustomUser.objects.filter(secondary_language="").update(
        secondary_language=None,
    )

    # Promote secondary language when primary is missing.
    CustomUser.objects.filter(
        primary_language__isnull=True,
        secondary_language__isnull=False,
    ).update(
        primary_language=F("secondary_language"),
        secondary_language=None,
    )

    # Remove duplicate secondary language.
    CustomUser.objects.filter(
        primary_language__isnull=False,
        secondary_language__isnull=False,
        primary_language=F("secondary_language"),
    ).update(
        secondary_language=None,
    )

    # Give legacy users a safe primary language.
    CustomUser.objects.filter(
        primary_language__isnull=True,
        secondary_language__isnull=True,
    ).update(
        primary_language="en",
    )

    # Existing users should not enter the new onboarding flow.
    CustomUser.objects.all().update(
        language_onboarding_completed=True,
    )


def reverse_normalize_existing_user_languages(apps, schema_editor):
    # Normalized legacy values cannot be restored safely.
    pass


class Migration(migrations.Migration):

    dependencies = [
        (
            "accounts",
            "0096_alter_customlabel_name_alter_customuser_image_name",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="language_onboarding_completed",
            field=models.BooleanField(
                default=False,
                verbose_name="Language Onboarding Completed",
            ),
        ),

        migrations.RunPython(
            normalize_existing_user_languages,
            reverse_normalize_existing_user_languages,
        ),

        migrations.AlterField(
            model_name="customuser",
            name="image_name",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=utils.common.utils.FileUpload.dir_upload,
                validators=[
                    validators.mediaValidators.image_validators.validate_image_file,
                    validators.mediaValidators.image_validators.validate_image_size,
                    validators.security_validators.validate_no_executable_file,
                ],
                verbose_name="Image",
            ),
        ),

        migrations.AddConstraint(
            model_name="customuser",
            constraint=models.CheckConstraint(
                check=(
                    Q(primary_language__isnull=True)
                    | Q(secondary_language__isnull=True)
                    | ~Q(primary_language=F("secondary_language"))
                ),
                name="accounts_user_distinct_profile_languages",
            ),
        ),
    ]