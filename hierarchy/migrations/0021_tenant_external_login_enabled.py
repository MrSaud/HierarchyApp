from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hierarchy", "0020_tenant_external_sync_credentials"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="external_login_enabled",
            field=models.BooleanField(
                default=True,
                help_text="When on, POST /api/auth/login/ verifies credentials against the external AD API. "
                "When off, login uses local Django passwords only (sync and health still use the external API above).",
                verbose_name="AD login enabled",
            ),
        ),
    ]
