"""
Lesson models - Lesson, LessonNote, RecurringPattern
"""

import uuid

from django.db import models

from studiosync_core.core.models import Student, Studio, Teacher


class RecurringPattern(models.Model):
    """
    Defines recurring lesson schedules (weekly, bi-weekly, etc.)
    """

    FREQUENCY_CHOICES = [
        ("weekly", "Weekly"),
        ("biweekly", "Bi-weekly"),
        ("monthly", "Monthly"),
    ]

    DAY_CHOICES = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name="recurring_patterns"
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="recurring_patterns"
    )

    # Pattern details
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default="weekly")
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    time = models.TimeField()
    duration_minutes = models.IntegerField(default=60)

    # Date range
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)  # Null means ongoing

    # Flags
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "recurring_patterns"
        ordering = ["day_of_week", "time"]

    def __str__(self):
        return f"{self.get_frequency_display()} - {self.student.user.get_full_name()} with {self.teacher.user.get_full_name()}"


class Lesson(models.Model):
    """
    Individual lesson instance
    """

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("no_show", "No Show"),
    ]

    LESSON_TYPE_CHOICES = [
        ("private", "Private Lesson"),
        ("group", "Group Lesson"),
        ("workshop", "Workshop"),
        ("recital", "Recital"),
        ("makeup", "Makeup Lesson"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    studio = models.ForeignKey(Studio, on_delete=models.CASCADE, related_name="lessons")
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="lessons")
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="lessons", null=True, blank=True
    )
    band = models.ForeignKey(
        "core.Band", on_delete=models.CASCADE, related_name="lessons", null=True, blank=True
    )
    room = models.ForeignKey(
        "inventory.PracticeRoom",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lessons",
    )

    # Lesson details
    lesson_type = models.CharField(max_length=20, choices=LESSON_TYPE_CHOICES, default="private")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")

    # Scheduling
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)

    # Recurring reference
    recurring_pattern = models.ForeignKey(
        RecurringPattern, on_delete=models.SET_NULL, null=True, blank=True, related_name="lessons"
    )

    # Lesson plan template reference
    lesson_plan = models.ForeignKey(
        "LessonPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lessons",
        help_text="Optional lesson plan template used for this lesson",
    )

    # Location
    location = models.CharField(max_length=200, blank=True)
    is_online = models.BooleanField(default=False)
    online_meeting_url = models.URLField(blank=True)

    # Billing
    rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_paid = models.BooleanField(default=False)

    # Notes (summary)
    summary = models.TextField(blank=True)

    # Cancellation
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cancelled_lessons",
    )
    cancellation_reason = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lessons"
        ordering = ["-scheduled_start"]
        indexes = [
            models.Index(fields=["scheduled_start"]),
            models.Index(fields=["teacher", "scheduled_start"]),
            models.Index(fields=["student", "scheduled_start"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        subject = (
            self.student.user.get_full_name()
            if self.student
            else (self.band.name if self.band else "Unknown")
        )
        return f"{subject} - {self.scheduled_start.strftime('%Y-%m-%d %H:%M')}"

    @property
    def duration_minutes(self):
        """Calculate lesson duration in minutes"""
        delta = self.scheduled_end - self.scheduled_start
        return int(delta.total_seconds() / 60)


class LessonNote(models.Model):
    """
    Detailed notes for a lesson with practice assignments
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.OneToOneField(Lesson, on_delete=models.CASCADE, related_name="note")
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="lesson_notes")

    # Content
    content = models.TextField()  # Rich text/Markdown
    practice_assignments = models.TextField(blank=True)
    homework = models.TextField(blank=True)

    # Repertoire worked on
    pieces_practiced = models.JSONField(default=list, blank=True)  # List of piece names

    # Progress tracking
    progress_rating = models.IntegerField(
        default=3,
        choices=[(i, str(i)) for i in range(1, 6)],
        help_text="1-5 rating of student progress",
    )
    strengths = models.TextField(blank=True)
    areas_for_improvement = models.TextField(blank=True)

    # Attachments (file paths in S3/MinIO)
    attachments = models.JSONField(default=list, blank=True)

    # Visibility
    visible_to_student = models.BooleanField(default=True)
    visible_to_parent = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lesson_notes"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Note for {self.lesson}"


class StudentGoal(models.Model):
    """
    Individual goals for students
    """

    STATUS_CHOICES = [
        ("active", "Active"),
        ("achieved", "Achieved"),
        ("abandoned", "Abandoned"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="goals")
    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name="student_goals", null=True, blank=True
    )

    # Goal details
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    # Timeline
    target_date = models.DateField(null=True, blank=True)
    achieved_date = models.DateField(null=True, blank=True)

    # Progress
    progress_percentage = models.IntegerField(default=0, help_text="0-100")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "student_goals"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student.user.get_full_name()}: {self.title}"


class LessonPlan(models.Model):
    """
    Reusable lesson plan template with resources
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Relationships
    created_by = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name="created_lesson_plans"
    )
    resources = models.ManyToManyField(
        "resources.Resource", related_name="lesson_plans", blank=True
    )

    # Content
    content = models.TextField(help_text="Markdown content describing the plan structure")

    # Metadata
    estimated_duration_minutes = models.IntegerField(default=30)
    tags = models.JSONField(default=list, blank=True)

    # Visibility
    is_public = models.BooleanField(default=False)  # Visible to other teachers in studio

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lesson_plans"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class ExternalCalendarFeed(models.Model):
    """
    A user's subscription to an external iCal feed URL.
    Events are fetched and cached in ExternalCalendarEvent.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "core.User",
        on_delete=models.CASCADE,
        related_name="external_calendar_feeds",
    )

    # Display settings
    name = models.CharField(max_length=200, help_text="Display name for this calendar")
    color = models.CharField(
        max_length=7,
        default="#6366f1",
        help_text="Hex color code for the calendar overlay (e.g. #6366f1)",
    )
    is_enabled = models.BooleanField(
        default=True, help_text="When disabled, events are hidden from the schedule"
    )

    # The iCal feed URL (webcal:// will be stored as https://)
    url = models.URLField(max_length=2000, help_text="iCal (.ics) feed URL")

    # Sync metadata
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(
        blank=True, help_text="Last fetch error message, if any"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "external_calendar_feeds"
        ordering = ["name"]

    def __str__(self):
        return f"{self.user.email} — {self.name}"


class ExternalCalendarEvent(models.Model):
    """
    A single event fetched and cached from an ExternalCalendarFeed.
    Deduplicated by (feed, uid) — the iCal UID field.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    feed = models.ForeignKey(
        ExternalCalendarFeed,
        on_delete=models.CASCADE,
        related_name="events",
    )

    # iCal UID — used for deduplication on re-sync
    uid = models.CharField(max_length=500)

    # Event fields
    title = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=500, blank=True)
    start_dt = models.DateTimeField()
    end_dt = models.DateTimeField()

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "external_calendar_events"
        ordering = ["start_dt"]
        unique_together = [("feed", "uid")]
        indexes = [
            models.Index(fields=["feed", "start_dt"]),
            models.Index(fields=["start_dt", "end_dt"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.start_dt:%Y-%m-%d %H:%M})"
