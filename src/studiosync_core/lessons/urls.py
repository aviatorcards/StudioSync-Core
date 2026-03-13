from django.urls import include, path

from rest_framework.routers import DefaultRouter  # noqa: F401

from config.routers import OptionalSlashRouter

from . import calendar_views, import_calendar_views, views

router = OptionalSlashRouter()
router.register(r"plans", views.LessonPlanViewSet, basename="lesson-plan")
router.register(r"goals", views.StudentGoalViewSet, basename="goal")
router.register(r"", views.LessonViewSet, basename="lesson")

# External calendar import — registered on their own router with explicit prefix
# so they're matched before the LessonViewSet's catch-all empty-prefix routes.
external_feeds_router = OptionalSlashRouter()
external_feeds_router.register(
    r"",
    import_calendar_views.ExternalCalendarFeedViewSet,
    basename="external-calendar-feed",
)

external_events_router = OptionalSlashRouter()
external_events_router.register(
    r"",
    import_calendar_views.ExternalCalendarEventViewSet,
    basename="external-calendar-event",
)

urlpatterns = [
    # External calendar import — MUST be listed before the main lesson router include
    # to avoid the lesson router's catch-all matching these paths.
    path("external-feeds/", include(external_feeds_router.urls)),
    path("external-feeds", include(external_feeds_router.urls)),
    path("external-events/", include(external_events_router.urls)),
    path("external-events", include(external_events_router.urls)),

    # REST API (lessons, plans, goals)
    path("", include(router.urls)),

    # Calendar feeds (export)
    path(
        "calendar/teacher/<uuid:teacher_id>/lessons.ics",
        calendar_views.teacher_calendar_feed,
        name="teacher-calendar-feed",
    ),
    path(
        "calendar/student/<uuid:student_id>/lessons.ics",
        calendar_views.student_calendar_feed,
        name="student-calendar-feed",
    ),
    path(
        "calendar/studio/<uuid:studio_id>/lessons.ics",
        calendar_views.studio_calendar_feed,
        name="studio-calendar-feed",
    ),
    path("calendar/my/lessons.ics", calendar_views.my_calendar_feed, name="my-calendar-feed"),
]


