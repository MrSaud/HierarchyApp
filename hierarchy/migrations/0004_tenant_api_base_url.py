from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hierarchy", "0003_tenant_and_membership"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="api_base_url",
            field=models.URLField(
                blank=True,
                help_text="This tenant's backend base (e.g. http://63.183.213.237:1113). Health checks use {base}/api/health.",
                max_length=500,
                verbose_name="API base URL",
            ),
        ),
    ]
