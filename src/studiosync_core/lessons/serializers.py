"""
Lesson API serializers
"""

from rest_framework import serializers

from studiosync_core.lessons.models import Lesson, LessonNote, LessonPlan, RecurringPattern, StudentGoal


class LessonListSerializer(serializers.ModelSerializer):
    """Simple serializer for lesson lists"""

    student_name = serializers.CharField(source="student.user.get_full_name", read_only=True)
    teacher_name = serializers.CharField(source="teacher.user.get_full_name", read_only=True)
    student_instrument = serializers.CharField(source="student.instrument", read_only=True)
    band_name = serializers.CharField(source="band.name", read_only=True)
    room_name = serializers.CharField(source="room.name", read_only=True)
    lesson_plan_title = serializers.CharField(source="lesson_plan.title", read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)
    student_profile_id = serializers.SerializerMethodField()

    def get_student_profile_id(self, obj):
        """Return the student profile UUID as a plain string for frontend matching."""
        if obj.student:
            return str(obj.student.id)
        return None

    class Meta:
        model = Lesson
        fields = [
            "id",
            "student",
            "student_name",
            "student_profile_id",
            "teacher",
            "teacher_name",
            "student_instrument",
            "band",
            "band_name",
            "room",
            "room_name",
            "lesson_type",
            "status",
            "scheduled_start",
            "scheduled_end",
            "duration_minutes",
            "location",
            "is_online",
            "online_meeting_url",
            "summary",
            "is_paid",
            "lesson_plan",
            "lesson_plan_title",
        ]


class LessonDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single lesson view"""

    student = serializers.SerializerMethodField()
    teacher = serializers.SerializerMethodField()
    band = serializers.SerializerMethodField()
    room = serializers.SerializerMethodField()
    duration_minutes = serializers.IntegerField(read_only=True)

    class Meta:
        model = Lesson
        fields = "__all__"

    def get_student(self, obj):
        if not obj.student:
            return None
        return {
            "id": str(obj.student.id),
            "name": obj.student.user.get_full_name(),
            "instrument": obj.student.instrument,
        }

    def get_teacher(self, obj):
        return {
            "id": str(obj.teacher.id),
            "name": obj.teacher.user.get_full_name(),
        }

    def get_band(self, obj):
        if not obj.band:
            return None
        return {
            "id": str(obj.band.id),
            "name": obj.band.name,
        }

    def get_room(self, obj):
        if not obj.room:
            return None
        return {
            "id": str(obj.room.id),
            "name": obj.room.name,
        }


class LessonCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating lessons"""

    class Meta:
        model = Lesson
        fields = [
            "studio",
            "teacher",
            "student",
            "band",
            "room",
            "lesson_type",
            "status",
            "scheduled_start",
            "scheduled_end",
            "location",
            "is_online",
            "online_meeting_url",
            "rate",
            "summary",
            "lesson_plan",
        ]

    def validate(self, data):
        """Ensure either student, band, or room is provided"""
        if not data.get("student") and not data.get("band") and not data.get("room"):
            raise serializers.ValidationError(
                "Either a student, band, or room must be selected for the lesson."
            )
        return data


class StudentGoalSerializer(serializers.ModelSerializer):
    """Serializer for student goals"""

    student_name = serializers.ReadOnlyField(source="student.user.get_full_name")

    class Meta:
        model = StudentGoal
        fields = [
            "id",
            "student",
            "student_name",
            "teacher",
            "title",
            "description",
            "status",
            "target_date",
            "achieved_date",
            "progress_percentage",
            "created_at",
        ]
        read_only_fields = ["teacher", "created_at"]
        extra_kwargs = {"student": {"required": False}}

    def create(self, validated_data):
        # Auto-assign teacher and student based on role
        request = self.context.get("request")
        user = request.user

        if hasattr(user, "teacher_profile"):
            validated_data["teacher"] = user.teacher_profile
            if "student" not in validated_data:
                raise serializers.ValidationError({"student": "Student is required."})

        elif hasattr(user, "student_profile"):
            validated_data["student"] = user.student_profile

        return super().create(validated_data)


class LessonPlanSerializer(serializers.ModelSerializer):
    """Serializer for lesson plans"""

    created_by_name = serializers.ReadOnlyField(source="created_by.user.get_full_name")
    resource_ids = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False
    )

    class Meta:
        model = LessonPlan
        fields = [
            "id",
            "title",
            "description",
            "content",
            "estimated_duration_minutes",
            "tags",
            "is_public",
            "created_by",
            "created_by_name",
            "resources",
            "resource_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_by", "created_at", "updated_at"]
        extra_kwargs = {"resources": {"read_only": True}}

    def create(self, validated_data):
        resource_ids = validated_data.pop("resource_ids", [])
        plan = super().create(validated_data)
        if resource_ids:
            plan.resources.set(resource_ids)
        return plan

    def update(self, instance, validated_data):
        resource_ids = validated_data.pop("resource_ids", None)
        plan = super().update(instance, validated_data)
        if resource_ids is not None:
            plan.resources.set(resource_ids)
        return plan


class LessonNoteSerializer(serializers.ModelSerializer):
    """Serializer for lesson notes"""

    teacher_name = serializers.ReadOnlyField(source="teacher.user.get_full_name")

    class Meta:
        model = LessonNote
        fields = [
            "id",
            "lesson",
            "teacher",
            "teacher_name",
            "content",
            "practice_assignments",
            "homework",
            "pieces_practiced",
            "progress_rating",
            "strengths",
            "areas_for_improvement",
            "attachments",
            "visible_to_student",
            "visible_to_parent",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["teacher", "created_at", "updated_at"]


class RecurringPatternSerializer(serializers.ModelSerializer):
    """Serializer for recurring lesson patterns"""

    teacher_name = serializers.ReadOnlyField(source="teacher.user.get_full_name")
    student_name = serializers.ReadOnlyField(source="student.user.get_full_name")

    class Meta:
        model = RecurringPattern
        fields = [
            "id",
            "teacher",
            "teacher_name",
            "student",
            "student_name",
            "frequency",
            "day_of_week",
            "time",
            "duration_minutes",
            "start_date",
            "end_date",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, data):
        """Validate that end_date is after start_date"""
        if data.get("end_date") and data.get("start_date"):
            if data["end_date"] < data["start_date"]:
                raise serializers.ValidationError({"end_date": "End date must be after start date"})
        return data


class ExternalCalendarFeedSerializer(serializers.ModelSerializer):
    """Serializer for external iCal feed subscriptions"""

    # Use CharField so we can normalise webcal:// before URL validation
    url = serializers.CharField(max_length=2000)
    event_count = serializers.SerializerMethodField()

    def get_event_count(self, obj):
        return obj.events.count()

    class Meta:
        from studiosync_core.lessons.models import ExternalCalendarFeed

        model = ExternalCalendarFeed
        fields = [
            "id",
            "name",
            "url",
            "color",
            "is_enabled",
            "last_synced_at",
            "last_error",
            "event_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["last_synced_at", "last_error", "created_at", "updated_at"]

    def validate_url(self, value):
        """Normalise webcal:// → https:// then validate as a URL."""
        from django.core.validators import URLValidator
        from django.core.exceptions import ValidationError as DjangoValidationError

        if value.startswith("webcal://"):
            value = "https://" + value[len("webcal://"):]

        validator = URLValidator(schemes=["http", "https"])
        try:
            validator(value)
        except DjangoValidationError:
            raise serializers.ValidationError("Enter a valid iCal feed URL (http or https).")

        return value


class ExternalCalendarEventSerializer(serializers.ModelSerializer):
    """Read-only serializer for cached external calendar events"""

    feed_name = serializers.CharField(source="feed.name", read_only=True)
    feed_color = serializers.CharField(source="feed.color", read_only=True)

    class Meta:
        from studiosync_core.lessons.models import ExternalCalendarEvent

        model = ExternalCalendarEvent
        fields = [
            "id",
            "feed",
            "feed_name",
            "feed_color",
            "uid",
            "title",
            "description",
            "location",
            "start_dt",
            "end_dt",
        ]
        read_only_fields = fields
