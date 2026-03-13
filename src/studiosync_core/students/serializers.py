from django.utils import timezone

from rest_framework import serializers

from studiosync_core.core.models import Student, User


class StudentListSerializer(serializers.ModelSerializer):
    """Serializer for listing students"""

    name = serializers.SerializerMethodField()
    email = serializers.EmailField(source="user.email", read_only=True)
    teacher_name = serializers.CharField(
        source="primary_teacher.user.get_full_name", read_only=True, allow_null=True
    )
    status = serializers.SerializerMethodField()
    next_lesson = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            "id",
            "name",
            "email",
            "instrument",
            "teacher_name",
            "primary_teacher",
            "status",
            "next_lesson",
            "is_active",
        ]

    def get_name(self, obj):
        return obj.user.get_full_name()

    def get_status(self, obj):
        return "active" if obj.is_active else "inactive"

    def get_next_lesson(self, obj):
        # This might be N+1 if not careful, but okay for MVP with small lists
        from studiosync_core.lessons.models import Lesson

        next_l = (
            Lesson.objects.filter(
                student=obj, status="scheduled", scheduled_start__gte=timezone.now()
            )
            .order_by("scheduled_start")
            .first()
        )

        if next_l:
            return next_l.scheduled_start
        return None


class StudentDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single student"""

    name = serializers.CharField(source="user.get_full_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)
    avatar = serializers.SerializerMethodField()
    teacher = serializers.SerializerMethodField()
    family_name = serializers.CharField(
        source="family.primary_parent.last_name", read_only=True, allow_null=True
    )

    class Meta:
        model = Student
        fields = "__all__"

    def get_avatar(self, obj):
        if obj.user.avatar:
            return obj.user.avatar.url
        return None

    def get_teacher(self, obj):
        if obj.primary_teacher:
            return {
                "id": str(obj.primary_teacher.id),
                "name": obj.primary_teacher.user.get_full_name(),
            }
        return None


class StudentCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating students with nested user data"""

    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    phone = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Student
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "instrument",
            "family",
            "studio",
            "birth_date",
            "emergency_contact_name",
            "emergency_contact_phone",
            "primary_teacher",
            "is_active",
        ]
        read_only_fields = ["studio"]

    def create(self, validated_data):
        user_data = {
            "first_name": validated_data.pop("first_name"),
            "last_name": validated_data.pop("last_name"),
            "email": validated_data.pop("email"),
            "phone": validated_data.pop("phone", ""),
            "role": "student",
            "is_active": True,
        }

        # Check if user exists (by email) -> Logical decision: for now fail if exists, or link?
        # MVP: Fail if exists to avoid account hijacking.
        if User.objects.filter(email=user_data["email"]).exists():
            raise serializers.ValidationError({"email": "User with this email already exists."})

        user = User.objects.create_user(**user_data)

        # Get studio context from view
        if "studio" not in validated_data:
            # This relies on perform_create in view to pass studio or defaults
            pass

        # Check if student profile was already created by signal
        if hasattr(user, "student_profile"):
            student = user.student_profile
            # Update with validated data
            for key, value in validated_data.items():
                setattr(student, key, value)
            student.save()
        else:
            student = Student.objects.create(user=user, **validated_data)

        return student

    def update(self, instance, validated_data):
        # Handle user updates if provided
        user = instance.user
        if "first_name" in validated_data:
            user.first_name = validated_data.pop("first_name")
        if "last_name" in validated_data:
            user.last_name = validated_data.pop("last_name")
        if "phone" in validated_data:
            user.phone = validated_data.pop("phone")
        if "email" in validated_data:
            # Email update logic is sensitive, maybe skip for now or require re-verification
            # user.email = validated_data.pop('email')
            validated_data.pop("email", None)
        user.save()

        return super().update(instance, validated_data)
