from django.urls import include, path

from rest_framework.routers import DefaultRouter  # noqa: F401

from config.routers import OptionalSlashRouter

from . import views

router = OptionalSlashRouter()
router.register(r"items", views.InventoryItemViewSet, basename="inventory-item")
router.register(r"checkouts", views.CheckoutLogViewSet, basename="checkout")
router.register(r"practice-rooms", views.PracticeRoomViewSet, basename="practice-room")
router.register(r"reservations", views.RoomReservationViewSet, basename="reservation")

urlpatterns = [
    path("", include(router.urls)),
]
