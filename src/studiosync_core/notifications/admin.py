from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["user", "title", "notification_type", "read", "created_at"]
    list_filter = ["notification_type", "read", "created_at"]
    search_fields = ["user__email", "title", "message"]
    readonly_fields = ["created_at", "read_at"]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Notification Info",
            {"fields": ("user", "notification_type", "title", "message", "link")},
        ),
        ("Status", {"fields": ("read", "read_at", "created_at")}),
        (
            "Related Objects",
            {
                "fields": (
                    "related_lesson_id",
                    "related_student_id",
                    "related_message_id",
                    "related_document_id",
                ),
                "classes": ("collapse",),
            },
        ),
    )
