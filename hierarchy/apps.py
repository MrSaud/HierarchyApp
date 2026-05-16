from django.apps import AppConfig


class HierarchyConfig(AppConfig):
    name = 'hierarchy'

    def ready(self):
        import hierarchy.signals  # noqa: F401
        from hierarchy.audit_model_signals import connect_generic_orm_audit

        connect_generic_orm_audit()
