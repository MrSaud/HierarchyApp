from django.apps import AppConfig


class HierarchyConfig(AppConfig):
    name = 'hierarchy'

    def ready(self):
        import hierarchy.signals  # noqa: F401
