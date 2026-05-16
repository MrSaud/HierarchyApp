"""
Convert HierarchyDB tables to utf8mb4 (Arabic and other Unicode text).

Usage:
    python manage.py convert_mysql_utf8mb4
    python manage.py convert_mysql_utf8mb4 --auth-only
"""

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection


def _auth_table_names() -> list[str]:
    return [
        m._meta.db_table
        for m in apps.get_app_config("auth").get_models()
        if m._meta.db_table
    ]


def _hierarchy_table_names() -> list[str]:
    return [m._meta.db_table for m in apps.get_app_config("hierarchy").get_models()]


class Command(BaseCommand):
    help = "Convert MySQL tables to utf8mb4 (fixes Incorrect string value for Unicode)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--auth-only",
            action="store_true",
            help="Convert only auth_* tables (e.g. auth_user for Arabic names).",
        )
        parser.add_argument(
            "--hierarchy-only",
            action="store_true",
            help="Convert only hierarchy_* tables (skip auth).",
        )

    def handle(self, *args, **options):
        if connection.vendor != "mysql":
            self.stdout.write("Skipped: default database is not MySQL.")
            return

        if options["auth_only"] and options["hierarchy_only"]:
            self.stderr.write("Use only one of --auth-only or --hierarchy-only.")
            return

        tables: list[str] = []
        if options["auth_only"]:
            tables = _auth_table_names()
        elif options["hierarchy_only"]:
            tables = _hierarchy_table_names()
        else:
            tables = _hierarchy_table_names() + _auth_table_names()

        db_name = settings.DATABASES["default"].get("NAME", "")
        self.stdout.write(f"Database: {db_name}")

        with connection.cursor() as cursor:
            for table in tables:
                self.stdout.write(f"Converting {table} …")
                cursor.execute(
                    "ALTER TABLE `%s` CONVERT TO CHARACTER SET utf8mb4 "
                    "COLLATE utf8mb4_unicode_ci" % table
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Done. Unicode text (Arabic names on User/Employee) should save correctly now."
            )
        )
