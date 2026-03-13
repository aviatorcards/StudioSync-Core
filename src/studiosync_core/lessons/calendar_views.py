"""
Calendar feed views
"""

from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from studiosync_core.core.models import Student, Studio, Teacher

from .calendar_utils import (
    generate_student_calendar,
    generate_studio_calendar,
    generate_teacher_calendar,
)


@api_view(["GET"])
def teacher_calendar_feed(request, teacher_id):
    """
    Generate ICS calendar feed for a teacher's lessons
    URL: /api/calendar/teacher/{teacher_id}/lessons.ics
    """
    teacher = get_object_or_404(Teacher, id=teacher_id)

    # Generate calendar
    ical_data = generate_teacher_calendar(teacher)

    # Return as downloadable file
    response = HttpResponse(ical_data, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="teacher-{teacher.id}-lessons.ics"'
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"

    return response


@api_view(["GET"])
def student_calendar_feed(request, student_id):
    """
    Generate ICS calendar feed for a student's lessons
    URL: /api/calendar/student/{student_id}/lessons.ics
    """
    student = get_object_or_404(Student, id=student_id)

    # Generate calendar
    ical_data = generate_student_calendar(student)

    # Return as downloadable file
    response = HttpResponse(ical_data, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="student-{student.id}-lessons.ics"'
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"

    return response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def studio_calendar_feed(request, studio_id):
    """
    Generate ICS calendar feed for all studio lessons
    URL: /api/calendar/studio/{studio_id}/lessons.ics
    Requires authentication
    """
    studio = get_object_or_404(Studio, id=studio_id)

    # Check permission (user must be studio owner or staff)
    if request.user != studio.owner and not request.user.is_staff:
        return Response({"error": "Permission denied"}, status=403)

    # Generate calendar
    ical_data = generate_studio_calendar(studio)

    # Return as downloadable file
    response = HttpResponse(ical_data, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="studio-{studio.id}-lessons.ics"'
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"

    return response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_calendar_feed(request):
    """
    Generate calendar feed for the current user
    Automatically detects if user is a teacher or student
    URL: /api/calendar/my/lessons.ics
    """
    # Check if user is a teacher
    if hasattr(request.user, "teacher_profile"):
        teacher = request.user.teacher_profile
        ical_data = generate_teacher_calendar(teacher)
        filename = "my-lessons.ics"
    # Check if user is a student
    elif hasattr(request.user, "student_profile"):
        student = request.user.student_profile
        ical_data = generate_student_calendar(student)
        filename = "my-lessons.ics"
    else:
        return Response({"error": "User is neither a teacher nor a student"}, status=400)

    # Return as downloadable file
    response = HttpResponse(ical_data, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"

    return response
