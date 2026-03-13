"""
Calendar integration utilities
Generate ICS feeds for lessons
"""

from datetime import timedelta

from django.utils import timezone

from icalendar import Calendar, Event

from studiosync_core.lessons.models import Lesson


def generate_teacher_calendar(teacher):
    """
    Generate ICS calendar feed for a teacher's lessons
    """
    calendar = Calendar()
    calendar.add("prodid", "-//Music Studio Manager//Teacher Calendar//EN")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("method", "PUBLISH")
    calendar.add("x-wr-calname", f"{teacher.user.get_full_name()} - Lessons")
    calendar.add("x-wr-timezone", "UTC")

    # Get lessons from 1 month ago to 6 months ahead
    start_date = timezone.now() - timedelta(days=30)
    end_date = timezone.now() + timedelta(days=180)

    lessons = Lesson.objects.filter(
        teacher=teacher, scheduled_start__gte=start_date, scheduled_start__lte=end_date
    ).exclude(status="cancelled")

    for lesson in lessons:
        event = Event()

        # Basic info
        event.add(
            "summary", f"🎵 {lesson.student.user.get_full_name()} - {lesson.student.instrument}"
        )
        event.add("dtstart", lesson.scheduled_start)
        event.add("dtend", lesson.scheduled_end)
        event.add("dtstamp", timezone.now())

        # Location
        if lesson.lesson_type == "online":
            event.add("location", "Online Lesson")
        else:
            event.add("location", lesson.location or "Studio")

        # Description
        description_parts = [
            f"Student: {lesson.student.user.get_full_name()}",
            f"Instrument: {lesson.student.instrument}",
            f"Type: {lesson.get_lesson_type_display()}",
        ]
        if lesson.notes:
            description_parts.append(f"\\nNotes: {lesson.notes}")

        event.add("description", "\\n".join(description_parts))

        # Unique ID
        event.add("uid", f"lesson-{lesson.id}@musicstudio.local")

        # Status
        if lesson.status == "completed":
            event.add("status", "CONFIRMED")
        elif lesson.status == "scheduled":
            event.add("status", "CONFIRMED")
        else:
            event.add("status", "TENTATIVE")

        calendar.add_component(event)

    return calendar.to_ical()


def generate_student_calendar(student):
    """
    Generate ICS calendar feed for a student's lessons
    """
    calendar = Calendar()
    calendar.add("prodid", "-//Music Studio Manager//Student Calendar//EN")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("method", "PUBLISH")
    calendar.add("x-wr-calname", f"{student.user.get_full_name()} - Lessons")
    calendar.add("x-wr-timezone", "UTC")

    # Get lessons from 1 month ago to 6 months ahead
    start_date = timezone.now() - timedelta(days=30)
    end_date = timezone.now() + timedelta(days=180)

    lessons = Lesson.objects.filter(
        student=student, scheduled_start__gte=start_date, scheduled_start__lte=end_date
    ).exclude(status="cancelled")

    for lesson in lessons:
        event = Event()

        # Basic info
        event.add(
            "summary", f"🎹 {student.instrument} Lesson with {lesson.teacher.user.get_full_name()}"
        )
        event.add("dtstart", lesson.scheduled_start)
        event.add("dtend", lesson.scheduled_end)
        event.add("dtstamp", timezone.now())

        # Location
        if lesson.lesson_type == "online":
            event.add("location", "Online Lesson")
        else:
            event.add("location", lesson.location or "Studio")

        # Description
        description_parts = [
            f"Teacher: {lesson.teacher.user.get_full_name()}",
            f"Instrument: {student.instrument}",
            f"Type: {lesson.get_lesson_type_display()}",
        ]

        event.add("description", "\\n".join(description_parts))

        # Unique ID
        event.add("uid", f"lesson-{lesson.id}@musicstudio.local")

        # Reminder (15 minutes before)
        from icalendar import Alarm

        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", "Lesson starts in 15 minutes")
        alarm.add("trigger", timedelta(minutes=-15))
        event.add_component(alarm)

        calendar.add_component(event)

    return calendar.to_ical()


def generate_studio_calendar(studio):
    """
    Generate ICS calendar feed for all studio lessons
    """
    calendar = Calendar()
    calendar.add("prodid", "-//Music Studio Manager//Studio Calendar//EN")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("method", "PUBLISH")
    calendar.add("x-wr-calname", f"{studio.name} - All Lessons")
    calendar.add("x-wr-timezone", "UTC")

    # Get lessons from 1 month ago to 6 months ahead
    start_date = timezone.now() - timedelta(days=30)
    end_date = timezone.now() + timedelta(days=180)

    lessons = (
        Lesson.objects.filter(
            teacher__studio=studio, scheduled_start__gte=start_date, scheduled_start__lte=end_date
        )
        .exclude(status="cancelled")
        .select_related("teacher__user", "student__user", "student")
    )

    for lesson in lessons:
        event = Event()

        # Basic info
        event.add(
            "summary",
            f"{lesson.teacher.user.get_full_name()} → {lesson.student.user.get_full_name()}",
        )
        event.add("dtstart", lesson.scheduled_start)
        event.add("dtend", lesson.scheduled_end)
        event.add("dtstamp", timezone.now())

        # Location
        if lesson.lesson_type == "online":
            event.add("location", "Online")
        else:
            event.add("location", lesson.location or "Studio")

        # Description
        description_parts = [
            f"Teacher: {lesson.teacher.user.get_full_name()}",
            f"Student: {lesson.student.user.get_full_name()}",
            f"Instrument: {lesson.student.instrument}",
        ]

        event.add("description", "\\n".join(description_parts))
        event.add("uid", f"lesson-{lesson.id}@musicstudio.local")

        calendar.add_component(event)

    return calendar.to_ical()
