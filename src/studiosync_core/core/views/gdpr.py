"""
GDPR Compliance Views
Provides data portability, right to erasure, and consent management
"""

import json

from django.http import HttpResponse
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from studiosync_core.lessons.models import Lesson

try:
    from studiosync_core.billing.models import Payment
except ImportError:
    Payment = None  # Billing app might not exist yet


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_my_data(request):
    """
    GDPR Article 20: Right to Data Portability
    Export all user data in machine-readable format
    """
    user = request.user

    # Collect all user data
    user_data = {
        "exported_at": timezone.now().isoformat(),
        "user_info": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "role": user.role,
            "timezone": user.timezone,
            "bio": user.bio,
            "instrument": user.instrument,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "preferences": user.preferences,
        },
        "lessons": [],
        "payments": [],
        "messages": [],
    }

    # Add student-specific data
    if hasattr(user, "student_profile"):
        student = user.student_profile
        user_data["student_info"] = {
            "primary_instrument": student.primary_instrument,
            "enrollment_date": (
                student.enrollment_date.isoformat() if student.enrollment_date else None
            ),
            "notes": student.notes,
        }

        # Add lessons
        lessons = Lesson.objects.filter(student=student).select_related("teacher__user")
        user_data["lessons"] = [
            {
                "date": lesson.scheduled_start.isoformat(),
                "duration_minutes": lesson.duration_minutes,
                "status": lesson.status,
                "teacher": lesson.teacher.user.get_full_name(),
                "notes": lesson.notes,
                "homework": lesson.homework,
            }
            for lesson in lessons
        ]

    # Add teacher-specific data
    if hasattr(user, "teacher_profile"):
        teacher = user.teacher_profile
        user_data["teacher_info"] = {
            "specialization": teacher.specialization,
            "bio": teacher.bio,
            "hourly_rate": str(teacher.hourly_rate) if teacher.hourly_rate else None,
        }

    # Add payment history
    if Payment:
        payments = Payment.objects.filter(user=user)
        user_data["payments"] = [
            {
                "date": payment.created_at.isoformat(),
                "amount": str(payment.amount),
                "status": payment.status,
                "description": payment.description,
            }
            for payment in payments
        ]

    # Return as downloadable JSON file
    response = HttpResponse(json.dumps(user_data, indent=2), content_type="application/json")
    response["Content-Disposition"] = (
        f'attachment; filename="my_data_{user.id}_{timezone.now().strftime("%Y%m%d")}.json"'
    )

    return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def request_account_deletion(request):
    """
    GDPR Article 17: Right to Erasure ("Right to be Forgotten")
    Request account deletion with confirmation
    """
    user = request.user

    # Check if user has confirmed the deletion
    confirm = request.data.get("confirm", False)

    if not confirm:
        return Response(
            {
                "message": "Please confirm account deletion",
                "warning": "This action cannot be undone. All your data will be permanently deleted.",
                "confirm_required": True,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # For teachers/admins, prevent deletion if they have active lessons
    if user.role in ["teacher", "admin"]:
        has_future_lessons = Lesson.objects.filter(
            teacher=user.teacher_profile if hasattr(user, "teacher_profile") else None,
            scheduled_start__gte=timezone.now(),
            status="scheduled",
        ).exists()

        if has_future_lessons:
            return Response(
                {
                    "error": "Cannot delete account with upcoming scheduled lessons",
                    "message": "Please cancel or reassign all future lessons before deleting your account.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    # Mark account for deletion (actual deletion handled by admin)
    user.preferences = user.preferences or {}
    user.preferences["deletion_requested"] = True
    user.preferences["deletion_requested_at"] = timezone.now().isoformat()
    user.save()

    # Notify admins (would typically send email here)

    return Response(
        {
            "message": "Account deletion requested successfully",
            "details": "Your request has been received. An administrator will review and process your deletion request within 30 days.",
            "request_date": timezone.now().isoformat(),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def privacy_dashboard(request):
    """
    GDPR Transparency: Show user all data we have and how it's used
    """
    user = request.user

    # Count user's data
    data_summary = {
        "account": {
            "email": user.email,
            "account_created": user.created_at.isoformat() if user.created_at else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
        },
        "data_counts": {
            "lessons": 0,
            "payments": Payment.objects.filter(user=user).count() if Payment else 0,
            "messages": 0,  # Would count messages if messaging app exists
        },
        "privacy_settings": user.preferences.get("privacy", {}) if user.preferences else {},
        "consents": user.preferences.get("consents", {}) if user.preferences else {},
        "data_retention": {
            "lessons": "Retained for 7 years for tax/record purposes",
            "payments": "Retained for 7 years for tax purposes",
            "messages": "Retained for 2 years unless deleted by user",
            "account": "Active until you request deletion",
        },
    }

    if hasattr(user, "student_profile"):
        data_summary["data_counts"]["lessons"] = Lesson.objects.filter(
            student=user.student_profile
        ).count()
    elif hasattr(user, "teacher_profile"):
        data_summary["data_counts"]["lessons"] = Lesson.objects.filter(
            teacher=user.teacher_profile
        ).count()

    return Response(data_summary)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_privacy_settings(request):
    """
    Allow users to control their privacy settings
    """
    user = request.user

    # Initialize preferences if needed
    if not user.preferences:
        user.preferences = {}

    # Update privacy settings
    privacy_settings = request.data.get("privacy", {})

    allowed_settings = {
        "show_profile_picture": bool,
        "show_instrument": bool,
        "allow_student_messaging": bool,
        "show_in_directory": bool,
        "receive_marketing_emails": bool,
        "data_sharing_analytics": bool,
    }

    # Validate and save settings
    user.preferences["privacy"] = user.preferences.get("privacy", {})

    for key, value in privacy_settings.items():
        if key in allowed_settings:
            expected_type = allowed_settings[key]
            if isinstance(value, expected_type):
                user.preferences["privacy"][key] = value

    user.save()

    return Response(
        {
            "message": "Privacy settings updated successfully",
            "settings": user.preferences.get("privacy", {}),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def record_consent(request):
    """
    GDPR Article 7: Record user consent for data processing
    """
    user = request.user
    consent_type = request.data.get("consent_type")
    consent_given = request.data.get("consent", False)

    valid_consent_types = [
        "terms_of_service",
        "privacy_policy",
        "marketing_communications",
        "data_analytics",
        "third_party_sharing",
    ]

    if consent_type not in valid_consent_types:
        return Response(
            {"error": "Invalid consent type", "valid_types": valid_consent_types},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Initialize consent record
    if not user.preferences:
        user.preferences = {}
    if "consents" not in user.preferences:
        user.preferences["consents"] = {}

    # Record consent
    user.preferences["consents"][consent_type] = {
        "granted": consent_given,
        "timestamp": timezone.now().isoformat(),
        "ip_address": request.META.get("REMOTE_ADDR"),
        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:200],
    }

    user.save()

    return Response(
        {
            "message": f"Consent for {consent_type} recorded",
            "consent": user.preferences["consents"][consent_type],
        }
    )
