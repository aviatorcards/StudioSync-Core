from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Notification
from .serializers import NotificationSerializer

@receiver(post_save, sender=Notification)
def broadcast_notification(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        if channel_layer:
            user_group = f"user_notifications_{instance.user.id}"
            serializer = NotificationSerializer(instance)
            async_to_sync(channel_layer.group_send)(
                user_group,
                {
                    "type": "send_notification",
                    "notification": serializer.data
                }
            )
