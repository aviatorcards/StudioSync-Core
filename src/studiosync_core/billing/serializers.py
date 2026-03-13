from rest_framework import serializers

from .models import Invoice, InvoiceLineItem, Payment, PaymentMethod, SubscriptionPlan, Subscription


class InvoiceLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLineItem
        fields = ["id", "description", "quantity", "unit_price", "total_price", "created_at"]
        read_only_fields = ["total_price", "created_at"]


class InvoiceSerializer(serializers.ModelSerializer):
    line_items = InvoiceLineItemSerializer(many=True, required=False)
    balance_due = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    # Display fields
    student_name = serializers.SerializerMethodField()
    band_name = serializers.SerializerMethodField()
    stripe_transaction_id = serializers.SerializerMethodField()

    def get_stripe_transaction_id(self, obj):
        payment = obj.payments.filter(status='completed').order_by('-processed_at').first()
        if payment and payment.transaction_id:
            return payment.transaction_id
        return obj.stripe_session_id or None

    def get_student_name(self, obj):
        if obj.student and obj.student.user:
            return obj.student.user.get_full_name()
        return ""

    def get_band_name(self, obj):
        return obj.band.name if obj.band else ""

    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoice_number",
            "status",
            "issue_date",
            "due_date",
            "subtotal",
            "tax_amount",
            "discount_amount",
            "total_amount",
            "amount_paid",
            "balance_due",
            "is_overdue",
            "line_items",
            "created_at",
            "notes",
            "band",
            "student",
            "teacher",
            "band_name",
            "student_name",
            "stripe_transaction_id",
        ]
        read_only_fields = [
            "invoice_number",
            "subtotal",
            "total_amount",
            "amount_paid",
            "balance_due",
            "is_overdue",
            "created_at",
        ]

    def create(self, validated_data):
        line_items_data = validated_data.pop("line_items", [])
        invoice = Invoice.objects.create(**validated_data)
        for item_data in line_items_data:
            InvoiceLineItem.objects.create(invoice=invoice, **item_data)
        invoice.calculate_totals()
        return invoice

    def update(self, instance, validated_data):
        line_items_data = validated_data.pop("line_items", [])
        # Update main fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # improving nested update is complex (match IDs etc).
        # For MVP, if line items are provided, replace them? Or just append?
        # Let's assume replacement for now if provided, or append.
        # Actually simpler to just ignore nested update for now unless user asks.
        # But create is strict requirement.

        if line_items_data:
            # Clear old items? Or just add new ones?
            # Safe bet: delete old and re-create if it's a "draft" invoice edit
            if instance.status == "draft":
                instance.line_items.all().delete()
                for item_data in line_items_data:
                    InvoiceLineItem.objects.create(invoice=instance, **item_data)
                instance.calculate_totals()

        return instance


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for payments"""

    invoice_number = serializers.ReadOnlyField(source="invoice.invoice_number")
    processed_by_name = serializers.ReadOnlyField(source="processed_by.get_full_name")

    class Meta:
        model = Payment
        fields = [
            "id",
            "invoice",
            "invoice_number",
            "amount",
            "payment_method",
            "status",
            "transaction_id",
            "notes",
            "processed_by",
            "processed_by_name",
            "processed_at",
            "refunded_at",
            "created_at",
        ]
        read_only_fields = ["processed_by", "processed_at", "created_at"]


class PaymentMethodSerializer(serializers.ModelSerializer):
    """Serializer for payment methods"""

    display_name = serializers.SerializerMethodField()

    class Meta:
        model = PaymentMethod
        fields = [
            "id",
            "band",
            "provider",
            "provider_payment_method_id",
            "card_last_four",
            "card_brand",
            "expiry_month",
            "expiry_year",
            "is_default",
            "is_active",
            "display_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_display_name(self, obj):
        """Get friendly display name for payment method"""
        return str(obj)

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = [
            "id",
            "studio",
            "name",
            "description",
            "price",
            "interval",
            "is_active",
            "stripe_price_id",
            "stripe_product_id",
        ]
        read_only_fields = ["studio"]

class SubscriptionSerializer(serializers.ModelSerializer):
    plan_details = SubscriptionPlanSerializer(source="plan", read_only=True)
    student_name = serializers.ReadOnlyField(source="student.user.get_full_name")

    class Meta:
        model = Subscription
        fields = [
            "id",
            "studio",
            "plan",
            "plan_details",
            "student",
            "student_name",
            "status",
            "stripe_subscription_id",
            "current_period_start",
            "current_period_end",
            "cancel_at_period_end",
        ]
        read_only_fields = ["studio", "status", "stripe_subscription_id", "current_period_start", "current_period_end"]

