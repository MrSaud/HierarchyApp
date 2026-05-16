from django.db import migrations, models
import django.db.models.deletion

DEFAULT_ROWS = [
    ("minister", "Minister (DG)", 0, True, 0),
    ("deputy_dg", "Deputy DG", 10, True, 10),
    ("sector", "Sector (Program)", 20, False, 20),
    ("regional_directorate", "Regional directorate", 20, False, 25),
    ("general_admin", "General administration", 30, False, 30),
    ("department", "Department", 40, False, 40),
    ("controller", "Controller", 45, False, 45),
    ("section", "Section", 50, False, 50),
]


def seed_org_unit_types(apps, schema_editor):
    Tenant = apps.get_model("hierarchy", "Tenant")
    OrgUnitTypeDefinition = apps.get_model("hierarchy", "OrgUnitTypeDefinition")
    for tenant in Tenant.objects.all().iterator():
        for slug, label, rank, allows_root, sort_order in DEFAULT_ROWS:
            OrgUnitTypeDefinition.objects.get_or_create(
                tenant_id=tenant.pk,
                slug=slug,
                defaults={
                    "label": label,
                    "rank": rank,
                    "allows_root": allows_root,
                    "sort_order": sort_order,
                },
            )


class Migration(migrations.Migration):

    dependencies = [
        ("hierarchy", "0015_alter_positionassignment_is_primary"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrgUnitTypeDefinition",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "slug",
                    models.SlugField(
                        help_text="Stable code stored on units (e.g. department). Letters, numbers, underscores.",
                        max_length=64,
                    ),
                ),
                ("label", models.CharField(max_length=120)),
                (
                    "rank",
                    models.PositiveSmallIntegerField(
                        default=50,
                        help_text="Lower = higher in hierarchy. Parent must have a lower rank than child.",
                    ),
                ),
                (
                    "allows_root",
                    models.BooleanField(
                        default=False,
                        help_text="May exist without a parent unit (top-level).",
                    ),
                ),
                ("sort_order", models.PositiveIntegerField(default=0)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="org_unit_type_definitions",
                        to="hierarchy.tenant",
                    ),
                ),
            ],
            options={
                "verbose_name": "organizational unit type",
                "ordering": ["sort_order", "rank", "label"],
            },
        ),
        migrations.AddConstraint(
            model_name="orgunittypedefinition",
            constraint=models.UniqueConstraint(
                fields=("tenant", "slug"),
                name="hierarchy_orgunittype_tenant_slug_uniq",
            ),
        ),
        migrations.RunPython(seed_org_unit_types, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="organizationalunit",
            name="unit_type",
            field=models.CharField(
                db_index=True,
                default="department",
                help_text="Slug of an organizational unit type defined for this tenant.",
                max_length=64,
            ),
        ),
    ]
