from django.apps import AppConfig


class SellersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sellers"
    
    def ready(self):
        """Register signals when the app is ready."""
        import sellers.signals  # noqa
