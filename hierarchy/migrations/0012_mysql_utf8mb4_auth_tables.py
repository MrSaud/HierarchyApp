"""Convert Django auth MySQL tables to utf8mb4 (Arabic names on User, etc.)."""

from django.db import migrations


def _convert_auth_tables_to_utf8mb4(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    with schema_editor.connection.cursor() as cursor:
        for model in apps.get_app_config("auth").get_models():
            table = model._meta.db_table
            if table:
                cursor.execute(
                    "ALTER TABLE `%s` CONVERT TO CHARACTER SET utf8mb4 "
                    "COLLATE utf8mb4_unicode_ci" % table
                )


class Migration(migrations.Migration):

    dependencies = [
        ("hierarchy", "0011_mysql_utf8mb4_tables"),
    ]

    operations = [
        migrations.RunPython(
            _convert_auth_tables_to_utf8mb4,
            migrations.RunPython.noop,
        ),
    ]
