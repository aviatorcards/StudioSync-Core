import logging

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

import stripe
from rest_framework import permissions, status, views
from rest_framework.response import Response

from .models import Invoice, Payment

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


class CreateCheckoutSessionView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, invoice_id):
        if not settings.STRIPE_SECRET_KEY:
            return Response(
                {"error": "Stripe is not configured. Please add STRIPE_SECRET_KEY to your environment."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        invoice = get_object_or_404(Invoice, id=invoice_id)

        # Determine success/cancel URLs
        domain_url = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3000")


        try:
            checkout_session = stripe.checkout.Session.create(
                client_reference_id=str(invoice.id),
                success_url=domain_url + "/payment/success?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=domain_url + "/payment/cancel",
                payment_method_types=["card"],
                mode="payment",
                line_items=[
                    {
                        "price_data": {
                            "currency": "usd",
                            "product_data": {
                                "name": f"Invoice {invoice.invoice_number}",
                                "description": f"Payment for Invoice {invoice.invoice_number}",
                            },
                            "unit_amount": int(float(invoice.total_amount) * 100),
                        },
                        "quantity": 1,
                    }
                ],
                customer_email=(
                    invoice.student.user.email if invoice.student and invoice.student.user else None
                ),
                metadata={"invoice_id": str(invoice.id), "invoice_number": invoice.invoice_number},
            )

            invoice.stripe_session_id = checkout_session["id"]
            invoice.save()

            return Response({"sessionId": checkout_session["id"], "url": checkout_session["url"]})
        except Exception as e:
            logger.error(f"Stripe Checkout Error: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class CreateSubscriptionCheckoutSessionView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, plan_id):
        from .models import SubscriptionPlan, Subscription
        plan = get_object_or_404(SubscriptionPlan, id=plan_id)
        
        student = getattr(request.user, "student_profile", None)
        if not student and request.user.role == "student":
            from studiosync_core.core.models import Student
            student = Student.objects.filter(user=request.user).first()

        if not student:
            return Response({"error": "Could not identify student profile."}, status=400)

        domain_url = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3000")

        
        try:
            subscription = Subscription.objects.create(
                studio=plan.studio,
                plan=plan,
                student=student,
                status="incomplete"
            )

            checkout_session = stripe.checkout.Session.create(
                client_reference_id=str(subscription.id),
                success_url=domain_url + "/payment/success?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=domain_url + "/payment/cancel",
                payment_method_types=["card"],
                mode="subscription",
                line_items=[
                    {
                        "price_data": {
                            "currency": "usd",
                            "product_data": {
                                "name": plan.name,
                                "description": plan.description or f"Subscription to {plan.name}",
                            },
                            "unit_amount": int(float(plan.price) * 100),
                            "recurring": {
                                "interval": plan.interval,
                            }
                        },
                        "quantity": 1,
                    }
                ],
                customer_email=request.user.email,
                metadata={"subscription_id": str(subscription.id), "type": "subscription"},
            )

            return Response({"sessionId": checkout_session["id"], "url": checkout_session["url"]})
        except Exception as e:
            logger.error(f"Stripe Subscription Checkout Error: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class VerifyCheckoutSessionView(views.APIView):
    # Allow unauthenticated access: this endpoint is called right after
    # returning from Stripe checkout, when the JWT access token may have
    # expired during the external redirect. The endpoint only uses the
    # Stripe session ID to verify payment status — no user-specific data.
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        session_id = request.data.get("session_id")
        if not session_id:
            return Response({"error": "session_id is required"}, status=400)
            
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == "paid" or session.status == "complete":
                # Reuse the existing webhook handler safely to apply states
                webhook_view = StripeWebhookView()
                webhook_view.handle_checkout_session(session)
                return Response({"status": "success", "message": "Payment verified"})
            return Response({"status": session.payment_status or session.status})
        except Exception as e:
            logger.error(f"Verify Session Error: {str(e)}")
            return Response({"error": str(e)}, status=400)

@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(views.APIView):
    permission_classes = []

    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        event = None

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        except stripe.error.SignatureVerificationError:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            self.handle_checkout_session(session)

        return Response(status=status.HTTP_200_OK)

    def handle_checkout_session(self, session):
        metadata = session.get("metadata", {})
        if metadata.get("type") == "subscription":
            sub_id = metadata.get("subscription_id") or session.get("client_reference_id")
            if sub_id:
                try:
                    from .models import Subscription
                    sub = Subscription.objects.get(id=sub_id)
                    sub.status = "active"
                    sub.stripe_subscription_id = session.get("subscription")
                    sub.stripe_customer_id = session.get("customer")
                    sub.save()
                    logger.info(f"Subscription {sub.id} activated via Stripe.")
                except Exception as e:
                    logger.error(f"Subscription {sub_id} not found: {e}")
            return

        invoice_id = session.get("client_reference_id")
        if invoice_id:
            try:
                invoice = Invoice.objects.get(id=invoice_id)
                # Avoid duplicates
                if invoice.status != "paid":
                    invoice.status = "paid"
                    invoice.amount_paid = invoice.total_amount
                    invoice.save()

                    Payment.objects.create(
                        invoice=invoice,
                        amount=invoice.total_amount,
                        payment_method="stripe",
                        status="completed",
                        transaction_id=session.get("payment_intent") or session.get("id"),
                        processed_at=timezone.now(),
                    )
                    logger.info(f"Invoice {invoice.invoice_number} marked as paid via Stripe.")
            except Invoice.DoesNotExist:
                logger.error(f"Invoice {invoice_id} not found during webhook processing.")
