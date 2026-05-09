"""Project package — selects MySQL driver before Django connects.

Homebrew ``mysqlclient`` often links to MySQL 9.x without ``mysql_native_password.so``.
If the server still uses ``mysql_native_password``, connections fail with OperationalError 2059.
**Default:** PyMySQL (pure Python, no plugin .so). Override with ``DJANGO_USE_MYSQLCLIENT=1``.
"""

import os


def _setup_mysql_driver() -> None:
    use_mysqlclient = os.environ.get(
        "DJANGO_USE_MYSQLCLIENT",
        "",
    ).lower() in ("1", "true", "yes")

    if use_mysqlclient:
        try:
            import MySQLdb  # noqa: F401
            return
        except ImportError:
            pass
        try:
            import pymysql

            pymysql.install_as_MySQLdb()
        except ImportError:
            pass
        return

    try:
        import pymysql

        pymysql.install_as_MySQLdb()
        return
    except ImportError:
        pass

    try:
        import MySQLdb  # noqa: F401
    except ImportError:
        pass


_setup_mysql_driver()


def _patch_django_basecontext_copy_for_python_314() -> None:
    """Django 4.2 LTS ``BaseContext.__copy__`` uses ``copy(super())``, which breaks on Python 3.14+.

    Upstream ``django.template.context`` replaces this with an explicit ``BaseContext()`` copy.
    """
    import sys

    if sys.version_info < (3, 14):
        return

    from copy import copy as copy_fn

    from django.template import context as ctx

    def basecontext_copy(self):
        duplicate = ctx.BaseContext()
        duplicate.__class__ = self.__class__
        duplicate.__dict__ = copy_fn(self.__dict__)
        duplicate.dicts = self.dicts[:]
        return duplicate

    ctx.BaseContext.__copy__ = basecontext_copy


_patch_django_basecontext_copy_for_python_314()
