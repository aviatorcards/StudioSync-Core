from django.db import models

from rest_framework import filters, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from studiosync_core.core.models import Family, Student
from studiosync_core.students.serializers import (
    StudentCreateUpdateSerializer,
    StudentDetailSerializer,
    StudentListSerializer,
)
from studiosync_core.students.serializers_family import FamilySerializer


class StudentViewSet(viewsets.ModelViewSet):
    """
    API endpoints for managing students
    """

    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["user__first_name", "user__last_name", "instrument"]
    ordering_fields = ["user__last_name", "enrollment_date"]
    ordering = ["user__last_name"]

    def get_serializer_class(self):
        if self.action == "list":
            return StudentListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return StudentCreateUpdateSerializer
        return StudentDetailSerializer

    def get_queryset(self):
        user = self.request.user
        # Only show students whose user role is still 'student' (exclude promoted users)
        queryset = Student.objects.select_related("user", "primary_teacher__user", "family").filter(
            user__role="student"
        )

        # Admin can see everything
        if user.role == "admin":
            return queryset

        # Teachers can see their own students
        if hasattr(user, "teacher_profile"):
            return queryset.filter(primary_teacher=user.teacher_profile)

        # Students can only see themselves and their band members
        if hasattr(user, "student_profile"):
            student_profile = user.student_profile
            user_bands = student_profile.bands.all()
            if user_bands.exists():
                return queryset.filter(
                    models.Q(id=student_profile.id) | models.Q(bands__in=user_bands)
                ).distinct()
            return queryset.filter(id=student_profile.id)

        # Fallback
        return queryset.none()

    @action(detail=False, methods=["get"], url_path="instruments")
    def instruments(self, request):
        """Return sorted unique instrument list: studio curated list + instruments used by existing students."""
        from studiosync_core.core.models import Studio

        # 1. Instruments already assigned to students
        student_instruments = (
            self.get_queryset()
            .exclude(instrument="")
            .exclude(instrument__isnull=True)
            .values_list("instrument", flat=True)
            .distinct()
        )

        # 2. Curated list stored in studio settings
        curated: list = []
        studio = Studio.objects.filter(owner=request.user).first()
        if not studio:
            studio = Studio.objects.first()
        if studio and isinstance(studio.settings, dict):
            curated = studio.settings.get("instruments", [])

        merged = sorted(
            {i.strip().title() for i in list(student_instruments) + curated if i and i.strip()}
        )
        return Response(merged)

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """Return aggregate stats for the students the current user can access."""
        qs = self.get_queryset()
        total = qs.count()
        active = qs.filter(is_active=True).count()
        unassigned = qs.filter(primary_teacher__isnull=True).count()
        return Response(
            {
                "total_students": total,
                "active_students": active,
                "unassigned_students": unassigned,
            }
        )

    def perform_create(self, serializer):
        # Automatically assign the studio from the admin's owned studio
        # For MVP, we'll use the first studio or admin's owned studio
        from studiosync_core.core.models import Studio

        user = self.request.user
        if user.role == "admin":
            studio = Studio.objects.filter(owner=user).first()
            if not studio:
                studio = Studio.objects.first()  # Fallback to any studio
            if studio:
                serializer.save(studio=studio)
            else:
                serializer.save()  # Will fail if studio is required
        else:
            serializer.save()


class FamilyViewSet(viewsets.ModelViewSet):
    """
    API endpoints for managing families
    """

    permission_classes = [permissions.IsAuthenticated]  # Adjust permissions as needed (Admin only?)
    serializer_class = FamilySerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["primary_parent__last_name", "primary_parent__email"]

    def get_queryset(self):
        return Family.objects.select_related("primary_parent", "secondary_parent").prefetch_related(
            "students__user"
        )
