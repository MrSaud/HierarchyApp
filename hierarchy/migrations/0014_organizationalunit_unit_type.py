# Generated manually

from django.db import migrations, models


def _infer_unit_type(code: str, name: str) -> str:
    code = (code or "").upper()
    if code == "MIN" or code.startswith("MIN-"):
        return "minister"
    if code == "US" or (code.startswith("US-") and "-" not in code[3:]):
        return "deputy_dg"
    if code.startswith("REG"):
        return "regional_directorate"
    if code in ("SOC", "FAM", "DIS", "PLN", "INT") or (
        len(code) == 3 and code.isalpha() and not code.startswith("US")
    ):
        return "sector"
    if "-ADM" in code or "-HR" in code or "-IT" in code or "-LEG" in code:
        if code.count("-") == 1:
            return "general_admin"
    if "CTL" in code or "CTRL" in code:
        return "controller"
    if "SEC" in code.split("-")[-1] if code else False:
        return "section"
    if code.count("-") >= 2:
        return "department"
    if "إدارة عامة" in name or "الإدارة العامة" in name:
        return "general_admin"
    if "قطاع" in name:
        return "sector"
    if "مديرية" in name:
        return "regional_directorate"
    if "قسم" in name:
        return "section"
    if "وكيل" in name:
        return "deputy_dg"
    if "وزير" in name:
        return "minister"
    if "إدارة" in name:
        return "department"
    return "department"


def forwards_set_unit_types(apps, schema_editor):
    OrganizationalUnit = apps.get_model("hierarchy", "OrganizationalUnit")
    for unit in OrganizationalUnit.objects.all().iterator():
        unit.unit_type = _infer_unit_type(unit.code, unit.name)
        unit.save(update_fields=["unit_type"])


class Migration(migrations.Migration):

    dependencies = [
        ("hierarchy", "0013_delegation"),
    ]

    operations = [
        migrations.AddField(
            model_name="organizationalunit",
            name="unit_type",
            field=models.CharField(
                choices=[
                    ("minister", "Minister (DG)"),
                    ("deputy_dg", "Deputy DG"),
                    ("sector", "Sector (Program)"),
                    ("general_admin", "General administration"),
                    ("department", "Department"),
                    ("controller", "Controller"),
                    ("section", "Section"),
                    ("regional_directorate", "Regional directorate"),
                ],
                db_index=True,
                default="department",
                max_length=32,
            ),
        ),
        migrations.RunPython(forwards_set_unit_types, migrations.RunPython.noop),
    ]
