from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from studiosync_core.core.models import User  # Need Studio for Thread creation

from .models import Message, MessageThread
from .serializers import MessageSerializer, MessageThreadSerializer


from django.conf import settings
from stream_chat import StreamChat
from rest_framework.views import APIView

class StreamTokenView(APIView):
    """
    Generate a Stream Chat token for the authenticated user.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not settings.STREAM_API_KEY or not settings.STREAM_API_SECRET:
            return Response({"error": "Stream Chat API keys are not configured."}, status=500)

        try:
            client = StreamChat(api_key=settings.STREAM_API_KEY, api_secret=settings.STREAM_API_SECRET)
            token = client.create_token(str(request.user.id))
            return Response({"token": token, "apiKey": settings.STREAM_API_KEY})
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class MessageThreadViewSet(viewsets.ModelViewSet):
    """
    API for managing conversation threads
    """

    serializer_class = MessageThreadSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["subject", "participants__first_name", "participants__last_name"]
    ordering_fields = ["updated_at"]
    ordering = ["-updated_at"]

    def get_queryset(self):
        # Users see threads they are participants in
        return MessageThread.objects.filter(participants=self.request.user)

    def create(self, request, *args, **kwargs):
        """
        Create a new thread. params: recipient_ids (list), subject, initial_message
        """
        recipient_ids = request.data.get("recipient_ids", [])
        subject = request.data.get("subject", "")
        initial_message_body = request.data.get("message", "")

        if not recipient_ids or not initial_message_body:
            return Response(
                {"error": " recipients and message body required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get participants
        recipients = User.objects.filter(id__in=recipient_ids)
        if not recipients.exists():
            return Response({"error": "Invalid recipients"}, status=status.HTTP_400_BAD_REQUEST)

        # Find or create Studio (Assuming single studio context for now or derived from user)
        # For MV, try to get studio from request.user's teacher profile or student profile
        # Or just pick the first one related to the user.
        # Fallback: Create without studio if allowed? Model says studio is required.
        # Let's try to infer studio.

        studio = None
        if hasattr(request.user, "teacher_profile"):
            studio = request.user.teacher_profile.studio
        elif hasattr(request.user, "student_profile"):
            studio = request.user.student_profile.studio
        elif hasattr(request.user, "owned_studios") and request.user.owned_studios.exists():
            studio = request.user.owned_studios.first()

        if not studio:
            # Try to infer from recipients?
            for r in recipients:
                if hasattr(r, "teacher_profile"):
                    studio = r.teacher_profile.studio
                    break

        if not studio:
            return Response(
                {"error": "Could not determine context (Studio) for this message"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create Thread
        thread = MessageThread.objects.create(studio=studio, subject=subject)
        thread.participants.add(request.user)
        thread.participants.add(*recipients)

        # Create Initial Message
        message = Message.objects.create(
            thread=thread, sender=request.user, body=initial_message_body
        )
        # Mark read by sender
        message.read_by.add(request.user)

        serializer = self.get_serializer(thread)
        
        # Notify via WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"chat_{thread.id}",
            {
                "type": "chat_message",
                "message": MessageSerializer(message).data
            }
        )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def reply(self, request, pk=None):
        """Reply to a thread"""
        thread = self.get_object()
        body = request.data.get("body")

        if not body:
            return Response({"error": "Body required"}, status=status.HTTP_400_BAD_REQUEST)

        message = Message.objects.create(thread=thread, sender=request.user, body=body)
        message.read_by.add(request.user)

        # Touch thread update time
        thread.save()  # Updates updated_at auto_now

        # Notify via WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"chat_{thread.id}",
            {
                "type": "chat_message",
                "message": MessageSerializer(message).data
            }
        )

        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        """Get all messages in thread"""
        thread = self.get_object()
        messages = thread.messages.all().order_by("created_at")

        # Mark all as read for this user?
        # Or allow manual marking. Usually opening thread marks as read.
        for msg in messages:
            msg.read_by.add(request.user)

        return Response(MessageSerializer(messages, many=True).data)

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        thread = self.get_object()
        for msg in thread.messages.all():
            msg.read_by.add(request.user)
        return Response({"status": "read"})
