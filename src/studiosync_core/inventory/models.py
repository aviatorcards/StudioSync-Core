from decimal import Decimal

from django.conf import settings
from django.db import models


class InventoryItem(models.Model):
    """Items tracked in studio inventory"""

    CATEGORY_CHOICES = [
        ("instrument", "Instrument"),
        ("equipment", "Equipment"),
        ("sheet-music", "Sheet Music"),
        ("accessories", "Accessories"),
        ("other", "Other"),
    ]

    CONDITION_CHOICES = [
        ("excellent", "Excellent"),
        ("good", "Good"),
        ("fair", "Fair"),
        ("needs-repair", "Needs Repair"),
    ]

    STATUS_CHOICES = [
        ("available", "Available"),
        ("checked-out", "Checked Out"),
        ("maintenance", "In Maintenance"),
        ("retired", "Retired"),
    ]

    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    quantity = models.IntegerField(default=1)
    available_quantity = models.IntegerField(default=1, help_text="Quantity currently available")
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default="good")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="available")
    location = models.CharField(max_length=200)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    last_maintenance = models.DateField(null=True, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)

    # Borrowing settings
    is_borrowable = models.BooleanField(default=True, help_text="Can students check this out?")
    max_checkout_days = models.IntegerField(default=7, help_text="Maximum days for checkout")

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_items"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.category})"

    @property
    def is_low_stock(self):
        """Check if item is low on available quantity"""
        return self.available_quantity <= 2


class CheckoutLog(models.Model):
    """Track who has checked out inventory items"""

    STATUS_CHOICES = [
        ("pending", "Pending Approval"),
        ("approved", "Checked Out"),
        ("returned", "Returned"),
        ("overdue", "Overdue"),
        ("cancelled", "Cancelled"),
    ]

    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="checkouts")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="item_checkouts"
    )
    quantity = models.IntegerField(default=1)

    # Dates
    checkout_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField()
    return_date = models.DateTimeField(null=True, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    notes = models.TextField(blank=True, help_text="Special instructions or damage reports")

    # Approval
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_checkouts",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-checkout_date"]

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.item.name} ({self.status})"

    @property
    def is_overdue(self):
        """Check if checkout is overdue"""
        from django.utils import timezone

        if self.status == "approved" and self.due_date:
            return timezone.now().date() > self.due_date
        return False


class PracticeRoom(models.Model):
    """Practice rooms available for reservation"""

    name = models.CharField(max_length=100)
    capacity = models.IntegerField(default=1, help_text="Maximum number of people")
    description = models.TextField(blank=True)
    equipment = models.TextField(blank=True, help_text="Equipment available in this room")
    hourly_rate = models.DecimalField(
        max_digits=6, decimal_places=2, default=0, help_text="Cost per hour (0 for free)"
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class RoomReservation(models.Model):
    """Student reservations for practice rooms"""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
        ("no-show", "No Show"),
    ]

    room = models.ForeignKey(PracticeRoom, on_delete=models.CASCADE, related_name="reservations")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="room_reservations"
    )

    # Time
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    notes = models.TextField(blank=True)

    # Payment
    total_cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_paid = models.BooleanField(default=False)

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_time"]

    def __str__(self):
        return f"{self.room.name} - {self.student.get_full_name()} on {self.start_time.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        """Calculate total cost based on duration and room rate"""
        if self.start_time and self.end_time and self.room:
            duration_hours = (self.end_time - self.start_time).total_seconds() / 3600
            self.total_cost = Decimal(str(duration_hours)) * self.room.hourly_rate
        super().save(*args, **kwargs)

    def clean(self):
        """Validate reservation doesn't overlap with existing ones"""
        from django.core.exceptions import ValidationError
        from django.db.models import Q

        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                raise ValidationError("End time must be after start time")

            # Check for overlapping reservations
            overlapping = RoomReservation.objects.filter(
                room=self.room, status__in=["pending", "confirmed"]
            ).filter(Q(start_time__lt=self.end_time, end_time__gt=self.start_time))

            if self.pk:
                overlapping = overlapping.exclude(pk=self.pk)

            if overlapping.exists():
                raise ValidationError("This time slot overlaps with an existing reservation")
