from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import CheckoutLog, InventoryItem, PracticeRoom, RoomReservation
from .serializers import (
    CheckoutLogSerializer,
    InventoryItemSerializer,
    PracticeRoomSerializer,
    RoomReservationSerializer,
)


class InventoryItemViewSet(viewsets.ModelViewSet):
    """ViewSet for inventory items"""

    queryset = InventoryItem.objects.all()
    serializer_class = InventoryItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter based on query params"""
        queryset = super().get_queryset()

        # Filter by category
        category = self.request.query_params.get("category")
        if category and category != "all":
            queryset = queryset.filter(category=category)

        # Filter by status
        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)

        # Search by name or location
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(location__icontains=search))

        return queryset

    def perform_create(self, serializer):
        """Set created_by to current user"""
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get inventory statistics"""
        items = self.get_queryset()

        total_items = items.count()
        total_value = sum(item.value * item.quantity for item in items)
        low_stock = items.filter(available_quantity__lte=2).count()
        needs_repair = items.filter(condition="needs-repair").count()

        return Response(
            {
                "total_items": total_items,
                "total_value": f"${total_value:,.2f}",
                "low_stock": low_stock,
                "needs_repair": needs_repair,
            }
        )


class CheckoutLogViewSet(viewsets.ModelViewSet):
    """ViewSet for checkout logs"""

    queryset = CheckoutLog.objects.select_related("item", "student", "approved_by")
    serializer_class = CheckoutLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter checkouts"""
        queryset = super().get_queryset()

        # Students can only see their own checkouts
        if self.request.user.role == "student":
            queryset = queryset.filter(student=self.request.user)

        # Filter by status
        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)

        # Filter by student
        student_id = self.request.query_params.get("student")
        if student_id:
            queryset = queryset.filter(student_id=student_id)

        return queryset

    def perform_create(self, serializer):
        """Create a new checkout request"""
        item = serializer.validated_data["item"]
        quantity = serializer.validated_data.get("quantity", 1)

        # Check if enough quantity available
        if item.available_quantity < quantity:
            raise serializers.ValidationError(
                {"quantity": f"Only {item.available_quantity} available"}
            )

        # Set due date if not provided
        if "due_date" not in serializer.validated_data:
            due_date = timezone.now().date() + timedelta(days=item.max_checkout_days)
            serializer.validated_data["due_date"] = due_date

        # Save the checkout
        serializer.save(student=self.request.user, status="pending")

        # Decrease available quantity
        item.available_quantity -= quantity
        item.save()

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Approve a checkout request (admin/teacher only)"""
        if request.user.role not in ["admin", "teacher"]:
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        checkout = self.get_object()
        checkout.status = "approved"
        checkout.approved_by = request.user
        checkout.approved_at = timezone.now()
        checkout.save()

        serializer = self.get_serializer(checkout)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def return_item(self, request, pk=None):
        """Mark item as returned"""
        checkout = self.get_object()

        if checkout.status != "approved":
            return Response(
                {"detail": "Only approved checkouts can be returned"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        checkout.status = "returned"
        checkout.return_date = timezone.now()
        checkout.notes = request.data.get("notes", checkout.notes)
        checkout.save()

        # Increase available quantity
        checkout.item.available_quantity += checkout.quantity
        checkout.item.save()

        serializer = self.get_serializer(checkout)
        return Response(serializer.data)


class PracticeRoomViewSet(viewsets.ModelViewSet):
    """ViewSet for practice rooms"""

    queryset = PracticeRoom.objects.filter(is_active=True)
    serializer_class = PracticeRoomSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["get"])
    def availability(self, request, pk=None):
        """Get room availability for a specific date"""
        room = self.get_object()
        date_str = request.query_params.get("date", timezone.now().date().isoformat())

        try:
            from datetime import datetime

            target_date = datetime.fromisoformat(date_str).date()
        except (ValueError, TypeError):
            return Response(
                {"detail": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get all reservations for this room on this date
        reservations = RoomReservation.objects.filter(
            room=room, start_time__date=target_date, status__in=["pending", "confirmed"]
        ).order_by("start_time")

        reserved_slots = [
            {
                "start": res.start_time.isoformat(),
                "end": res.end_time.isoformat(),
                "student": res.student.get_full_name(),
            }
            for res in reservations
        ]

        return Response({"room": room.name, "date": date_str, "reserved_slots": reserved_slots})


class RoomReservationViewSet(viewsets.ModelViewSet):
    """ViewSet for room reservations"""

    queryset = RoomReservation.objects.select_related("room", "student")
    serializer_class = RoomReservationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter reservations"""
        queryset = super().get_queryset()

        # Students can only see their own reservations
        if self.request.user.role == "student":
            queryset = queryset.filter(student=self.request.user)

        # Filter by date range
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")

        if start_date:
            queryset = queryset.filter(start_time__gte=start_date)
        if end_date:
            queryset = queryset.filter(end_time__lte=end_date)

        # Filter by room
        room_id = self.request.query_params.get("room")
        if room_id:
            queryset = queryset.filter(room_id=room_id)

        return queryset

    def perform_create(self, serializer):
        """Create a new reservation"""
        serializer.save(student=self.request.user)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel a reservation"""
        reservation = self.get_object()

        # Students can only cancel their own reservations
        if request.user.role == "student" and reservation.student != request.user:
            return Response(
                {"detail": "You can only cancel your own reservations"},
                status=status.HTTP_403_FORBIDDEN,
            )

        reservation.status = "cancelled"
        reservation.save()

        serializer = self.get_serializer(reservation)
        return Response(serializer.data)
