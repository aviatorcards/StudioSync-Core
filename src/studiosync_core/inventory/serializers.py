from rest_framework import serializers

from .models import CheckoutLog, InventoryItem, PracticeRoom, RoomReservation


class InventoryItemSerializer(serializers.ModelSerializer):
    """Serializer for inventory items"""

    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = InventoryItem
        fields = [
            "id",
            "name",
            "category",
            "quantity",
            "available_quantity",
            "condition",
            "status",
            "location",
            "value",
            "notes",
            "last_maintenance",
            "purchase_date",
            "serial_number",
            "is_borrowable",
            "max_checkout_days",
            "is_low_stock",
            "created_at",
            "updated_at",
            "created_by",
            "created_by_name",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "created_by"]


class CheckoutLogSerializer(serializers.ModelSerializer):
    """Serializer for checkout logs"""

    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    item_name = serializers.CharField(source="item.name", read_only=True)
    approved_by_name = serializers.CharField(
        source="approved_by.get_full_name", read_only=True, allow_null=True
    )
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = CheckoutLog
        fields = [
            "id",
            "item",
            "item_name",
            "student",
            "student_name",
            "quantity",
            "checkout_date",
            "due_date",
            "return_date",
            "status",
            "notes",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "is_overdue",
        ]
        read_only_fields = ["id", "checkout_date", "approved_by", "approved_at"]


class PracticeRoomSerializer(serializers.ModelSerializer):
    """Serializer for practice rooms"""

    class Meta:
        model = PracticeRoom
        fields = ["id", "name", "capacity", "description", "equipment", "hourly_rate", "is_active"]


class RoomReservationSerializer(serializers.ModelSerializer):
    """Serializer for room reservations"""

    room_name = serializers.CharField(source="room.name", read_only=True)
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    duration_hours = serializers.SerializerMethodField()

    class Meta:
        model = RoomReservation
        fields = [
            "id",
            "room",
            "room_name",
            "student",
            "student_name",
            "start_time",
            "end_time",
            "duration_hours",
            "status",
            "notes",
            "total_cost",
            "is_paid",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "total_cost", "created_at", "updated_at"]

    def get_duration_hours(self, obj):
        """Calculate duration in hours"""
        if obj.start_time and obj.end_time:
            duration = (obj.end_time - obj.start_time).total_seconds() / 3600
            return round(duration, 2)
        return 0

    def validate(self, data):
        """Validate reservation times"""
        if data.get("start_time") and data.get("end_time"):
            if data["start_time"] >= data["end_time"]:
                raise serializers.ValidationError("End time must be after start time")
        return data
