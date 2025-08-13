# apps/conversation/migrations/00xx_fix_add_created_at_on_message_encryption.py
from django.db import migrations

def add_created_at(apps, schema_editor):
    connection = schema_editor.connection
    ME = apps.get_model("conversation", "MessageEncryption")
    table = ME._meta.db_table

    # لیست ستون‌های فعلی جدول
    with connection.cursor() as cursor:
        cols = [c.name for c in connection.introspection.get_table_description(cursor, table)]

    if "created_at" not in cols:
        vendor = connection.vendor

        # اضافه کردن ستون (idempotent با بررسی بالا)
        with connection.cursor() as cursor:
            if vendor == "mysql":
                cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN `created_at` datetime(6) NULL")
                cursor.execute(f"UPDATE `{table}` SET `created_at` = NOW(6) WHERE `created_at` IS NULL")
            elif vendor == "postgresql":
                cursor.execute(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "created_at" timestamp with time zone NULL')
                cursor.execute(f'UPDATE "{table}" SET "created_at" = NOW() WHERE "created_at" IS NULL')
            else:  # sqlite و سایر
                cursor.execute(f'ALTER TABLE "{table}" ADD COLUMN "created_at" datetime NULL')
                cursor.execute(f'UPDATE "{table}" SET "created_at" = CURRENT_TIMESTAMP WHERE "created_at" IS NULL')

class Migration(migrations.Migration):
    dependencies = [
        ("conversation", "0016_alter_dialogue_group_image_alter_message_audio_and_more"),
    ]
    operations = [
        migrations.RunPython(add_created_at, migrations.RunPython.noop),
    ]
