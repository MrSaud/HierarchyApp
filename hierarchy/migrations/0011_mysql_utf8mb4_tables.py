"""Convert hierarchy MySQL tables to utf8mb4 (fixes Arabic / Unicode DataError 1366)."""

from django.db import migrations


def _convert_hierarchy_tables_to_utf8mb4(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    with schema_editor.connection.cursor() as cursor:
        for model in apps.get_app_config("hierarchy").get_models():
            table = model._meta.db_table
            cursor.execute(
                "ALTER TABLE `%s` CONVERT TO CHARACTER SET utf8mb4 "
                "COLLATE utf8mb4_unicode_ci" % table
            )


class Migration(migrations.Migration):

    dependencies = [
        ("hierarchy", "0010_tenant_api_key"),
    ]

    operations = [
        migrations.RunPython(
            _convert_hierarchy_tables_to_utf8mb4,
            migrations.RunPython.noop,
        ),
    ]
