from django.urls import include, path

from rest_framework.routers import DefaultRouter  # noqa: F401

from config.routers import OptionalSlashRouter

from .stripe_views import (
    CreateCheckoutSessionView,
    CreateSubscriptionCheckoutSessionView,
    StripeWebhookView,
    VerifyCheckoutSessionView,
)
from .views import InvoiceViewSet, SubscriptionPlanViewSet, SubscriptionViewSet

router = OptionalSlashRouter()
router.register(r"invoices", InvoiceViewSet, basename="invoice")
router.register(r"subscription-plans", SubscriptionPlanViewSet, basename="subscription-plan")
router.register(r"subscriptions", SubscriptionViewSet, basename="subscription")

urlpatterns = [
    path(
        "create-checkout-session/<str:invoice_id>/",
        CreateCheckoutSessionView.as_view(),
        name="create-checkout-session",
    ),
    path(
        "create-subscription-checkout-session/<str:plan_id>/",
        CreateSubscriptionCheckoutSessionView.as_view(),
        name="create-subscription-checkout-session",
    ),
    path(
        "verify-checkout-session/",
        VerifyCheckoutSessionView.as_view(),
        name="verify-checkout-session",
    ),
    path("webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
    path("", include(router.urls)),
]
