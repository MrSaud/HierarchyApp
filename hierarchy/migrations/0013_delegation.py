# Generated manually for Delegation model

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hierarchy", "0012_mysql_utf8mb4_auth_tables"),
    ]

    operations = [
        migrations.CreateModel(
            name="Delegation",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("start_date", models.DateField()),
                ("end_date", models.DateField(blank=True, help_text="Leave empty for an open-ended delegation.", null=True)),
                ("notes", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "delegatee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="delegations_received",
                        to="hierarchy.employee",
                    ),
                ),
                (
                    "delegator",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="delegations_given",
                        to="hierarchy.employee",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="delegations",
                        to="hierarchy.tenant",
                    ),
                ),
            ],
            options={
                "verbose_name": "delegation",
                "ordering": ["-start_date", "pk"],
            },
        ),
    ]
