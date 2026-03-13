import os

from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from studiosync_core.resources.models import Resource

from .models import Band, Studio, User


@receiver(post_delete, sender=User)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    """
    Deletes file from filesystem
    when corresponding User object is deleted.
    """
    if instance.avatar:
        if os.path.isfile(instance.avatar.path):
            os.remove(instance.avatar.path)


@receiver(pre_save, sender=User)
def auto_delete_file_on_change(sender, instance, **kwargs):
    """
    Stores old file path to be deleted in post_save
    """
    if not instance.pk:
        return

    try:
        old_file = User.objects.get(pk=instance.pk).avatar
    except User.DoesNotExist:
        return

    new_file = instance.avatar
    if not old_file == new_file:
        instance._old_avatar_path = old_file.path if old_file else None


@receiver(models.signals.post_save, sender=User)
def auto_delete_file_post_save(sender, instance, **kwargs):
    """
    Deletes the old file after the new one is saved to allow Django
    to generate a fresh filename for cache-busting.
    """
    if hasattr(instance, '_old_avatar_path') and instance._old_avatar_path:
        if os.path.isfile(instance._old_avatar_path):
            os.remove(instance._old_avatar_path)
        delattr(instance, '_old_avatar_path')


# Similar handlers for other models with files
@receiver(post_delete, sender=Band)
def auto_delete_band_photo_on_delete(sender, instance, **kwargs):
    if instance.photo:
        if os.path.isfile(instance.photo.path):
            os.remove(instance.photo.path)


@receiver(pre_save, sender=Band)
def auto_delete_band_photo_on_change(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old_file = Band.objects.get(pk=instance.pk).photo
    except Band.DoesNotExist:
        return
    new_file = instance.photo
    if not old_file == new_file:
        instance._old_photo_path = old_file.path if old_file else None


@receiver(models.signals.post_save, sender=Band)
def auto_delete_band_photo_post_save(sender, instance, **kwargs):
    if hasattr(instance, '_old_photo_path') and instance._old_photo_path:
        if os.path.isfile(instance._old_photo_path):
            os.remove(instance._old_photo_path)
        delattr(instance, '_old_photo_path')


@receiver(post_delete, sender=Studio)
def auto_delete_studio_cover_on_delete(sender, instance, **kwargs):
    if instance.cover_image:
        if os.path.isfile(instance.cover_image.path):
            os.remove(instance.cover_image.path)


@receiver(pre_save, sender=Studio)
def auto_delete_studio_cover_on_change(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old_file = Studio.objects.get(pk=instance.pk).cover_image
    except Studio.DoesNotExist:
        return
    new_file = instance.cover_image
    if not old_file == new_file:
        instance._old_cover_image_path = old_file.path if old_file else None


@receiver(models.signals.post_save, sender=Studio)
def auto_delete_studio_cover_post_save(sender, instance, **kwargs):
    if hasattr(instance, '_old_cover_image_path') and instance._old_cover_image_path:
        if os.path.isfile(instance._old_cover_image_path):
            os.remove(instance._old_cover_image_path)
        delattr(instance, '_old_cover_image_path')


@receiver(post_delete, sender=Resource)
def auto_delete_resource_file_on_delete(sender, instance, **kwargs):
    if instance.file:
        if os.path.isfile(instance.file.path):
            os.remove(instance.file.path)


@receiver(pre_save, sender=Resource)
def auto_delete_resource_file_on_change(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old_file = Resource.objects.get(pk=instance.pk).file
    except Resource.DoesNotExist:
        return
    new_file = instance.file
    if not old_file == new_file:
        instance._old_resource_path = old_file.path if old_file else None


@receiver(models.signals.post_save, sender=Resource)
def auto_delete_resource_file_post_save(sender, instance, **kwargs):
    if hasattr(instance, '_old_resource_path') and instance._old_resource_path:
        if os.path.isfile(instance._old_resource_path):
            os.remove(instance._old_resource_path)
        delattr(instance, '_old_resource_path')
