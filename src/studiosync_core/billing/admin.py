"""
Django Admin configuration for Billing models
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import Invoice, InvoiceLineItem, Payment, PaymentMethod


class InvoiceLineItemInline(admin.TabularInline):
    """Inline admin for invoice line items"""

    model = InvoiceLineItem
    extra = 1
    fields = ["description", "quantity", "unit_price", "total_price", "lesson"]
    readonly_fields = ["total_price"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Django Admin interface for Invoice model"""

    list_display = [
        "invoice_number",
        "get_client",
        "total_amount",
        "amount_paid",
        "balance_due",
        "status_badge",
        "issue_date",
        "due_date",
    ]
    list_filter = ["status", "issue_date", "due_date", "studio"]
    search_fields = [
        "invoice_number",
        "band__name",
        "student__user__first_name",
        "student__user__last_name",
        "student__user__email",
    ]
    readonly_fields = [
        "id",
        "invoice_number",
        "created_at",
        "updated_at",
        "balance_due",
        "is_overdue",
    ]
    inlines = [InvoiceLineItemInline]
    fieldsets = (
        ("Basic Information", {"fields": ("invoice_number", "studio", "status", "teacher")}),
        ("Bill To", {"fields": ("band", "student")}),
        (
            "Amounts",
            {
                "fields": (
                    "subtotal",
                    "tax_amount",
                    "discount_amount",
                    "late_fee_amount",
                    "total_amount",
                    "amount_paid",
                    "balance_due",
                )
            },
        ),
        ("Dates", {"fields": ("issue_date", "due_date", "paid_date", "sent_at", "is_overdue")}),
        ("Notes", {"fields": ("notes", "internal_notes"), "classes": ("collapse",)}),
        (
            "Payment Integration",
            {"fields": ("stripe_session_id", "late_fee_applied"), "classes": ("collapse",)},
        ),
        ("Metadata", {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_client(self, obj):
        """Get the client name (band or student)"""
        if obj.band:
            return obj.band.name
        elif obj.student:
            return obj.student.user.get_full_name() or obj.student.user.email
        return "Unknown"

    get_client.short_description = "Client"

    def status_badge(self, obj):
        """Display status as a colored badge"""
        colors = {
            "draft": "#5A6B4F",  # Neutral Dark
            "sent": "#6B8E23",  # Olive Primary
            "paid": "#556B2F",  # Olive Dark
            "partial": "#E8A845",  # Warm Amber
            "overdue": "#C4704F",  # Earth Primary (Terracotta)
            "cancelled": "#8A9780",  # Light Neutral
        }
        color = colors.get(obj.status, "#5A6B4F")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Django Admin interface for Payment model"""

    list_display = [
        "__str__",
        "invoice",
        "amount",
        "payment_method",
        "status_badge",
        "processed_at",
        "processed_by",
    ]
    list_filter = ["status", "payment_method", "processed_at"]
    search_fields = [
        "invoice__invoice_number",
        "transaction_id",
        "notes",
    ]
    readonly_fields = ["id", "created_at", "processed_at", "refunded_at"]
    fieldsets = (
        ("Payment Details", {"fields": ("invoice", "amount", "payment_method", "status")}),
        ("Transaction Info", {"fields": ("transaction_id", "notes", "processed_by")}),
        (
            "Timestamps",
            {"fields": ("created_at", "processed_at", "refunded_at"), "classes": ("collapse",)},
        ),
        ("Metadata", {"fields": ("id",), "classes": ("collapse",)}),
    )

    def status_badge(self, obj):
        """Display status as a colored badge"""
        colors = {
            "pending": "#E8A845",  # Warm Amber
            "completed": "#556B2F",  # Olive Dark
            "failed": "#C4704F",  # Earth Primary (Terracotta)
            "refunded": "#5A6B4F",  # Neutral Dark
        }
        color = colors.get(obj.status, "#5A6B4F")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    """Django Admin interface for PaymentMethod model"""

    list_display = [
        "__str__",
        "band",
        "provider",
        "is_default",
        "is_active",
        "created_at",
    ]
    list_filter = ["provider", "is_default", "is_active", "created_at"]
    search_fields = [
        "band__name",
        "provider",
        "card_last_four",
        "provider_payment_method_id",
    ]
    readonly_fields = ["id", "created_at", "updated_at"]
    fieldsets = (
        ("Basic Information", {"fields": ("band", "provider", "provider_payment_method_id")}),
        (
            "Card Details",
            {"fields": ("card_brand", "card_last_four", "expiry_month", "expiry_year")},
        ),
        ("Status", {"fields": ("is_default", "is_active")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
        ("Metadata", {"fields": ("id",), "classes": ("collapse",)}),
    )
