from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Band, Student, Studio, Teacher, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "get_full_name", "role", "is_active", "created_at")
    list_filter = ("role", "is_active", "email_verified", "is_staff")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("-created_at",)

    # Fields to show when viewing/editing a user
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Personal info",
            {"fields": ("first_name", "last_name", "phone", "role", "timezone", "avatar")},
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "email_verified",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )

    # Fields to show when creating a new user
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "first_name",
                    "last_name",
                    "role",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )

    readonly_fields = ("created_at", "updated_at", "last_login")
    filter_horizontal = ("groups", "user_permissions")


@admin.register(Studio)
class StudioAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "email", "is_active", "created_at")
    list_filter = ("is_active", "country")
    search_fields = ("name", "email", "subdomain")
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ("user", "studio", "hourly_rate", "is_active", "created_at")
    list_filter = ("is_active", "studio")
    search_fields = ("user__first_name", "user__last_name", "user__email")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Band)
class BandAdmin(admin.ModelAdmin):
    list_display = ("__str__", "primary_contact", "billing_email", "studio", "created_at")
    list_filter = ("studio",)
    search_fields = (
        "name",
        "billing_email",
        "primary_contact__first_name",
        "primary_contact__last_name",
    )
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("user", "instrument", "primary_teacher", "is_active", "enrollment_date")
    list_filter = ("is_active", "instrument", "studio")
    search_fields = ("user__first_name", "user__last_name", "user__email", "instrument")
    ordering = ("-enrollment_date",)
    readonly_fields = ("created_at", "updated_at", "total_lessons")
