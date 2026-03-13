"""
Django Admin configuration for Lessons models
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import Lesson, LessonNote, RecurringPattern, StudentGoal


class LessonNoteInline(admin.StackedInline):
    """Inline admin for lesson notes"""

    model = LessonNote
    extra = 0
    fields = ["content", "practice_assignments", "teacher"]
    readonly_fields = ["teacher"]


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    """Django Admin interface for Lesson model"""

    list_display = [
        "get_student_name",
        "teacher",
        "lesson_type",
        "status_badge",
        "scheduled_start",
        "scheduled_end",
        "room",
    ]
    list_filter = ["status", "lesson_type", "scheduled_start", "studio"]
    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "band__name",
        "teacher__user__first_name",
        "teacher__user__last_name",
    ]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [LessonNoteInline]
    date_hierarchy = "scheduled_start"
    fieldsets = (
        ("Basic Information", {"fields": ("studio", "teacher", "student", "band", "room")}),
        ("Lesson Details", {"fields": ("lesson_type", "status")}),
        (
            "Scheduling",
            {
                "fields": (
                    "scheduled_start",
                    "scheduled_end",
                    "actual_start",
                    "actual_end",
                )
            },
        ),
        ("Recurring", {"fields": ("recurring_pattern",), "classes": ("collapse",)}),
        ("Metadata", {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_student_name(self, obj):
        """Get the student or band name"""
        if obj.student:
            return obj.student.user.get_full_name() or obj.student.user.email
        elif obj.band:
            return f"{obj.band.name} (Band)"
        return "Unknown"

    get_student_name.short_description = "Student/Band"

    def status_badge(self, obj):
        """Display status as a colored badge"""
        colors = {
            "scheduled": "#6B8E23",  # Olive Primary
            "in_progress": "#E8A845",  # Warm Amber
            "completed": "#556B2F",  # Olive Dark
            "cancelled": "#5A6B4F",  # Neutral Dark
            "no_show": "#C4704F",  # Earth Primary (Terracotta)
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"


@admin.register(RecurringPattern)
class RecurringPatternAdmin(admin.ModelAdmin):
    """Django Admin interface for RecurringPattern model"""

    list_display = [
        "__str__",
        "student",
        "teacher",
        "frequency",
        "day_of_week",
        "time",
        "is_active",
        "start_date",
        "end_date",
    ]
    list_filter = ["frequency", "day_of_week", "is_active", "start_date"]
    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "teacher__user__first_name",
        "teacher__user__last_name",
    ]
    readonly_fields = ["id", "created_at", "updated_at"]
    fieldsets = (
        ("Students & Teacher", {"fields": ("teacher", "student")}),
        ("Schedule Pattern", {"fields": ("frequency", "day_of_week", "time", "duration_minutes")}),
        ("Date Range", {"fields": ("start_date", "end_date", "is_active")}),
        ("Metadata", {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(StudentGoal)
class StudentGoalAdmin(admin.ModelAdmin):
    """Django Admin interface for StudentGoal model"""

    list_display = [
        "title",
        "student",
        "target_date",
        "status",
        "created_at",
    ]
    list_filter = ["status", "target_date", "created_at"]
    search_fields = [
        "title",
        "description",
        "student__user__first_name",
        "student__user__last_name",
    ]
    readonly_fields = ["id", "created_at", "updated_at"]
    fieldsets = (
        ("Goal Information", {"fields": ("student", "teacher", "title", "description")}),
        ("Progress", {"fields": ("status", "progress_percentage")}),
        ("Timeline", {"fields": ("target_date", "achieved_date")}),
        ("Metadata", {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)}),
    )
