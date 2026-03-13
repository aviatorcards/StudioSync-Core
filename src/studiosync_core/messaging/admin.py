"""
Django Admin configuration for Messaging models
"""

from django.contrib import admin

from .models import Message, MessageThread


@admin.register(MessageThread)
class MessageThreadAdmin(admin.ModelAdmin):
    """Django Admin interface for MessageThread model"""

    list_display = [
        "subject",
        "studio",
        "get_participant_count",
        "created_at",
        "updated_at",
    ]
    list_filter = ["created_at", "updated_at", "studio"]
    search_fields = [
        "subject",
        "participants__first_name",
        "participants__last_name",
        "participants__email",
    ]
    readonly_fields = ["id", "created_at", "updated_at"]
    filter_horizontal = ["participants"]
    fieldsets = (
        ("Thread Information", {"fields": ("studio", "subject")}),
        ("Participants", {"fields": ("participants",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
        ("Metadata", {"fields": ("id",), "classes": ("collapse",)}),
    )

    def get_participant_count(self, obj):
        """Get the number of participants in the thread"""
        return obj.participants.count()

    get_participant_count.short_description = "Participants"


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Django Admin interface for Message model"""

    list_display = [
        "__str__",
        "thread",
        "sender",
        "get_read_count",
        "created_at",
    ]
    list_filter = ["created_at", "updated_at"]
    search_fields = [
        "body",
        "sender__first_name",
        "sender__last_name",
        "sender__email",
        "thread__subject",
    ]
    readonly_fields = ["id", "created_at", "updated_at"]
    filter_horizontal = ["read_by"]
    fieldsets = (
        ("Message Information", {"fields": ("thread", "sender", "body")}),
        ("Attachments", {"fields": ("attachments",), "classes": ("collapse",)}),
        ("Read Tracking", {"fields": ("read_by",), "classes": ("collapse",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
        ("Metadata", {"fields": ("id",), "classes": ("collapse",)}),
    )

    def get_read_count(self, obj):
        """Get the number of users who have read this message"""
        return obj.read_by.count()

    get_read_count.short_description = "Read By"
