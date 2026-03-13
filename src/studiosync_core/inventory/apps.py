from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "studiosync_core.inventory"
    verbose_name = "Inventory Management"
