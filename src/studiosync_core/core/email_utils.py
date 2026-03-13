import logging

from django.conf import settings

from studiosync_core.core.models import User

logger = logging.getLogger(__name__)

# Import the shared task from tasks.py (to avoid circular dependency issues, import inside functions if needed)
# However, usually tasks are imported at module level if valid.
# Ideally, email_utils should just disable the async implementation here OR import it.


def get_email_settings():
    """
    Get email settings from admin user preferences.
    """
    try:
        admin = User.objects.filter(role="admin").first()
        from_name = getattr(settings, "SITE_NAME", "StudioSync")
        from_email_address = settings.DEFAULT_FROM_EMAIL

        smtp_config = {}

        if admin and admin.preferences and "technical" in admin.preferences:
            tech_settings = admin.preferences["technical"]
            from_name = tech_settings.get("smtp_from_name", from_name)
            custom_from = tech_settings.get("smtp_from_email")
            if custom_from:
                from_email_address = custom_from

            # Extract SMTP settings for the connection
            smtp_config = {
                "host": tech_settings.get("smtp_host"),
                "port": tech_settings.get("smtp_port"),
                "username": tech_settings.get("smtp_username"),
                "password": tech_settings.get("smtp_password"),
                "use_tls": tech_settings.get("smtp_use_tls", True),
            }
            # Heuristic for implicit SSL
            if str(smtp_config.get("port")) == "465":
                smtp_config["use_tls"] = False
                smtp_config["use_ssl"] = True

        return {
            "from_name": from_name,
            "from_email": from_email_address,
            "smtp_config": smtp_config,
        }
    except Exception as e:
        logger.error(f"Error getting email settings: {str(e)}")
        return {
            "from_name": getattr(settings, "SITE_NAME", "StudioSync"),
            "from_email": settings.DEFAULT_FROM_EMAIL,
            "smtp_config": {},  # Return empty dict to use default settings
        }


def send_welcome_email(user_email, first_name, temp_password=None):
    """
    Trigger the async welcome email task.
    """
    from studiosync_core.core.tasks import send_email_async

    subject = "Welcome to StudioSync! 🎵"
    context = {
        "first_name": first_name,
        "user_email": user_email,
        "dashboard_url": f"{settings.FRONTEND_BASE_URL}/login",
        "temp_password": temp_password,
    }
    # Call the background task
    from django_q.tasks import async_task

    async_task(send_email_async, subject, user_email, "emails/welcome_email.html", context)
    return True


def send_registration_pending_email(user_email, first_name):
    """
    Inform the student that their registration is pending approval.
    """
    from studiosync_core.core.tasks import send_email_async

    subject = "Account Registration Received 🎵"
    context = {
        "first_name": first_name,
        "site_name": getattr(settings, "SITE_NAME", "StudioSync"),
    }
    from django_q.tasks import async_task

    async_task(send_email_async, subject, user_email, "emails/registration_pending.html", context)


def send_admin_approval_notification(student_user):
    """
    Notify admins/instructors that a new student needs approval.
    """
    from studiosync_core.core.tasks import send_email_async

    subject = "New Student Pending Approval 🚀"
    # Notify admins and instructors? 
    # Usually instructors are only notified if they are assigned.
    # For now, let's notify all admins and optionally teachers if relevant.
    admin_emails = User.objects.filter(role="admin").values_list("email", flat=True)
    if not admin_emails:
        return

    context = {
        "student_name": student_user.get_full_name(),
        "student_email": student_user.email,
        "dashboard_url": f"{settings.FRONTEND_BASE_URL}/dashboard/users",
    }
    from django_q.tasks import async_task

    for email in admin_emails:
        async_task(send_email_async, subject, email, "emails/admin_approval_request.html", context)


def send_account_approved_email(user_email, first_name):
    """
    Notify the student that their account has been approved.
    """
    from studiosync_core.core.tasks import send_email_async

    subject = "Account Approved! Welcome to StudioSync 🎵"
    context = {
        "first_name": first_name,
        "login_url": f"{settings.FRONTEND_BASE_URL}/login",
    }
    from django_q.tasks import async_task

    async_task(send_email_async, subject, user_email, "emails/account_approved.html", context)


def send_test_email(recipient_email, from_name="StudioSync"):
    """
    Send a test email (synchronous for immediate feedback).
    """
    pass
