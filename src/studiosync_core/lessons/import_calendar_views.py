"""
External iCal Calendar Import Views
Allows users to subscribe to external iCal feeds and overlay events on their schedule.
"""

import logging
from datetime import datetime, timezone

import requests

from django.utils import timezone as dj_timezone

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from icalendar import Calendar as ICalendar

from studiosync_core.lessons.models import ExternalCalendarEvent, ExternalCalendarFeed
from studiosync_core.lessons.serializers import ExternalCalendarEventSerializer, ExternalCalendarFeedSerializer

logger = logging.getLogger(__name__)

# How long to wait for a remote iCal URL before giving up
FETCH_TIMEOUT_SECONDS = 10

# Maximum bytes we'll accept from a feed (5 MB) to prevent abuse
MAX_FEED_SIZE_BYTES = 5 * 1024 * 1024


def _fetch_ical(url: str) -> bytes:
    """
    Fetch raw ICS bytes from a URL.
    Raises requests.RequestException on network failure.
    Raises ValueError if the response is too large or doesn't look like iCal.
    """
    headers = {
        "User-Agent": "StudioSync/1.0 (iCal import)",
        "Accept": "text/calendar, application/ics, */*",
    }
    resp = requests.get(url, headers=headers, timeout=FETCH_TIMEOUT_SECONDS, stream=True)
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "")
    # Don't be too strict — some servers send wrong content types
    # (e.g. application/octet-stream) but the body is valid ICS

    data = b""
    for chunk in resp.iter_content(chunk_size=8192):
        data += chunk
        if len(data) > MAX_FEED_SIZE_BYTES:
            raise ValueError(
                f"Feed exceeds maximum allowed size of {MAX_FEED_SIZE_BYTES // 1024 // 1024} MB"
            )

    return data


def _parse_and_upsert_events(feed: ExternalCalendarFeed, ics_bytes: bytes) -> int:
    """
    Parse raw ICS bytes and upsert ExternalCalendarEvent records for the given feed.
    Returns the number of events created or updated.
    """
    cal = ICalendar.from_ical(ics_bytes)
    count = 0

    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        uid = str(component.get("UID", ""))
        if not uid:
            continue

        summary = str(component.get("SUMMARY", ""))
        description = str(component.get("DESCRIPTION", ""))
        location = str(component.get("LOCATION", ""))

        dtstart = component.get("DTSTART")
        dtend = component.get("DTEND")

        if dtstart is None:
            continue

        def to_aware_dt(dt_prop):
            """Convert a vDatetime/vDate to timezone-aware datetime."""
            dt = dt_prop.dt if hasattr(dt_prop, "dt") else dt_prop
            if isinstance(dt, datetime):
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            else:
                # all-day date — treat as midnight UTC
                return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)

        start_dt = to_aware_dt(dtstart)
        end_dt = to_aware_dt(dtend) if dtend else start_dt

        ExternalCalendarEvent.objects.update_or_create(
            feed=feed,
            uid=uid,
            defaults={
                "title": summary[:500],
                "description": description,
                "location": location[:500],
                "start_dt": start_dt,
                "end_dt": end_dt,
            },
        )
        count += 1

    return count


class ExternalCalendarFeedViewSet(viewsets.ModelViewSet):
    """
    CRUD for a user's external iCal feed subscriptions.

    GET    /api/lessons/external-feeds/          — list my feeds
    POST   /api/lessons/external-feeds/          — add a feed
    GET    /api/lessons/external-feeds/{id}/     — get one feed
    PATCH  /api/lessons/external-feeds/{id}/     — update name/color/enabled
    DELETE /api/lessons/external-feeds/{id}/     — remove feed + all cached events
    POST   /api/lessons/external-feeds/{id}/refresh/  — manually trigger re-sync
    """

    serializer_class = ExternalCalendarFeedSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ExternalCalendarFeed.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Save the feed and immediately attempt a first sync."""
        url = serializer.validated_data["url"]
        feed = serializer.save(user=self.request.user, last_error="")

        # Attempt initial fetch
        try:
            ics_bytes = _fetch_ical(url)
            _parse_and_upsert_events(feed, ics_bytes)
            feed.last_synced_at = dj_timezone.now()
            feed.last_error = ""
            feed.save(update_fields=["last_synced_at", "last_error"])
        except Exception as exc:
            logger.error("Initial sync failed for feed %s: %s", feed.id, exc)
            feed.last_error = str(exc)
            feed.save(update_fields=["last_error"])
            # Don't raise — the feed is saved, user can retry

    @action(detail=True, methods=["post"], url_path="refresh")
    def refresh(self, request, pk=None):
        """
        Manually trigger a re-sync of a specific feed.
        POST /api/lessons/external-feeds/{id}/refresh/
        """
        feed = self.get_object()  # Ensures ownership via get_queryset

        try:
            ics_bytes = _fetch_ical(feed.url)
            count = _parse_and_upsert_events(feed, ics_bytes)
            feed.last_synced_at = dj_timezone.now()
            feed.last_error = ""
            feed.save(update_fields=["last_synced_at", "last_error"])

            return Response(
                {
                    "status": "ok",
                    "events_synced": count,
                    "last_synced_at": feed.last_synced_at,
                }
            )
        except requests.RequestException as exc:
            msg = f"Failed to fetch feed: {exc}"
            feed.last_error = msg
            feed.save(update_fields=["last_error"])
            return Response({"error": msg}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as exc:
            msg = f"Failed to parse feed: {exc}"
            feed.last_error = msg
            feed.save(update_fields=["last_error"])
            return Response({"error": msg}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)


class ExternalCalendarEventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only access to cached external calendar events for the authenticated user.

    GET /api/lessons/external-events/
        ?feed=<uuid>          — filter by specific feed
        ?start=<iso8601>      — filter events ending after this datetime
        ?end=<iso8601>        — filter events starting before this datetime
        ?enabled_only=true    — only events from enabled feeds (default: true)
    """

    serializer_class = ExternalCalendarEventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = ExternalCalendarEvent.objects.filter(
            feed__user=self.request.user
        ).select_related("feed")

        # Default: only return events from enabled feeds
        enabled_only = self.request.query_params.get("enabled_only", "true").lower()
        if enabled_only != "false":
            qs = qs.filter(feed__is_enabled=True)

        # Filter by feed ID
        feed_id = self.request.query_params.get("feed")
        if feed_id:
            qs = qs.filter(feed__id=feed_id)

        # Date range filtering for schedule overlay
        start_str = self.request.query_params.get("start")
        end_str = self.request.query_params.get("end")

        if start_str:
            try:
                from django.utils.dateparse import parse_datetime

                start = parse_datetime(start_str)
                if start:
                    qs = qs.filter(end_dt__gte=start)
            except Exception:
                pass

        if end_str:
            try:
                from django.utils.dateparse import parse_datetime

                end = parse_datetime(end_str)
                if end:
                    qs = qs.filter(start_dt__lte=end)
            except Exception:
                pass

        return qs.order_by("start_dt")
