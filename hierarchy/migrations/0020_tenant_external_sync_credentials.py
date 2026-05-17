from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hierarchy", "0019_demote_duplicate_primary_assignments"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="external_sync_username",
            field=models.CharField(
                blank=True,
                help_text="Service account for Sync users (GET /api/auth/users with JSON body).",
                max_length=255,
                verbose_name="AD sync username",
            ),
        ),
        migrations.AddField(
            model_name="tenant",
            name="external_sync_password",
            field=models.CharField(
                blank=True,
                help_text="Password for the AD sync account (stored on tenant).",
                max_length=255,
                verbose_name="AD sync password",
            ),
        ),
    ]
