"""
Notification System Models
Handles in-app notifications for students, teachers, and admins
"""

from django.db import models
from django.utils import timezone

from studiosync_core.core.models import User


class Notification(models.Model):
    """
    In-app notifications for users
    """

    NOTIFICATION_TYPES = [
        ("welcome", "Welcome"),
        ("lesson_scheduled", "Lesson Scheduled"),
        ("lesson_reminder", "Lesson Reminder"),
        ("lesson_cancelled", "Lesson Cancelled"),
        ("new_student", "New Student"),
        ("new_message", "New Message"),
        ("payment_received", "Payment Received"),
        ("payment_due", "Payment Due"),
        ("document_pending", "Document Pending Signature"),
        ("document_signed", "Document Signed"),
        ("system_update", "System Update"),
        ("inventory_request", "Inventory Request"),
        ("room_reserved", "Practice Room Reserved"),
        ("instructor_request", "Instructor Role Request"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_notifications")
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=500, blank=True, null=True, help_text="Internal app link")

    read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    # Optional: Link to related objects
    related_lesson_id = models.IntegerField(null=True, blank=True)
    related_student_id = models.IntegerField(null=True, blank=True)
    related_message_id = models.IntegerField(null=True, blank=True)
    related_document_id = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "read"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.title}"

    def mark_as_read(self):
        """Mark notification as read"""
        if not self.read:
            self.read = True
            self.read_at = timezone.now()
            self.save(update_fields=["read", "read_at"])

    @classmethod
    def create_notification(cls, user, notification_type, title, message, link=None, **kwargs):
        """Helper method to create notifications"""
        return cls.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
            **kwargs,
        )

    @classmethod
    def notify_lesson_scheduled(cls, lesson):
        """Create notification for newly scheduled lesson"""
        # Notify student
        if lesson.student and lesson.student.user:
            user = lesson.student.user
            if user.wants_notification("lesson_scheduled", "push"):
                cls.create_notification(
                    user=user,
                    notification_type="lesson_scheduled",
                    title="New Lesson Scheduled",
                    message=f'Your {lesson.student.instrument} lesson is scheduled for {lesson.scheduled_start.strftime("%B %d at %I:%M %p")}',
                    link=f"/dashboard/lessons/{lesson.id}",
                    related_lesson_id=lesson.id,
                )

        # Notify teacher
        if lesson.teacher and lesson.teacher.user:
            user = lesson.teacher.user
            if user.wants_notification("lesson_scheduled", "push"):
                cls.create_notification(
                    user=user,
                    notification_type="lesson_scheduled",
                    title="New Lesson Scheduled",
                    message=f'Lesson with {lesson.student.user.get_full_name()} scheduled for {lesson.scheduled_start.strftime("%B %d at %I:%M %p")}',
                    link=f"/dashboard/lessons/{lesson.id}",
                    related_lesson_id=lesson.id,
                )

    @classmethod
    def notify_new_student(cls, teacher_user, student):
        """Notify teacher of new student assignment"""
        if teacher_user.wants_notification("new_student", "push"):
            cls.create_notification(
                user=teacher_user,
                notification_type="new_student",
                title="New Student Assigned",
                message=f"{student.user.get_full_name()} has been added to your students",
                link=f"/dashboard/students/{student.id}",
                related_student_id=student.id,
            )

    @classmethod
    def notify_upcoming_lesson(cls, lesson, hours_before=24):
        """Send reminder notification for upcoming lesson"""
        # Notify student
        if lesson.student and lesson.student.user:
            user = lesson.student.user
            if user.wants_notification("lesson_reminder", "push"):
                cls.create_notification(
                    user=user,
                    notification_type="lesson_reminder",
                    title="Upcoming Lesson Reminder",
                    message=f'Your {lesson.student.instrument} lesson is tomorrow at {lesson.scheduled_start.strftime("%I:%M %p")}',
                    link=f"/dashboard/lessons/{lesson.id}",
                    related_lesson_id=lesson.id,
                )

        # Notify teacher
        if lesson.teacher and lesson.teacher.user:
            user = lesson.teacher.user
            if user.wants_notification("lesson_reminder", "push"):
                cls.create_notification(
                    user=user,
                    notification_type="lesson_reminder",
                    title="Upcoming Lesson Reminder",
                    message=f'Lesson with {lesson.student.user.get_full_name()} tomorrow at {lesson.scheduled_start.strftime("%I:%M %p")}',
                    link=f"/dashboard/lessons/{lesson.id}",
                    related_lesson_id=lesson.id,
                )

    @classmethod
    def notify_document_pending(cls, user, document_name):
        """Notify user of document requiring signature"""
        cls.create_notification(
            user=user,
            notification_type="document_pending",
            title="Document Requires Signature",
            message=f"Please review and sign: {document_name}",
            link="/dashboard/resources",
        )

    @classmethod
    def notify_admin_instructor_request(cls, requester_user):
        """Notify all admins that a user requested instructor role"""
        admin_users = User.objects.filter(role="admin")
        for admin in admin_users:
            cls.create_notification(
                user=admin,
                notification_type="instructor_request",
                title="Instructor Role Requested",
                message=f"{requester_user.get_full_name()} ({requester_user.email}) has requested to be an instructor.",
                link="/dashboard/users",
            )

    @classmethod
    def notify_admin_new_student_registration(cls, student_user):
        """Notify all admins that a new student has registered and needs approval"""
        admin_users = User.objects.filter(role="admin")
        for admin in admin_users:
            cls.create_notification(
                user=admin,
                notification_type="new_student",
                title="New Student Registration",
                message=f"New student {student_user.get_full_name()} ({student_user.email}) has registered and is pending approval.",
                link="/dashboard/users",
            )
