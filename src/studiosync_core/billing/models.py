"""
Billing models - Invoice, Payment, InvoiceLineItem
"""

import uuid
from decimal import Decimal

from django.db import models
from django.utils import timezone

from studiosync_core.core.models import Band, Studio, User


class Invoice(models.Model):
    """
    Invoice for a band/group
    """

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("paid", "Paid"),
        ("partial", "Partially Paid"),
        ("overdue", "Overdue"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    studio = models.ForeignKey(Studio, on_delete=models.CASCADE, related_name="invoices")

    # Bill To (can be Band or Student)
    band = models.ForeignKey(
        Band, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices"
    )
    student = models.ForeignKey(
        "core.Student", on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices"
    )

    # Attribution
    teacher = models.ForeignKey(
        "core.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices_generated",
    )

    # Invoice details
    invoice_number = models.CharField(max_length=50, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    # Amounts
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    # Dates
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)

    # Notes
    notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)  # Not visible to client

    # Late fees
    late_fee_applied = models.BooleanField(default=False)
    late_fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    stripe_session_id = models.CharField(max_length=200, blank=True, db_index=True)

    class Meta:
        db_table = "invoices"
        ordering = ["-issue_date", "-invoice_number"]
        indexes = [
            models.Index(fields=["invoice_number"]),
            models.Index(fields=["band", "status"]),
            models.Index(fields=["due_date"]),
        ]

    def __str__(self):
        subject = (
            self.band.name
            if self.band
            else (self.student.user.get_full_name() if self.student else "Unknown")
        )
        return f"Invoice {self.invoice_number} - {subject} - {self.total_amount}"

    @property
    def balance_due(self):
        """Calculate remaining balance"""
        return self.total_amount - self.amount_paid

    @property
    def is_overdue(self):
        """Check if invoice is overdue"""
        if self.status == "paid":
            return False
        return timezone.now().date() > self.due_date

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            # Generate simple invoice number
            self.invoice_number = (
                f"INV-{timezone.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"
            )
        super().save(*args, **kwargs)

    def calculate_totals(self):
        """Recalculate invoice totals from line items"""
        line_items = self.line_items.all()
        self.subtotal = sum(item.total_price for item in line_items)
        self.total_amount = (
            self.subtotal + self.tax_amount - self.discount_amount + self.late_fee_amount
        )
        self.save()


class InvoiceLineItem(models.Model):
    """
    Individual line item on an invoice
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="line_items")

    # Item details
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    # Optional lesson reference
    lesson = models.ForeignKey(
        "lessons.Lesson",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice_line_items",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "invoice_line_items"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.description} - {self.total_price}"

    def save(self, *args, **kwargs):
        """Auto-calculate total price"""
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class Payment(models.Model):
    """
    Payment record for invoices
    """

    PAYMENT_METHOD_CHOICES = [
        ("cash", "Cash"),
        ("check", "Check"),
        ("credit_card", "Credit Card"),
        ("debit_card", "Debit Card"),
        ("bank_transfer", "Bank Transfer"),
        ("paypal", "PayPal"),
        ("stripe", "Stripe"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")

    # Payment details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="completed")

    # External reference (e.g., Stripe transaction ID)
    transaction_id = models.CharField(max_length=200, blank=True, db_index=True)

    # Metadata
    notes = models.TextField(blank=True)
    processed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="processed_payments"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(default=timezone.now)
    refunded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payments"
        ordering = ["-processed_at"]
        indexes = [
            models.Index(fields=["transaction_id"]),
            models.Index(fields=["invoice", "status"]),
        ]

    def __str__(self):
        return f"Payment {self.amount} for {self.invoice.invoice_number}"


class PaymentMethod(models.Model):
    """
    Saved payment methods for bands
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    band = models.ForeignKey(Band, on_delete=models.CASCADE, related_name="payment_methods")

    # Payment provider details
    provider = models.CharField(max_length=50)  # e.g., 'stripe', 'paypal'
    provider_payment_method_id = models.CharField(max_length=200)

    # Display information
    card_last_four = models.CharField(max_length=4, blank=True)
    card_brand = models.CharField(max_length=50, blank=True)
    expiry_month = models.IntegerField(null=True, blank=True)
    expiry_year = models.IntegerField(null=True, blank=True)

    # Flags
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payment_methods"
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        if self.card_last_four:
            return f"{self.card_brand} ending in {self.card_last_four}"
        return f"{self.provider} payment method"


class SubscriptionPlan(models.Model):
    """
    Recurring billing plans (e.g., Weekly Lesson, Monthly Access)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    studio = models.ForeignKey(Studio, on_delete=models.CASCADE, related_name="subscription_plans")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    interval = models.CharField(
        max_length=20,
        choices=[("day", "Daily"), ("week", "Weekly"), ("month", "Monthly"), ("year", "Yearly")],
        default="month",
    )
    
    # Provider IDs (optional if created in Stripe directly vs local first)
    stripe_product_id = models.CharField(max_length=200, blank=True)
    stripe_price_id = models.CharField(max_length=200, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscription_plans"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - ${self.price}/{self.interval}"


class Subscription(models.Model):
    """
    A student's enrollment in a subscription plan
    """

    STATUS_CHOICES = [
        ("active", "Active"),
        ("past_due", "Past Due"),
        ("canceled", "Canceled"),
        ("unpaid", "Unpaid"),
        ("trialing", "Trialing"),
        ("incomplete", "Incomplete"),
        ("incomplete_expired", "Incomplete Expired"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    studio = models.ForeignKey(Studio, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.RESTRICT, related_name="subscriptions")
    student = models.ForeignKey(
        "core.Student", on_delete=models.CASCADE, related_name="subscriptions"
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="incomplete")
    
    stripe_subscription_id = models.CharField(max_length=200, blank=True, db_index=True)
    stripe_customer_id = models.CharField(max_length=200, blank=True)
    
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscriptions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student} - {self.plan.name} ({self.status})"

