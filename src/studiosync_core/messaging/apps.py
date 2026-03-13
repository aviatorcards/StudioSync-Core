from django.apps import AppConfig


class MessagingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "studiosync_core.messaging"

    def ready(self):
        pass
