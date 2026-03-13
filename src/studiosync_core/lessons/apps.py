from django.apps import AppConfig


class LessonsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "studiosync_core.lessons"

    def ready(self):
        import studiosync_core.lessons.signals
