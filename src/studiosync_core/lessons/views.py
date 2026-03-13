"""
Lesson API views
"""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from rest_framework import filters, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from studiosync_core.lessons.models import Lesson, LessonPlan, StudentGoal
from studiosync_core.lessons.serializers import (
    LessonCreateSerializer,
    LessonDetailSerializer,
    LessonListSerializer,
    LessonPlanSerializer,
    StudentGoalSerializer,
)


class LessonViewSet(viewsets.ModelViewSet):
    """
    API endpoints for lessons
    """

    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "teacher__user__first_name",
    ]
    ordering_fields = ["scheduled_start", "created_at"]
    ordering = ["scheduled_start"]

    def get_serializer_class(self):
        if self.action == "list":
            return LessonListSerializer
        elif self.action in ["create", "update", "partial_update"]:
            return LessonCreateSerializer
        return LessonDetailSerializer

    def get_queryset(self):
        """
        Role-based privacy filtering:
        - Students: See ONLY their own lessons
        - Teachers: See ONLY their own students' lessons
        - Admins: See all lessons
        """
        user = self.request.user
        # Default to full queryset
        queryset = Lesson.objects.select_related("student__user", "teacher__user", "studio")

        # Admin sees everything
        if user.role == "admin":
            pass  # No filtering for admins

        # Teachers see only their own students
        elif user.role == "teacher" and hasattr(user, "teacher_profile"):
            queryset = queryset.filter(teacher=user.teacher_profile)

        # Students see only their own lessons
        elif user.role == "student" and hasattr(user, "student_profile"):
            queryset = queryset.filter(student=user.student_profile)

        # Fallback: If role unclear, show nothing (maximum privacy)
        else:
            queryset = Lesson.objects.none()

        # Date range filtering (same for all roles)
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")

        if start_date:
            queryset = queryset.filter(scheduled_start__gte=start_date)
        if end_date:
            queryset = queryset.filter(scheduled_end__lte=end_date)

        # Status filtering (same for all roles)
        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)

        return queryset

    def paginate_queryset(self, queryset):
        """
        Disable pagination when fetching a specific date range for the calendar.
        Calendar views need all events to render correctly.
        """
        if "start_date" in self.request.query_params and "end_date" in self.request.query_params:
            return None
        return super().paginate_queryset(queryset)

    @action(detail=False, methods=["get"])
    def upcoming(self, request):
        """Get upcoming lessons"""
        queryset = (
            self.get_queryset()
            .filter(scheduled_start__gte=timezone.now(), status="scheduled")
            .order_by("scheduled_start")[:10]
        )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def today(self, request):
        """Get today's lessons"""
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        queryset = (
            self.get_queryset()
            .filter(scheduled_start__gte=today_start, scheduled_start__lt=today_end)
            .order_by("scheduled_start")
        )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def week(self, request):
        """Get this week's lessons"""
        today = timezone.now()
        week_start = today - timedelta(days=today.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)

        queryset = (
            self.get_queryset()
            .filter(scheduled_start__gte=week_start, scheduled_start__lt=week_end)
            .order_by("scheduled_start")
        )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        user = self.request.user
        if hasattr(user, "teacher_profile"):
            serializer.save(teacher=user.teacher_profile, studio=user.teacher_profile.studio)
        elif hasattr(user, "student_profile"):
            # allow student to book, forcing themselves as the student
            serializer.save(
                student=user.student_profile,
                studio=user.student_profile.studio,
                # If teacher is not in payload, validation would have failed if required.
                # If it is in payload, it is used.
                # We could default to primary_teacher if we wanted to make it optional in serializer,
                # but for now assume frontend sends it.
            )
        elif user.role == "admin":
            # Admin needs to provide teacher/studio or we try to guess/default?
            # For now, let validation fail if not provided, or default if possible.
            # But the serializer will require them.
            # If admin is creating, they likely send the data.
            serializer.save()
        else:
            # Fallback
            serializer.save()


class LessonPlanViewSet(viewsets.ModelViewSet):
    """
    API endpoints for lesson plans
    """

    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "description", "tags"]
    ordering_fields = ["created_at", "title"]

    def get_serializer_class(self):
        return LessonPlanSerializer

    def get_queryset(self):
        user = self.request.user
        qs = LessonPlan.objects.select_related("created_by__user", "created_by__studio")

        if user.role == "admin":
            # Admin sees all plans in their studio(s)
            from studiosync_core.core.models import Studio

            studios = Studio.objects.filter(owner=user)
            qs = qs.filter(created_by__studio__in=studios)
        elif hasattr(user, "teacher_profile") and user.teacher_profile:
            # Teacher sees: their own plans + public plans from same studio
            studio = user.teacher_profile.studio
            qs = qs.filter(
                Q(created_by=user.teacher_profile) | Q(is_public=True, created_by__studio=studio)
            )
        elif hasattr(user, "student_profile") and user.student_profile:
            # Students see only public plans from their studio
            studio = user.student_profile.studio
            qs = qs.filter(is_public=True, created_by__studio=studio)
        else:
            qs = qs.none()

        return qs

    def perform_create(self, serializer):
        user = self.request.user

        if hasattr(user, "teacher_profile") and user.teacher_profile:
            serializer.save(created_by=user.teacher_profile)
        elif user.role == "admin":
            # Admin can specify teacher_id in request.data.get('created_by')
            teacher_id = self.request.data.get("created_by")
            teacher = None

            if teacher_id:
                from studiosync_core.core.models import Teacher

                try:
                    teacher = Teacher.objects.get(id=teacher_id)
                except (Teacher.DoesNotExist, ValueError):
                    raise serializers.ValidationError(
                        {"created_by": "Teacher with this ID does not exist"}
                    ) from None

            if not teacher:
                # Try to find a sensible default teacher for this admin
                from studiosync_core.core.models import Studio, Teacher

                studio = Studio.objects.filter(owner=user).first()
                if studio:
                    teacher = Teacher.objects.filter(studio=studio).first()

                if not teacher:
                    teacher = Teacher.objects.first()

            if not teacher:
                raise serializers.ValidationError(
                    {
                        "created_by": "No teacher found to assign this lesson plan to. Please create a teacher profile first."
                    }
                )

            serializer.save(created_by=teacher)
        else:
            raise PermissionDenied("Only teachers and admins can create lesson plans")


class StudentGoalViewSet(viewsets.ModelViewSet):
    """
    API endpoints for student goals
    """

    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "student__user__first_name", "student__user__last_name"]
    ordering_fields = ["target_date", "progress_percentage"]

    def get_serializer_class(self):
        return StudentGoalSerializer  # Make sure to import this

    def get_queryset(self):
        user = self.request.user

        if hasattr(user, "teacher_profile") and user.teacher_profile:
            # Teacher: Goals for their students only
            return StudentGoal.objects.filter(teacher=user.teacher_profile)
        elif hasattr(user, "student_profile") and user.student_profile:
            # Student: Their own goals
            return StudentGoal.objects.filter(student=user.student_profile)
        elif user.role == "admin":
            # Admin: Goals for students in their studio(s) only
            from studiosync_core.core.models import Student, Studio

            studios = Studio.objects.filter(owner=user)
            students = Student.objects.filter(studio__in=studios)
            return StudentGoal.objects.filter(student__in=students)
        else:
            return StudentGoal.objects.none()

    def perform_create(self, serializer):
        user = self.request.user

        if hasattr(user, "teacher_profile") and user.teacher_profile:
            # Teacher creating goal for a student
            serializer.save(teacher=user.teacher_profile)
        elif hasattr(user, "student_profile") and user.student_profile:
            # Student creating their own goal
            student = user.student_profile
            # Use primary teacher if available, otherwise require teacher in request
            if hasattr(student, "primary_teacher") and student.primary_teacher:
                serializer.save(student=student, teacher=student.primary_teacher)
            else:
                # Student must have teacher in validated_data
                if "teacher" not in serializer.validated_data:
                    raise serializers.ValidationError(
                        {"teacher": "Teacher must be specified for this goal"}
                    )
                serializer.save(student=student)
        elif user.role == "admin":
            # Admin must specify student
            if "student" not in serializer.validated_data:
                raise serializers.ValidationError({"student": "Admin must specify a student"})

            student = serializer.validated_data.get("student")
            # If teacher is not in validated_data (it's read_only anyway),
            # try to use student's primary teacher.
            teacher = serializer.validated_data.get("teacher")
            if not teacher and student and hasattr(student, "primary_teacher"):
                teacher = student.primary_teacher

            serializer.save(teacher=teacher)
        else:
            raise PermissionDenied("You don't have permission to create goals")
