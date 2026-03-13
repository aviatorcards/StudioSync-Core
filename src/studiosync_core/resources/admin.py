"""
Django Admin configuration for Resources models
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import Resource, ResourceCheckout, Setlist, SetlistResource


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    """Django Admin interface for Resource model"""

    list_display = [
        "title",
        "resource_type",
        "uploaded_by",
        "is_public",
        "is_lendable",
        "availability_status",
        "created_at",
    ]
    list_filter = ["resource_type", "is_public", "is_lendable", "is_physical_item", "created_at"]
    search_fields = [
        "title",
        "description",
        "category",
        "uploaded_by__first_name",
        "uploaded_by__last_name",
    ]
    readonly_fields = ["id", "created_at", "updated_at"]
    filter_horizontal = ["shared_with_students"]
    fieldsets = (
        (
            "Basic Information",
            {"fields": ("studio", "uploaded_by", "title", "description", "resource_type")},
        ),
        (
            "File Information",
            {
                "fields": ("file", "file_size", "mime_type", "external_url"),
                "classes": ("collapse",),
            },
        ),
        ("Organization", {"fields": ("category", "tags")}),
        (
            "Physical Item Tracking",
            {
                "fields": (
                    "is_physical_item",
                    "quantity_total",
                    "quantity_available",
                    "is_lendable",
                    "checkout_duration_days",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Visibility & Sharing", {"fields": ("is_public", "shared_with_students")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
        ("Metadata", {"fields": ("id",), "classes": ("collapse",)}),
    )

    def availability_status(self, obj):
        """Display availability status for physical items"""
        if not obj.is_physical_item:
            return "Digital"

        if obj.quantity_available == 0:
            return format_html(
                '<span style="color: #C4704F; font-weight: bold;">Out of Stock</span>'
            )
        elif obj.quantity_available < obj.quantity_total:
            return format_html(
                '<span style="color: #E8A845; font-weight: bold;">{}/{} Available</span>',
                obj.quantity_available,
                obj.quantity_total,
            )
        else:
            return format_html(
                '<span style="color: #556B2F; font-weight: bold;">In Stock ({}/{})</span>',
                obj.quantity_available,
                obj.quantity_total,
            )

    availability_status.short_description = "Availability"


@admin.register(ResourceCheckout)
class ResourceCheckoutAdmin(admin.ModelAdmin):
    """Django Admin interface for ResourceCheckout model"""

    list_display = [
        "resource",
        "student",
        "checked_out_at",
        "due_date",
        "status_badge",
        "returned_at",
    ]
    list_filter = ["status", "checked_out_at", "due_date", "returned_at"]
    search_fields = [
        "resource__title",
        "student__user__first_name",
        "student__user__last_name",
        "notes",
    ]
    readonly_fields = ["id", "created_at"]
    fieldsets = (
        ("Checkout Information", {"fields": ("resource", "student", "checked_out_by")}),
        ("Dates", {"fields": ("checked_out_at", "due_date", "returned_at", "status")}),
        ("Notes", {"fields": ("notes",), "classes": ("collapse",)}),
        ("Metadata", {"fields": ("id", "created_at"), "classes": ("collapse",)}),
    )

    def status_badge(self, obj):
        """Display status as a colored badge"""
        colors = {
            "checked_out": "#E8A845",  # Warm Amber
            "returned": "#556B2F",  # Olive Dark
            "overdue": "#C4704F",  # Earth Primary (Terracotta)
            "lost": "#C4704F",  # Earth Primary (Terracotta)
        }
        color = colors.get(obj.status, "#5A6B4F")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"


class SetlistResourceInline(admin.TabularInline):
    model = SetlistResource
    extra = 1
    autocomplete_fields = ["resource"]


@admin.register(Setlist)
class SetlistAdmin(admin.ModelAdmin):
    list_display = ["name", "studio", "created_by", "created_at"]
    search_fields = ["name", "description", "studio__name"]
    inlines = [SetlistResourceInline]
