from django.contrib.auth import get_user_model

from rest_framework import serializers

from .models import Message, MessageThread, Notification

User = get_user_model()


class MessageUserSerializer(serializers.ModelSerializer):
    """Minimal user info for messages"""

    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "avatar", "role"]


class MessageSerializer(serializers.ModelSerializer):
    sender_details = MessageUserSerializer(source="sender", read_only=True)

    class Meta:
        model = Message
        fields = [
            "id",
            "thread",
            "sender",
            "sender_details",
            "body",
            "attachments",
            "created_at",
            "read_by",
        ]
        read_only_fields = ["thread", "sender", "created_at", "read_by"]


class MessageThreadSerializer(serializers.ModelSerializer):
    participants_details = MessageUserSerializer(source="participants", many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = MessageThread
        fields = [
            "id",
            "subject",
            "participants",
            "participants_details",
            "created_at",
            "updated_at",
            "last_message",
            "unread_count",
        ]
        read_only_fields = ["created_at", "updated_at", "participants"]

    def get_last_message(self, obj):
        last_msg = obj.messages.last()
        if last_msg:
            return MessageSerializer(last_msg).data
        return None

    def get_unread_count(self, obj):
        request = self.context.get("request")
        if not request:
            return 0
        user = request.user
        # Count messages in this thread NOT in user.read_messages
        # Logic: Message.read_by is M2M.
        return obj.messages.exclude(read_by=user).count()


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "notification_type",
            "title",
            "message",
            "related_object",
            "action_url",
            "status",
            "created_at",
            "read_at",
        ]
        read_only_fields = ["created_at", "read_at", "related_object"]
