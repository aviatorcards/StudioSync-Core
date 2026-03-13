from django.apps import AppConfig


class AuthConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "studiosync_core.auth"
    label = "custom_auth"  # Avoid conflict with django.contrib.auth
