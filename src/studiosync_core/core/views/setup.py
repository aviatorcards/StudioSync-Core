"""
Setup Wizard Views

Handles initial system setup including:
- Studio creation
- Admin user creation
- Feature flag configuration
- Optional sample data generation
"""

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from studiosync_core.core.models import SetupStatus, Student, Studio, Teacher, User
from studiosync_core.core.serializers import SetupWizardCompleteSerializer


@api_view(["GET"])
@permission_classes([AllowAny])
def check_setup_status(request):
    """
    Check if initial setup has been completed.

    Returns:
        Response with setup status including:
        - is_completed: bool
        - setup_required: bool
        - completed_at: datetime (optional)
        - setup_version: str (optional)
        - features_enabled: dict of feature flags
    """
    setup = SetupStatus.objects.first()

    if not setup:
        return Response(
            {
                "is_completed": False,
                "setup_required": True,
                "message": "Initial setup required",
                "features_enabled": {},
            }
        )

    return Response(
        {
            "is_completed": setup.is_completed,
            "setup_required": not setup.is_completed,
            "completed_at": setup.completed_at,
            "setup_version": setup.setup_version,
            "features_enabled": setup.features_enabled or {},
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
@transaction.atomic
def complete_setup_wizard(request):
    """
    Complete the entire setup wizard in one atomic transaction.

    Creates:
    - Admin User
    - Studio
    - Feature Flags
    - Optionally: Sample data (teachers, students)

    Returns:
        Response with created entities and JWT tokens for immediate login
    """

    # Check if setup already completed
    setup_status = SetupStatus.objects.first()
    if setup_status and setup_status.is_completed:
        return Response(
            {"detail": "Setup has already been completed"}, status=status.HTTP_400_BAD_REQUEST
        )

    # Validate input
    serializer = SetupWizardCompleteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    try:
        # 1. Create Admin User
        admin_user = User.objects.create_user(
            email=data["admin_email"],
            password=data["admin_password"],
            first_name=data["admin_first_name"],
            last_name=data["admin_last_name"],
            phone=data.get("admin_phone", ""),
            role="admin",
            is_staff=True,
            is_active=True,
            timezone=data.get("timezone", "UTC"),
        )

        # 1.5 Save Email Settings to Admin Preferences
        if data.get("smtp_host"):
            admin_user.preferences["technical"] = {
                "smtp_host": data["smtp_host"],
                "smtp_port": data["smtp_port"],
                "smtp_username": data["smtp_username"],
                "smtp_password": data["smtp_password"],
                "smtp_from_email": data["smtp_from_email"],
                "smtp_use_tls": data["smtp_use_tls"],
            }
            admin_user.save()

        # 2. Setup Studio
        # Check if signals.py already created a default studio for this user
        studio = Studio.objects.filter(owner=admin_user).first()
        if studio:
            studio.name = data["studio_name"]
            studio.email = data["studio_email"]
            studio.phone = data.get("studio_phone", "")
            studio.address_line1 = data.get("address_line1", "")
            studio.address_line2 = data.get("address_line2", "")
            studio.city = data.get("city", "")
            studio.state = data.get("state", "")
            studio.postal_code = data.get("postal_code", "")
            studio.country = data.get("country", "US")
            studio.timezone = data.get("timezone", "UTC")
            studio.currency = data.get("currency", "USD")
            studio.settings["default_lesson_duration"] = data.get("default_lesson_duration", 60)
            studio.settings["business_start_hour"] = data.get("business_start_hour", 9)
            studio.settings["business_end_hour"] = data.get("business_end_hour", 18)
            studio.is_active = True
            studio.save()
        else:
            studio = Studio.objects.create(
                name=data["studio_name"],
                email=data["studio_email"],
                phone=data.get("studio_phone", ""),
                address_line1=data.get("address_line1", ""),
                address_line2=data.get("address_line2", ""),
                city=data.get("city", ""),
                state=data.get("state", ""),
                postal_code=data.get("postal_code", ""),
                country=data.get("country", "US"),
                timezone=data.get("timezone", "UTC"),
                currency=data.get("currency", "USD"),
                owner=admin_user,
                settings={
                    "default_lesson_duration": data.get("default_lesson_duration", 60),
                    "business_start_hour": data.get("business_start_hour", 9),
                    "business_end_hour": data.get("business_end_hour", 18),
                },
                is_active=True,
            )

        # Feature flags system has been removed - all features are enabled by default

        # 4. Create/Update Setup Status
        if not setup_status:
            setup_status = SetupStatus.objects.create(
                is_completed=True,
                completed_at=timezone.now(),
                setup_version="1.0",
                features_enabled={
                    feature: data.get(f"{feature}_enabled", True)
                    for feature in [
                        "billing",
                        "inventory",
                        "messaging",
                        "resources",
                        "goals",
                        "bands",
                        "analytics",
                        "practice_rooms",
                    ]
                },
                setup_data={
                    "language": data.get("language", "en"),
                    "completed_by": admin_user.email,
                },
            )
        else:
            setup_status.mark_complete()
            setup_status.features_enabled = {
                feature: data.get(f"{feature}_enabled", True)
                for feature in [
                    "billing",
                    "inventory",
                    "messaging",
                    "resources",
                    "goals",
                    "bands",
                    "analytics",
                    "practice_rooms",
                ]
            }
            setup_status.setup_data = {
                "language": data.get("language", "en"),
                "completed_by": admin_user.email,
            }
            setup_status.save()

        # 5. Create Sample Data (if requested)
        if data.get("create_sample_data", False):
            _create_sample_data(studio, admin_user)

        # 6. Send Welcome Email if SMTP is configured
        if data.get("smtp_host"):
            try:
                subject = f"Welcome to StudioSync, {admin_user.first_name}!"
                message = f"""
Hi {admin_user.first_name},

Congratulations! Your studio, {studio.name}, has been successfully set up on StudioSync.

You can now start:
- Onboarding instructors and students
- Building your resource library
- Managing your schedule and billing

If you have any questions, feel free to reach out to our support team.

Best regards,
the StudioSync Team
                """
                send_mail(
                    subject,
                    message,
                    data.get("smtp_from_email") or settings.DEFAULT_FROM_EMAIL,
                    [admin_user.email],
                    fail_silently=True,
                )
            except Exception as e:
                print(f"Failed to send welcome email: {e}")

        # Generate tokens for immediate redirect
        refresh = RefreshToken.for_user(admin_user)

        return Response(
            {
                "message": "Setup completed successfully",
                "studio": {"id": str(studio.id), "name": studio.name, "email": studio.email},
                "user": {
                    "id": str(admin_user.id),
                    "email": admin_user.email,
                    "first_name": admin_user.first_name,
                    "last_name": admin_user.last_name,
                    "role": admin_user.role,
                },
                "tokens": {"access": str(refresh.access_token), "refresh": str(refresh)},
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        # Transaction will rollback automatically due to @transaction.atomic
        return Response(
            {"detail": f"Setup failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _create_sample_data(studio, admin_user):
    """
    Create sample teachers, students, and lessons for demo purposes.

    Args:
        studio: Studio instance
        admin_user: Admin user instance
    """
    # Sample Teacher
    teacher_user = User.objects.create_user(
        email=f'teacher@{studio.name.lower().replace(" ", "")}.demo',
        password="SamplePassword123!",
        first_name="Sarah",
        last_name="Johnson",
        role="teacher",
        timezone=studio.timezone,
    )
    # Use update_or_create because signals might have already created a shell profile
    teacher, _ = Teacher.objects.update_or_create(
        user=teacher_user,
        defaults={
            "studio": studio,
            "bio": "Experienced piano and vocal instructor",
            "specialties": ["Piano", "Voice"],
            "instruments": ["Piano", "Voice"],
            "hourly_rate": 75.00,
            "is_active": True,
        },
    )

    # Sample Students
    for first, last, instrument in [
        ("Emma", "Davis", "Piano"),
        ("Liam", "Wilson", "Guitar"),
        ("Olivia", "Martinez", "Voice"),
    ]:
        student_user = User.objects.create_user(
            email=f"{first.lower()}.{last.lower()}@example.com",
            password="SamplePassword123!",
            first_name=first,
            last_name=last,
            role="student",
            timezone=studio.timezone,
        )
        # Use update_or_create because signals might have already created a shell profile
        Student.objects.update_or_create(
            user=student_user,
            defaults={
                "studio": studio,
                "instrument": instrument,
                "primary_teacher": teacher,
                "is_active": True,
            },
        )
