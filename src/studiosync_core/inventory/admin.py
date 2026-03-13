from django.contrib import admin

from .models import CheckoutLog, InventoryItem, PracticeRoom, RoomReservation


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "category",
        "quantity",
        "available_quantity",
        "condition",
        "status",
        "value",
        "location",
    ]
    list_filter = ["category", "condition", "status", "is_borrowable"]
    search_fields = ["name", "location", "serial_number"]
    readonly_fields = ["created_at", "updated_at", "created_by"]


@admin.register(CheckoutLog)
class CheckoutLogAdmin(admin.ModelAdmin):
    list_display = [
        "item",
        "student",
        "quantity",
        "checkout_date",
        "due_date",
        "status",
        "is_overdue",
    ]
    list_filter = ["status", "checkout_date", "due_date"]
    search_fields = ["item__name", "student__first_name", "student__last_name"]
    readonly_fields = ["checkout_date", "is_overdue"]

    def get_readonly_fields(self, request, obj=None):
        """Make certain fields readonly after creation"""
        if obj:  # Editing an existing object
            return self.readonly_fields + ["item", "student", "checkout_date"]
        return self.readonly_fields


@admin.register(PracticeRoom)
class PracticeRoomAdmin(admin.ModelAdmin):
    list_display = ["name", "capacity", "hourly_rate", "is_active"]
    list_filter = ["is_active", "capacity"]
    search_fields = ["name", "description"]


@admin.register(RoomReservation)
class RoomReservationAdmin(admin.ModelAdmin):
    list_display = ["room", "student", "start_time", "end_time", "status", "total_cost", "is_paid"]
    list_filter = ["status", "is_paid", "start_time"]
    search_fields = ["room__name", "student__first_name", "student__last_name"]
    readonly_fields = ["total_cost", "created_at", "updated_at"]
