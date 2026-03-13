import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from django_q.tasks import async_task

from .email_utils import get_email_settings

logger = logging.getLogger(__name__)


def send_email_async(subject, to_email, template_name, context, from_email=None, from_name=None):
    """
    Background task to send emails asynchronously using HTML templates.
    """
    try:
        email_settings = get_email_settings()

        real_from_email = from_email or email_settings["from_email"]
        real_from_name = from_name or email_settings["from_name"]

        # Add common context variables
        context["site_name"] = real_from_name

        # Render HTML body
        html_content = render_to_string(template_name, context)
        text_content = strip_tags(html_content)

        # Configure connection if settings found in DB
        connection = None
        smtp_config = email_settings.get("smtp_config")
        if smtp_config and smtp_config.get("host"):
            connection = get_connection(
                backend="django.core.mail.backends.smtp.EmailBackend",
                host=smtp_config["host"],
                port=int(smtp_config["port"]),
                username=smtp_config["username"],
                password=smtp_config["password"],
                use_tls=smtp_config.get("use_tls", True),
                use_ssl=smtp_config.get("use_ssl", False),
                timeout=10,
            )

        # Construct From header
        if real_from_name and real_from_name != real_from_email:
            final_from = f"{real_from_name} <{real_from_email}>"
        else:
            final_from = real_from_email

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=final_from,
            to=[to_email],
            connection=connection,
        )
        email.attach_alternative(html_content, "text/html")
        email.send()

        logger.info(f"✅ Email sent to {to_email} (Template: {template_name})")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send email to {to_email}: {e}")
        return False


def check_upcoming_lessons():
    """
    Periodic task to check for upcoming lessons and send reminders.
    Runs hourly. Checks for lessons starting between 23 and 25 hours from now.
    """
    from datetime import timedelta

    from django.utils import timezone

    from studiosync_core.lessons.models import Lesson
    from studiosync_core.notifications.models import Notification

    now = timezone.now()
    start_window = now + timedelta(hours=23)
    end_window = now + timedelta(hours=25)

    # Find active lessons in the window
    upcoming_lessons = Lesson.objects.filter(
        scheduled_start__range=(start_window, end_window), status="scheduled"
    )

    logger.info(
        f"Checking for lesson reminders. Found {upcoming_lessons.count()} lessons in window."
    )

    reminders_sent = 0

    for lesson in upcoming_lessons:
        # Check if reminder already sent to student
        student_reminder_exists = Notification.objects.filter(
            related_lesson_id=lesson.id,
            notification_type="lesson_reminder",
            user=lesson.student.user,
        ).exists()

        if not student_reminder_exists:
            try:
                user = lesson.student.user
                
                # Create in-app notification (respecting prefs)
                if user.wants_notification("lesson_reminder", "push"):
                    Notification.create_notification(
                        user=user,
                        notification_type="lesson_reminder",
                        title="Upcoming Lesson Reminder",
                        message=f'Your {lesson.student.instrument} lesson is tomorrow at {lesson.scheduled_start.strftime("%I:%M %p")}',
                        link=f"/dashboard/lessons/{lesson.id}",
                    )

                # Send Email (respecting prefs)
                if user.wants_notification("lesson_reminder", "email"):
                    context = {
                        "instructor_name": lesson.teacher.user.get_full_name(),
                        "lesson_start_time": lesson.scheduled_start.strftime("%A, %B %d at %I:%M %p"),
                        "location": lesson.location,
                        "student_name": lesson.student.user.get_full_name(),
                        "instrument": lesson.student.instrument,
                        "duration_minutes": lesson.duration_minutes,
                        "lesson_url": f"{settings.FRONTEND_BASE_URL}/dashboard/lessons/{lesson.id}",
                    }

                    async_task(
                        send_email_async,
                        "Lesson Reminder 🎵",
                        user.email,
                        "emails/lesson_reminder.html",
                        context,
                    )
                    reminders_sent += 1
            except Exception as e:
                logger.error(f"Failed to send reminder for lesson {lesson.id}: {e}")

    return f"Sent {reminders_sent} reminders"
