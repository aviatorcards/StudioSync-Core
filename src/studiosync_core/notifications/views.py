from django.utils import timezone

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user notifications
    """

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return notifications for current user only"""
        return Notification.objects.filter(user=self.request.user)

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        """Get count of unread notifications"""
        count = self.get_queryset().filter(read=False).count()
        return Response({"count": count})

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        """Mark all notifications as read"""
        updated = self.get_queryset().filter(read=False).update(read=True, read_at=timezone.now())
        return Response({"message": f"{updated} notifications marked as read", "count": updated})

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        """Mark a single notification as read"""
        notification = self.get_object()
        notification.mark_as_read()
        return Response(
            {
                "message": "Notification marked as read",
                "notification": NotificationSerializer(notification).data,
            }
        )

    @action(detail=False, methods=["delete"])
    def clear_all(self, request):
        """Delete all read notifications"""
        deleted_count, _ = self.get_queryset().filter(read=True).delete()
        return Response(
            {"message": f"{deleted_count} notifications cleared", "count": deleted_count}
        )

    @action(detail=False, methods=["get"])
    def recent(self, request):
        """Get recent notifications (last 50)"""
        notifications = self.get_queryset()[:50]
        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data)
