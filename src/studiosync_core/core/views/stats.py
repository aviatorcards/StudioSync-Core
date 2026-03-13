from datetime import timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from studiosync_core.billing.models import Invoice
from studiosync_core.core.models import Student, Teacher
from studiosync_core.lessons.models import Lesson


class DashboardStatsView(APIView):
    """
    API View to return aggregated dashboard statistics
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):  # noqa: C901
        user = request.user
        today = timezone.now()
        start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Initialize stats structure
        stats = {"overview": {}, "recent_activity": []}

        # ADMIN VIEW
        if user.role == "admin":
            # 1. Total Students — all active students for admins
            total_students = Student.objects.filter(is_active=True).count()
            # Growth should be compared to start of month
            students_before_month = Student.objects.filter(
                is_active=True, created_at__lt=start_of_month
            ).count()
            student_growth = total_students - students_before_month

            # 2. Scheduled Lessons (This Week)
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=7)
            lessons_this_week = Lesson.objects.filter(
                scheduled_start__range=[week_start, week_end], status="scheduled"
            ).count()

            # 3. Revenue (Month) - Sum of total_amount from paid invoices issued this month
            revenue_month = (
                Invoice.objects.filter(
                    status="paid", issue_date__gte=start_of_month.date()
                ).aggregate(total=Sum("total_amount"))["total"]
                or 0
            )

            # 4. Active Teachers
            active_teachers = Teacher.objects.filter(is_active=True).count()

            # 5. Unpaid Invoices
            unpaid_qs = Invoice.objects.filter(
                status__in=["sent", "overdue", "partial"]
            )
            unpaid_val = sum(inv.balance_due for inv in unpaid_qs)
            unpaid_invoices = float(unpaid_val)

            # 6. Average Attendance
            completed_c = Lesson.objects.filter(status="completed").count()
            cancelled_c = Lesson.objects.filter(status="cancelled").count()
            noshow_c = Lesson.objects.filter(status="no_show").count()
            total_past = completed_c + cancelled_c + noshow_c
            rate_val = int(completed_c / total_past * 100) if total_past > 0 else 100
            avg_attendance = f"{rate_val}%"

            # 7. New Enquiries (Placeholder until Enquiry module exists)
            new_enquiries = 0

            stats["overview"] = {
                "total_students": {
                    "value": total_students,
                    "trend": f"{'+' if student_growth >= 0 else ''}{student_growth} new this month",
                    "positive": student_growth > 0,
                },
                "weekly_lessons": {
                    "value": lessons_this_week,
                    "trend": "Scheduled",
                    "positive": True,
                },
                "monthly_revenue": {
                    "value": float(revenue_month),
                    "trend": "This month",
                    "positive": True,
                },
                "active_teachers": {"value": active_teachers, "trend": "Active", "positive": True},
                "unpaid_invoices": {
                    "value": unpaid_invoices,
                    "trend": "Overdue",
                    "positive": False,
                },
                "avg_attendance": {
                    "value": avg_attendance,
                    "trend": "Last 30 days",
                    "positive": True,
                },
                "new_enquiries": {
                    "value": new_enquiries,
                    "trend": "Needs action",
                    "positive": True,
                },
            }

        # TEACHER VIEW
        elif user.role == "teacher" and hasattr(user, "teacher_profile"):
            teacher = user.teacher_profile

            # 1. My Students
            my_students = Student.objects.filter(primary_teacher=teacher, is_active=True).count()

            # 2. Today's Schedule
            today_start = today.replace(hour=0, minute=0, second=0)
            today_end = today_start + timedelta(days=1)
            lessons_today = Lesson.objects.filter(
                teacher=teacher, scheduled_start__range=[today_start, today_end], status="scheduled"
            ).count()

            # 3. Hours Taught (Month)
            lessons_month = Lesson.objects.filter(
                teacher=teacher, scheduled_start__gte=start_of_month, status="completed"
            )
            # Calculate duration in hours roughly
            hours_taught = 0
            for lesson in lessons_month:
                duration = (lesson.scheduled_end - lesson.scheduled_start).total_seconds() / 3600
                hours_taught += duration

            stats["overview"] = {
                "my_students": {"value": my_students, "label": "Active Students"},
                "lessons_today": {"value": lessons_today, "label": "Remaining Today"},
                "hours_taught": {"value": round(hours_taught, 1), "label": "Hours (This Month)"},
            }

        # STUDENT VIEW
        elif user.role == "student" and hasattr(user, "student_profile"):
            student = user.student_profile

            # 1. Next Lesson
            next_lesson_obj = (
                Lesson.objects.filter(
                    student=student, scheduled_start__gte=today, status="scheduled"
                )
                .order_by("scheduled_start")
                .first()
            )

            next_lesson_val = "None"
            next_lesson_label = ""
            if next_lesson_obj:
                next_lesson_val = next_lesson_obj.scheduled_start.strftime("%a, %b %d")
                next_lesson_label = next_lesson_obj.scheduled_start.strftime("%I:%M %p")

            # 2. Balance Due
            balance_due = 0.0
            if student.bands.exists():
                unpaid_qs = Invoice.objects.filter(
                    band__in=student.bands.all(), status__in=["sent", "overdue", "partial"]
                )
                unpaid_val = sum(inv.balance_due for inv in unpaid_qs)
                balance_due = float(unpaid_val)

            # 3. Practice Goal (Estimate from active practice-related goals)
            practice_val = "0/7"
            practice_label = "days this week"
            try:
                week_start = timezone.now() - timedelta(days=timezone.now().weekday())
                week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

                # Check for practice-related goals
                practice_goal_obj = student.goals.filter(
                    title__icontains="Practice", status="active"
                ).first()

                if practice_goal_obj and practice_goal_obj.progress_percentage is not None:
                    # Estimate days practiced from progress percentage
                    days_practiced = int((practice_goal_obj.progress_percentage / 100) * 7)
                    practice_val = f"{days_practiced}/7"
                    practice_label = "days this week (est.)"
            except Exception:
                pass

            stats["overview"] = {
                "next_lesson": {
                    "value": next_lesson_val,
                    "label": next_lesson_label,
                    "id": "next_lesson",
                },
                "practice_goal": {
                    "value": practice_val,
                    "label": practice_label,
                    "id": "practice_goal",
                },
                "balance_due": {
                    "value": f"${balance_due:,.2f}",
                    "label": "All paid up!" if balance_due <= 0 else "Pending payment",
                    "id": "balance_due",
                },
            }

        # RECENT ACTIVITY (Common)
        # Fetch recent completed lessons or updates
        qs = (
            Lesson.objects.select_related("student__user", "teacher__user")
            .filter(status__in=["completed", "cancelled", "scheduled"])
            .order_by("-updated_at")
        )

        # Filter visibility
        if user.role == "teacher" and hasattr(user, "teacher_profile"):
            qs = qs.filter(teacher=user.teacher_profile)
        elif user.role == "student" and hasattr(user, "student_profile"):
            qs = qs.filter(student=user.student_profile)

        recent_lessons = qs[:5]

        activity_data = []
        for lesson in recent_lessons:
            action_text = ""
            icon_type = "info"

            # Determine display name based on who is asking
            other_party = "Unknown"
            if user.role == "student":
                if lesson.teacher and lesson.teacher.user:
                    other_party = lesson.teacher.user.get_full_name()
                display_text = f"lesson with {other_party}"
            else:
                if lesson.student and lesson.student.user:
                    other_party = lesson.student.user.get_full_name()
                display_text = f"lesson with {other_party}"

            if lesson.status == "completed":
                action_text = f"Completed {display_text}"
                icon_type = "success"
            elif lesson.status == "cancelled":
                action_text = f"Cancelled {display_text}"
                icon_type = "warning"
            elif lesson.status == "scheduled":
                action_text = f"Scheduled {display_text}"
                icon_type = "info"

            activity_data.append(
                {
                    "id": str(lesson.id),
                    "text": action_text,
                    "time": lesson.updated_at,
                    "type": icon_type,
                }
            )

        stats["recent_activity"] = activity_data

        return Response(stats)


class DashboardAnalyticsView(APIView):
    """
    API View to return aggregated dashboard charts data (Revenue, Student Growth, Attendance)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Only admins can see full studio analytics
        if user.role != "admin":
            return Response({"error": "Unauthorized"}, status=403)

        today = timezone.now()
        six_months_ago = today - timedelta(days=180)

        # 1. Revenue Trend (Last 6 Months)
        # Assuming paid invoices confirm revenue
        revenue_trend = []

        # We'll use TruncMonth to aggregate by month
        revenue_qs = (
            Invoice.objects.filter(
                status="paid", created_at__gte=six_months_ago
            )
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(total_revenue=Sum("total_amount"))
            .order_by("month")
        )

        # Convert to list with month names
        # We want to ensure all 6 months are present even if 0 revenue, but for simplicity
        # let's just map what we have and the frontend can fill gaps or we handle gaps here.
        # Handling gaps here is better for charts.

        revenue_map = {
            item["month"].strftime("%Y-%m"): item["total_revenue"] for item in revenue_qs
        }

        for i in range(5, -1, -1):
            date = today - timedelta(days=i * 30)  # Approx
            key = date.strftime("%Y-%m")
            month_label = date.strftime("%b")

            revenue_trend.append({"month": month_label, "revenue": float(revenue_map.get(key, 0))})

        # 2. Student Growth (Last 6 Months enrollment)
        # This is strictly "New Students" per month, or Total Active?
        # The chart title says "Student Growth - Monthly enrollment", implying new students.
        student_growth = []

        enrollment_qs = (
            Student.objects.filter(
                created_at__gte=six_months_ago,
                is_active=True,  # We might want historical here, but active is okay for now
            )
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(new_students=Count("id"))
            .order_by("month")
        )

        enrollment_map = {
            item["month"].strftime("%Y-%m"): item["new_students"] for item in enrollment_qs
        }

        for i in range(5, -1, -1):
            date = today - timedelta(days=i * 30)
            key = date.strftime("%Y-%m")
            month_label = date.strftime("%b")

            student_growth.append({"month": month_label, "students": enrollment_map.get(key, 0)})

        # 3. Lesson Attendance (This Month Breakdown)
        start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        attendance_qs = (
            Lesson.objects.filter(
                scheduled_start__gte=start_of_month,
                scheduled_start__lte=today,  # Up to now
            )
            .values("status")
            .annotate(count=Count("id"))
        )

        # We need to map standard statuses to chart categories: Attended, Excused (Cancelled), No-show
        # Assuming model has: 'scheduled', 'completed' (Attended), 'cancelled', 'no_show' (if exists), 'missed'

        status_map = {item["status"]: item["count"] for item in attendance_qs}

        attendance_data = [
            {"name": "Attended", "value": status_map.get("completed", 0)},
            {"name": "Canceled", "value": status_map.get("cancelled", 0)},
            {"name": "No-show", "value": status_map.get("no_show", 0)},
            {"name": "Scheduled", "value": status_map.get("scheduled", 0)},
        ]

        return Response(
            {
                "revenue_trend": revenue_trend,
                "student_growth": student_growth,
                "attendance": attendance_data,
            }
        )
