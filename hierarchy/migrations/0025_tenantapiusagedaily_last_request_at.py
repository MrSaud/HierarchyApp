from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "hierarchy",
            "0024_rename_hierarchy_t_tenant__a1b2c3_idx_hierarchy_t_tenant__9b8d71_idx_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="tenantapiusagedaily",
            name="last_request_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Timestamp of the most recent call counted on this day.",
                null=True,
            ),
        ),
    ]
