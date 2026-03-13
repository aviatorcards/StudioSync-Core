import csv

from django.db import models
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404

from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from studiosync_core.core.models import Band, Family, Student, Studio, Teacher, User
from studiosync_core.core.serializers import (
    BandSerializer,
    PublicTeacherSerializer,
    StudentSerializer,
    StudioSerializer,
    TeacherSerializer,
    UserSerializer,
)


class BandViewSet(viewsets.ModelViewSet):
    """API endpoint for managing bands/groups"""

    serializer_class = BandSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Admin sees all, teachers see theirs, students see theirs
        user = self.request.user
        if user.role == "admin":
            return Band.objects.all()
        elif user.role == "teacher" and hasattr(user, "teacher_profile"):
            # This is complex if teachers aren't directly linked to bands
            # For now, allow listing all for choice in UI
            return Band.objects.all()
        elif user.role == "student" and hasattr(user, "student_profile"):
            return user.student_profile.bands.all()
        return Band.objects.none()

    def perform_create(self, serializer):
        # Auto-assign studio to current user's studio
        studio = Studio.objects.filter(owner=self.request.user).first() or Studio.objects.first()
        serializer.save(studio=studio)


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint for users to view/update their own profile
    """

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["email", "first_name", "last_name", "role"]
    ordering_fields = ["created_at", "last_name"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = User.objects.none()

        # Admins can manage everyone
        if self.request.user.role == "admin":
            queryset = User.objects.all()

        # Teachers see their studio members
        elif self.request.user.role == "teacher" and hasattr(self.request.user, "teacher_profile"):
            studio = self.request.user.teacher_profile.studio
            if studio:
                queryset = User.objects.filter(
                    models.Q(teacher_profile__studio=studio)
                    | models.Q(student_profile__studio=studio)
                    | models.Q(id=self.request.user.id)
                ).distinct()

        # Allow listing all users for specific actions (legacy logic, kept for safety)
        elif self.action in ["list", "assign_to_band", "link_family"]:
            queryset = User.objects.all()

        else:
            queryset = User.objects.filter(id=self.request.user.id)

        # Apply Manual Role Filter
        role = self.request.query_params.get("role")
        if role and role != "all":
            queryset = queryset.filter(role=role)

        return queryset

    @action(detail=True, methods=["post"])
    def assign_to_band(self, request, pk=None):
        """Assign a student user to a band"""
        user = self.get_object()
        if user.role != "student" or not hasattr(user, "student_profile"):
            return Response(
                {"detail": "Only students can be assigned to bands"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        band_id = request.data.get("band_id")
        if not band_id:
            return Response(
                {"band_id": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST
            )

        band = get_object_or_404(Band, id=band_id)
        user.student_profile.bands.add(band)

        return Response({"detail": f"Assigned to {band.name}"})

    @action(detail=True, methods=["post"])
    def remove_from_band(self, request, pk=None):
        """Remove a student user from a band"""
        user = self.get_object()
        if user.role != "student" or not hasattr(user, "student_profile"):
            return Response(
                {"detail": "Only students are in bands"}, status=status.HTTP_400_BAD_REQUEST
            )

        band_id = request.data.get("band_id")
        band = get_object_or_404(Band, id=band_id)
        user.student_profile.bands.remove(band)

        return Response({"detail": f"Removed from {band.name}"})

    @action(detail=True, methods=["post"])
    def link_family(self, request, pk=None):
        """Link a parent to a student (creates a Family if needed)"""
        target_user = self.get_object()  # The student
        parent_id = request.data.get("parent_id")

        if not parent_id:
            return Response(
                {"parent_id": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST
            )

        parent = get_object_or_404(User, id=parent_id, role="parent")

        if target_user.role != "student" or not hasattr(target_user, "student_profile"):
            return Response(
                {"detail": "Relationships must target a student profile"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if family already exists for this parent
        family, created = Family.objects.get_or_create(
            primary_parent=parent,
            studio=target_user.student_profile.studio,
            defaults={"billing_email": parent.email},
        )

        target_user.student_profile.family = family
        target_user.student_profile.save()

        return Response({"detail": "Family link created successfully"})

    @action(detail=False, methods=["get", "put", "patch"])
    def me(self, request):
        """Get or update current user"""
        user = request.user
        if request.method == "GET":
            serializer = self.get_serializer(user)
            return Response(serializer.data)

        serializer = self.get_serializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def remove_avatar(self, request):
        """Dedicated action to clear user avatar"""
        user = request.user
        if user.avatar:
            user.avatar = None
            user.save()
        return Response({"detail": "Avatar removed", "avatar": None})

    @action(detail=False, methods=["post"])
    def change_password(self, request):
        """Allow user to change their password"""
        user = request.user
        current_password = request.data.get("current_password")
        new_password = request.data.get("new_password")

        if not current_password or not new_password:
            return Response(
                {"detail": "Both current and new passwords are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.check_password(current_password):
            return Response(
                {"detail": "Current password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.save()
        return Response({"detail": "Password updated successfully."})

    def create(self, request):
        """Create a new user (Admin only)"""
        # Only admins can create users
        if not request.user.role == "admin":
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        email = data.get("email")
        role = data.get("role", "student")
        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")

        if not email:
            return Response(
                {"email": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(email=email).exists():
            return Response(
                {"email": ["User with this email already exists."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create user with a generated temporary password
        from django.utils.crypto import get_random_string
        temp_password = get_random_string(length=12)

        user = User.objects.create_user(
            email=email,
            password=temp_password,
            role=role,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            is_approved=True,  # Users created by admins are approved by default
        )

        try:
            from studiosync_core.core.email_utils import send_welcome_email

            send_welcome_email(user.email, user.first_name, temp_password)
        except Exception as e:
            # Don't fail registration if email fails
            print(f"Failed to trigger welcome email: {e}")

        # Auto-create profile based on role
        try:
            # Find admin's studio (or fallback)
            from studiosync_core.core.models import Student, Studio, Teacher

            studio = Studio.objects.filter(owner=request.user).first()
            if not studio:
                # Fallback to first studio in system (for dev/demo)
                studio = Studio.objects.first()

            if studio:
                if role == "student":
                    Student.objects.create(
                        user=user, studio=studio, instrument="Piano"
                    )  # Default instrument
                elif role == "teacher":
                    Teacher.objects.create(user=user, studio=studio)
        except Exception as e:
            print(f"Error creating profile: {e}")
            # Don't fail the user creation, but log it

        serializer = self.get_serializer(user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def send_test_email(self, request):
        """Send a test email using provided SMTP settings"""
        import traceback

        from django.core.mail import get_connection

        print("=" * 60)
        print("Send Test Email Request Started")

        smtp_host = request.data.get("smtp_host")
        smtp_port = request.data.get("smtp_port")
        smtp_username = request.data.get("smtp_username")
        smtp_password = request.data.get("smtp_password")
        smtp_use_tls = request.data.get("smtp_use_tls", True)
        smtp_from_email = request.data.get("smtp_from_email")
        smtp_from_name = request.data.get("smtp_from_name", "StudioSync")

        print(f"SMTP Host: {smtp_host}")
        print(f"SMTP Port: {smtp_port}")
        print(f"SMTP Username: {smtp_username}")
        print(f"SMTP Password: {'*' * len(smtp_password) if smtp_password else 'None'}")
        print(f"SMTP Use TLS: {smtp_use_tls}")
        print(f"SMTP From Email: {smtp_from_email}")
        print(f"SMTP From Name: {smtp_from_name}")

        if not all([smtp_host, smtp_port, smtp_username, smtp_password, smtp_from_email]):
            print("ERROR: Missing required SMTP configuration")
            return Response(
                {"detail": "Missing SMTP configurations"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Determine security settings
            use_tls = smtp_use_tls
            use_ssl = False

            # Heuristic: Port 465 is usually SSL/TLS (implicit), 587 is STARTTLS
            if str(smtp_port) == "465":
                use_tls = False
                use_ssl = True
                print("Port 465 detected - using SSL mode")
            elif str(smtp_port) == "587":
                use_tls = True
                use_ssl = False
                print("Port 587 detected - using STARTTLS mode")

            print(f"Final security settings: use_tls={use_tls}, use_ssl={use_ssl}")

            # Create a temporary connection with the provided settings
            print("Creating SMTP connection...")
            connection = get_connection(
                backend="django.core.mail.backends.smtp.EmailBackend",
                host=smtp_host,
                port=int(smtp_port),
                username=smtp_username,
                password=smtp_password,
                use_tls=use_tls,
                use_ssl=use_ssl,
                timeout=10,
            )

            # Test connection by opening it
            print("Testing SMTP connection...")
            try:
                connection.open()
                print("✅ SMTP connection successful!")
                connection.close()
            except Exception as conn_error:
                print(f"❌ SMTP connection failed: {conn_error}")
                print(f"Connection error traceback:\n{traceback.format_exc()}")
                return Response(
                    {
                        "detail": f"SMTP connection failed: {str(conn_error)}",
                        "error_type": type(conn_error).__name__,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Use the email utility to send a nice HTML test email
            from django.core.mail import EmailMultiAlternatives

            subject = f"Test Email from {smtp_from_name}"
            text_content = f"""This is a test email from {smtp_from_name}.

If you're receiving this, your email configuration is working correctly!

Best regards,
The {smtp_from_name} Team
"""

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 40px auto;
            padding: 20px;
        }}
        .container {{
            background: white;
            border-radius: 12px;
            padding: 40px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .success {{
            background: #d4edda;
            border: 2px solid #28a745;
            color: #155724;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✅ Test Email Successful!</h1>
        </div>
        <div class="success">
            Your email configuration is working correctly!
        </div>
        <p style="margin-top: 30px; text-align: center; color: #666;">
            This is a test email from <strong>{smtp_from_name}</strong>
        </p>
    </div>
</body>
</html>
"""

            print(f"Sending test email to {request.user.email}...")
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=smtp_from_email,
                to=[request.user.email],
                connection=connection,
            )
            email.attach_alternative(html_content, "text/html")
            email.send()

            print(f"✅ Test email sent successfully to {request.user.email}")
            print("=" * 60)
            return Response({"detail": f"Test email sent successfully to {request.user.email}"})
        except Exception as e:
            # Print stack trace for debugging if needed, but return error to user
            print(f"❌ Failed to send test email: {e}")
            print(f"Error type: {type(e).__name__}")
            print(f"Full traceback:\n{traceback.format_exc()}")
            print("=" * 60)
            return Response(
                {"detail": f"Failed to send email: {str(e)}", "error_type": type(e).__name__},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def list_all(self, request):
        """List all users associated with admin's studio"""
        if request.user.role != "admin":
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        from studiosync_core.core.models import Studio

        studio = Studio.objects.filter(owner=request.user).first()

        # If no studio, just return the user themselves as a fallback or empty list
        if not studio:
            # Fallback: if admin creates users but hasn't set up studio object yet,
            # they should still see users they created?
            # For now, let's just return all users if admin (simple mode)
            # or strictly follow the studio logic.
            # Let's simple return all users for now to unblock 'Add User' visibility
            all_users = User.objects.all()
        else:
            # Get users from all profiles linked to this studio
            # Teachers
            teacher_users = User.objects.filter(teacher_profile__studio=studio)
            # Students
            student_users = User.objects.filter(student_profile__studio=studio)
            # Parents (via Families)
            parent_users = User.objects.filter(
                primary_parent_families__studio=studio
            ) | User.objects.filter(secondary_parent_families__studio=studio)
            all_users = (teacher_users | student_users | parent_users).distinct()

        serializer = self.get_serializer(all_users, many=True)
        return Response(serializer.data)


class StudioViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing studio settings
    Only admins can update studio settings
    """

    serializer_class = StudioSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        # Users can only see studios they own or are associated with
        user = self.request.user

        if not user.is_authenticated:
            return Studio.objects.none()

        if user.role == "admin":
            return Studio.objects.filter(owner=user)
        elif hasattr(user, "teacher_profile") and user.teacher_profile:
            # Teachers see their studio (read-only via permissions)
            return Studio.objects.filter(id=user.teacher_profile.studio.id)
        elif hasattr(user, "student_profile") and user.student_profile:
            # Students see their studio (read-only via permissions)
            return Studio.objects.filter(id=user.student_profile.studio.id)
        else:
            return Studio.objects.none()

    @action(detail=False, methods=["get", "put", "patch"])
    def current(self, request):
        """Get or update the current context studio"""
        # For MVP, assuming 1 studio per admin
        studio = Studio.objects.filter(owner=request.user).first()

        if not studio:
            return Response(
                {"detail": "No studio found for this user"}, status=status.HTTP_404_NOT_FOUND
            )

        if request.method == "GET":
            serializer = self.get_serializer(studio)
            return Response(serializer.data)

        # Check permissions for update
        if request.user.role != "admin":
            return Response(
                {"detail": "Only admins can update studio settings"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(studio, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.AllowAny],
        url_path="by-subdomain/(?P<subdomain>[^/.]+)",
    )
    def by_subdomain(self, request, subdomain=None):
        """Fetch public studio info by subdomain"""
        studio = get_object_or_404(Studio, subdomain=subdomain, is_active=True)
        serializer = self.get_serializer(studio)
        # Filter out sensitive info if necessary, but for now StudioSerializer is okay
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.AllowAny],
        url_path="by-subdomain/(?P<subdomain>[^/.]+)/teachers",
    )
    def teachers(self, request, subdomain=None):
        """Fetch public teachers list for a studio"""
        studio = get_object_or_404(Studio, subdomain=subdomain, is_active=True)
        teachers = Teacher.objects.filter(studio=studio, is_active=True)
        serializer = PublicTeacherSerializer(teachers, many=True, context={"request": request})
        return Response(serializer.data)


class TeacherViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Admin teacher management
    """

    serializer_class = TeacherSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Admin: see all teachers in their studios
        if self.request.user.role == "admin":
            # Admin: see all teachers (consistent with UserViewSet)
            return Teacher.objects.all()
        # Teachers: see self?
        if hasattr(self.request.user, "teacher_profile"):
            return Teacher.objects.filter(studio=self.request.user.teacher_profile.studio)
        # Students: see teachers in their studio
        if hasattr(self.request.user, "student_profile"):
            return Teacher.objects.filter(studio=self.request.user.student_profile.studio)
        return Teacher.objects.none()


class StudentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Admin student management
    """

    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAuthenticated]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["user__email", "user__first_name", "user__last_name", "instrument"]
    ordering_fields = ["user__last_name", "created_at"]
    ordering = ["user__last_name"]

    def get_queryset(self):
        queryset = Student.objects.none()

        # Determine base queryset based on role
        if self.request.user.role == "admin":
            queryset = Student.objects.all()
        elif self.request.user.role == "teacher":
            if hasattr(self.request.user, "teacher_profile"):
                queryset = Student.objects.filter(
                    studio=self.request.user.teacher_profile.studio, user__role="student"
                )
        elif hasattr(self.request.user, "student_profile"):
            queryset = Student.objects.filter(id=self.request.user.student_profile.id)

        # Apply Manual Filters
        instrument = self.request.query_params.get("instrument")
        if instrument and instrument != "all":
            queryset = queryset.filter(instrument__iexact=instrument)

        teacher_id = self.request.query_params.get("teacher_id")
        if teacher_id:
            queryset = queryset.filter(primary_teacher_id=teacher_id)

        return queryset

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get roster metrics for the current user's scope"""
        queryset = self.get_queryset()

        total_students = queryset.count()
        active_students = queryset.filter(is_active=True).count()
        unassigned_students = queryset.filter(primary_teacher__isnull=True).count()

        return Response(
            {
                "total_students": total_students,
                "active_students": active_students,
                "unassigned_students": unassigned_students,
            }
        )


class ReportsExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get_report_data(self, report_type, user):  # noqa: C901
        """Return (headers, rows, records) for any report type.

        headers  – list of column names (for CSV)
        rows     – list of lists (for CSV)
        records  – list of dicts (for JSON / Excel)
        """
        headers, rows, records = [], [], []

        # Robust Studio Lookup
        from studiosync_core.core.models import Studio

        studio = Studio.objects.filter(owner=user).first()
        if not studio and user.role == "admin":
            # If admin but not technically owner in DB record, fallback to first studio
            studio = Studio.objects.first()

        if report_type == "financial":
            headers = ["date", "description", "category", "amount", "status"]
            from studiosync_core.billing.models import Invoice

            if studio:
                try:
                    invoices = Invoice.objects.filter(studio=studio).select_related(
                        "student__user", "band"
                    )
                    for inv in invoices:
                        bill_to = (
                            inv.student.user.get_full_name()
                            if inv.student
                            else (inv.band.name if inv.band else "Unknown")
                        )
                        row = [
                            str(inv.created_at.date()),
                            f"Invoice {inv.invoice_number} - {bill_to}",
                            "Tuition" if inv.student else "Band/Group",
                            str(inv.total_amount),
                            inv.status.title(),
                        ]
                        rows.append(row)
                        records.append(dict(zip(headers, row)))
                except Exception as e:
                    rows.append(["Error generating report", str(e)])

        elif report_type == "students":
            headers = ["name", "email", "instrument", "status", "phone", "enrollment_date"]
            from studiosync_core.core.models import Student

            if studio:
                students = Student.objects.filter(studio=studio).select_related("user")
                for s in students:
                    row = [
                        s.user.get_full_name(),
                        s.user.email,
                        s.instrument or "",
                        "Active" if s.is_active else "Inactive",
                        s.user.phone or "",
                        str(s.enrollment_date) if s.enrollment_date else "",
                    ]
                    rows.append(row)
                    records.append(dict(zip(headers, row)))

        elif report_type == "teachers":
            headers = ["name", "email", "specialties", "hourly_rate", "status"]
            from studiosync_core.core.models import Teacher

            if studio:
                teachers = Teacher.objects.filter(studio=studio).select_related("user")
                for t in teachers:
                    row = [
                        t.user.get_full_name(),
                        t.user.email,
                        ", ".join(t.specialties) if t.specialties else "",
                        str(t.hourly_rate) if t.hourly_rate else "",
                        "Active" if t.is_active else "Inactive",
                    ]
                    rows.append(row)
                    records.append(dict(zip(headers, row)))

        elif report_type == "users":
            headers = ["name", "email", "role", "date_joined", "last_login"]
            from django.db.models import Q

            if studio:
                target_users = User.objects.filter(
                    Q(student_profile__studio=studio)
                    | Q(teacher_profile__studio=studio)
                    | Q(id=user.id)
                ).distinct()
                for u in target_users:
                    row = [
                        u.get_full_name(),
                        u.email,
                        u.role.title(),
                        str(u.created_at.date()),
                        str(u.last_login.date()) if u.last_login else "Never",
                    ]
                    rows.append(row)
                    records.append(dict(zip(headers, row)))

        elif report_type == "attendance":
            headers = ["student", "total", "attended", "cancelled", "percentage"]
            from django.db.models import Count, Q

            if studio:
                # Group by student and count lesson statuses
                from studiosync_core.core.models import Student

                student_stats = (
                    Student.objects.filter(studio=studio)
                    .annotate(
                        total_count=Count("lessons"),
                        attended_count=Count("lessons", filter=Q(lessons__status="completed")),
                        cancelled_count=Count("lessons", filter=Q(lessons__status="cancelled")),
                    )
                    .select_related("user")
                )

                for s in student_stats:
                    percentage = (
                        f"{(s.attended_count / s.total_count * 100):.1f}%"
                        if s.total_count > 0
                        else "0.0%"
                    )
                    row = [
                        s.user.get_full_name(),
                        s.total_count,
                        s.attended_count,
                        s.cancelled_count,
                        percentage,
                    ]
                    rows.append(row)
                    records.append(dict(zip(headers, row)))

        elif report_type == "student-progress":
            headers = ["student", "goal", "status", "progress", "target_date"]
            from studiosync_core.lessons.models import StudentGoal

            goals = StudentGoal.objects.none()
            if studio:
                goals = StudentGoal.objects.filter(student__studio=studio).select_related(
                    "student__user"
                )
            elif hasattr(user, "teacher_profile"):
                goals = StudentGoal.objects.filter(teacher=user.teacher_profile).select_related(
                    "student__user"
                )

            for goal in goals:
                st_name = goal.student.user.get_full_name() if goal.student else "Unknown"
                row = [
                    st_name,
                    goal.title,
                    goal.status.title(),
                    f"{goal.progress_percentage}%",
                    str(goal.target_date) if goal.target_date else "",
                ]
                rows.append(row)
                records.append(dict(zip(headers, row)))

        return headers, rows, records

    def get(self, request):
        report_type = request.query_params.get("type", "")
        export_format = request.query_params.get("format", "csv").lower()
        user = request.user

        headers, rows, records = self._get_report_data(report_type, user)

        if export_format == "json":
            return JsonResponse(records, safe=False)

        # Default: CSV
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{report_type}_report.csv"'
        writer = csv.writer(response)
        if headers:
            # Write a human-friendly header row (Title Case)
            writer.writerow([h.replace("_", " ").title() for h in headers])
        if rows:
            writer.writerows(rows)
        elif not headers:
            writer.writerow(["Error", "Invalid report type"])
        return response
