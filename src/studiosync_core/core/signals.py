from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from stream_chat import StreamChat
import logging

logger = logging.getLogger(__name__)

from .models import Family, Student, Studio, Teacher, User


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    # Assign to a default studio if none exists for simplicity in this demo
    studio = Studio.objects.first()
    if not studio:
        # Create a default studio if none exists
        admin_user = User.objects.filter(role="admin").first() or instance
        studio = Studio.objects.create(name="Default Studio", owner=admin_user)

    if instance.role == "student":
        Student.objects.get_or_create(user=instance, studio=studio)
    elif instance.role == "teacher":
        Teacher.objects.get_or_create(user=instance, studio=studio)
    elif instance.role == "parent":
        Family.objects.get_or_create(primary_parent=instance, studio=studio)

    # Sync User to Stream Chat
    if not settings.STREAM_API_KEY or not settings.STREAM_API_SECRET:
        logger.warning("Stream API keys are not set. Skipping user sync.")
        return

    try:
        client = StreamChat(api_key=settings.STREAM_API_KEY, api_secret=settings.STREAM_API_SECRET)
        
        user_data = {
            "id": str(instance.id),
            "name": instance.get_full_name(),
        }
        
        # Add avatar if it exists
        if instance.avatar:
            request = getattr(instance, '_request', None)
            if request:
                user_data["image"] = request.build_absolute_uri(instance.avatar.url)
            else:
                user_data["image"] = f"{settings.FRONTEND_BASE_URL}{instance.avatar.url}"

        client.upsert_user(user_data)
        logger.info(f"Successfully synced user {instance.id} to Stream Chat.")
        
    except Exception as e:
        logger.error(f"Error syncing user {instance.id} to Stream Chat: {e}")
