from django.db.models import Q

from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from .models import Invoice, SubscriptionPlan, Subscription
from .serializers import InvoiceSerializer, SubscriptionPlanSerializer, SubscriptionSerializer


class InvoiceViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing invoices
    """

    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        # Admin: See all invoices for their owned studios
        if user.role == "admin":
            return Invoice.objects.filter(studio__owner=user)

        # Teachers: See all invoices for their studio
        if user.role == "teacher" and hasattr(user, "teacher_profile"):
            return Invoice.objects.filter(studio=user.teacher_profile.studio)

        # Students: See their own invoices (direct or via band)
        if hasattr(user, "student_profile"):
            student = user.student_profile
            return Invoice.objects.filter(
                Q(student=student) | Q(band__in=student.bands.all())
            ).distinct()

        # Parents: See invoices for their families? (Future scope)
        if hasattr(user, "primary_parent_families"):
            # Basic support for parents
            return Invoice.objects.filter(student__family__primary_parent=user).distinct()

        return Invoice.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        
        if user.role != "admin":
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only admins can create invoices.")

        from studiosync_core.core.models import Studio
        studio = Studio.objects.filter(owner=user).first()
        
        if studio:
            serializer.save(studio=studio)
        else:
            # Fallback for demo/dev
            studio = Studio.objects.first()
            if studio:
                serializer.save(studio=studio)
            else:
                raise serializer.ValidationError("No studio found to associate with this invoice.")

    def update(self, request, *args, **kwargs):
        if request.user.role != "admin":
            return Response(
                {"detail": "Only admins can update invoices."}, status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if request.user.role != "admin":
            return Response(
                {"detail": "Only admins can update invoices."}, status=status.HTTP_403_FORBIDDEN
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if request.user.role != "admin":
            return Response(
                {"detail": "Only admins can delete invoices."}, status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)

class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == "admin":
            return SubscriptionPlan.objects.filter(studio__owner=user)
        elif user.role == "teacher" and hasattr(user, "teacher_profile"):
            return SubscriptionPlan.objects.filter(studio=user.teacher_profile.studio)
        elif hasattr(user, "student_profile"):
            return SubscriptionPlan.objects.filter(studio=user.student_profile.studio, is_active=True)
        return SubscriptionPlan.objects.none()

    def perform_create(self, serializer):
        if self.request.user.role != "admin":
            raise permissions.PermissionDenied("Only admins can create subscription plans.")
        from studiosync_core.core.models import Studio
        studio = Studio.objects.filter(owner=self.request.user).first()
        if studio:
            serializer.save(studio=studio)
        else:
            serializer.save(studio=Studio.objects.first())

    def update(self, request, *args, **kwargs):
        if request.user.role != "admin":
            raise permissions.PermissionDenied("Only admins can update subscription plans.")
        return super().update(request, *args, **kwargs)


class SubscriptionViewSet(viewsets.ModelViewSet):
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == "admin":
            return Subscription.objects.filter(studio__owner=user)
        if user.role == "teacher" and hasattr(user, "teacher_profile"):
            return Subscription.objects.filter(studio=user.teacher_profile.studio)
        if hasattr(user, "student_profile"):
            return Subscription.objects.filter(student=user.student_profile)
        return Subscription.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.role not in ["admin", "student"]:
            raise permissions.PermissionDenied("Only admins or students can create subscriptions.")
            
        from studiosync_core.core.models import Studio
        studio = Studio.objects.filter(owner=self.request.user).first() if user.role == "admin" else getattr(getattr(user, "student_profile", None), "studio", None)
        if not studio:
            studio = Studio.objects.first()
        serializer.save(studio=studio)

