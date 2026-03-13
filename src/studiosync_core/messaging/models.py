"""
Messaging models - Message, Thread, Notification
"""

import uuid

from django.db import models
from django.utils import timezone

from studiosync_core.core.models import Studio, User


class MessageThread(models.Model):
    """
    Conversation thread between users
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    studio = models.ForeignKey(Studio, on_delete=models.CASCADE, related_name="message_threads")

    # Participants
    participants = models.ManyToManyField(User, related_name="message_threads")

    # Subject/topic
    subject = models.CharField(max_length=200, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "message_threads"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.subject or f"Thread {self.id}"


class Message(models.Model):
    """
    Individual message in a thread
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(MessageThread, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")

    # Content
    body = models.TextField()

    # Attachments
    attachments = models.JSONField(default=list, blank=True)

    # Read tracking
    read_by = models.ManyToManyField(User, blank=True, related_name="read_messages")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "messages"
        ordering = ["created_at"]

    def __str__(self):
        return f"Message from {self.sender.get_full_name()} at {self.created_at}"


class Notification(models.Model):
    """
    System notifications for users
    """

    NOTIFICATION_TYPE_CHOICES = [
        ("lesson_reminder", "Lesson Reminder"),
        ("lesson_cancelled", "Lesson Cancelled"),
        ("lesson_rescheduled", "Lesson Rescheduled"),
        ("new_message", "New Message"),
        ("invoice_sent", "Invoice Sent"),
        ("invoice_overdue", "Invoice Overdue"),
        ("payment_received", "Payment Received"),
        ("resource_shared", "Resource Shared"),
        ("system", "System Notification"),
    ]

    DELIVERY_METHOD_CHOICES = [
        ("email", "Email"),
        ("sms", "SMS"),
        ("in_app", "In-App"),
        ("push", "Push Notification"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
        ("read", "Read"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="delivery_notifications")

    # Notification details
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPE_CHOICES)
    delivery_method = models.CharField(
        max_length=20, choices=DELIVERY_METHOD_CHOICES, default="in_app"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Content
    title = models.CharField(max_length=200)
    message = models.TextField()

    # Related object (stores ID and type as JSON)
    related_object = models.JSONField(default=dict, blank=True)

    # Action URL (for clickable notifications)
    action_url = models.CharField(max_length=500, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["notification_type"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.user.get_full_name()}"

    def mark_as_read(self):
        """Mark notification as read"""
        if not self.read_at:
            self.read_at = timezone.now()
            self.status = "read"
            self.save()
