from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from studiosync_core.core.serializers import UserSerializer

User = get_user_model()


class MeView(APIView):
    """
    Returns the current authenticated user's details.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class RegisterView(APIView):
    """
    Public registration endpoint - creates users with 'student' role by default
    Admin must manually upgrade to teacher/admin via admin panel
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")
        first_name = request.data.get("first_name")
        last_name = request.data.get("last_name")

        # Validation
        if not all([email, password, first_name, last_name]):
            return Response(
                {"error": "Email, password, first name, and last name are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if user exists
        if User.objects.filter(email=email).exists():
            return Response(
                {"error": "A user with this email already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Restriction: Users cannot self-promote to 'teacher' or 'admin'
        actual_role = "student"
        requested_role = request.data.get("role", "student")

        # If they requested teacher/admin, we set them to student but notify admins
        needs_approval = requested_role in ["teacher", "admin"]
        if requested_role in ["student", "parent"]:
            actual_role = requested_role

        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=actual_role,
            is_active=True,
            is_approved=False,
        )

        # Notify student and admins
        from studiosync_core.core.email_utils import (
            send_admin_approval_notification,
            send_registration_pending_email,
        )
        from studiosync_core.notifications.models import Notification

        send_registration_pending_email(email, first_name)
        send_admin_approval_notification(user)
        Notification.notify_admin_new_student_registration(user)

        if needs_approval:
            try:
                Notification.notify_admin_instructor_request(user)
            except Exception:
                pass

        serializer = UserSerializer(user)
        return Response(
            {
                "message": "Account created successfully. Your account is pending approval. You will receive an email once an instructor or admin has approved your access.",
                "user": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email=email).first()
        if user:
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_link = f"{settings.FRONTEND_BASE_URL}/reset-password?uid={uid}&token={token}"

            send_mail(
                "Password Reset Request",
                f"Click the link to reset your password: {reset_link}",
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )

        # Always return success to prevent email enumeration
        return Response(
            {"message": "If an account exists with this email, a reset link has been sent."}
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        uidb64 = request.data.get("uid")
        token = request.data.get("token")
        password = request.data.get("password")

        if not all([uidb64, token, password]):
            return Response({"error": "Missing fields"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({"error": "Invalid link"}, status=status.HTTP_400_BAD_REQUEST)

        if default_token_generator.check_token(user, token):
            user.set_password(password)
            user.save()
            return Response({"message": "Password has been reset successfully."})

        return Response({"error": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST)
