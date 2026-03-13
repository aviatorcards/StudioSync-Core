"""
Tests for external calendar import API endpoints.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest
from django.urls import reverse
from rest_framework import status

from studiosync_core.lessons.models import ExternalCalendarFeed, ExternalCalendarEvent


# Minimal valid ICS fixture used across tests
SAMPLE_ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:test-event-001@example.com
SUMMARY:Gig at Blue Note
DESCRIPTION:Jazz quartet performance
LOCATION:Blue Note NYC
DTSTART:20260310T190000Z
DTEND:20260310T220000Z
END:VEVENT
BEGIN:VEVENT
UID:test-event-002@example.com
SUMMARY:Rehearsal
DTSTART:20260311T140000Z
DTEND:20260311T160000Z
END:VEVENT
END:VCALENDAR
"""


def _mock_fetch_ok(url, **kwargs):
    """Return a successful mock response simulating an iCal feed."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "text/calendar; charset=utf-8"}
    mock_resp.raise_for_status = MagicMock()
    mock_resp.iter_content = MagicMock(return_value=[SAMPLE_ICS])
    return mock_resp


@pytest.mark.api
@pytest.mark.django_db
class TestExternalCalendarFeedAPI:
    """Test the /api/lessons/external-feeds/ endpoints."""

    def test_list_feeds_unauthenticated(self, api_client):
        """Unauthenticated requests are rejected."""
        url = reverse("external-calendar-feed-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("studiosync_core.lessons.import_calendar_views.requests.get", side_effect=_mock_fetch_ok)
    def test_create_feed_success(self, mock_get, authenticated_client):
        """Authenticated user can create a feed; initial sync runs."""
        url = reverse("external-calendar-feed-list")
        data = {
            "name": "My Google Calendar",
            "url": "https://calendar.google.com/calendar/ical/test%40gmail.com/public/basic.ics",
            "color": "#10b981",
        }
        response = authenticated_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert ExternalCalendarFeed.objects.count() == 1
        feed = ExternalCalendarFeed.objects.first()
        assert feed.name == "My Google Calendar"
        assert feed.color == "#10b981"
        # Initial sync should have created events
        assert ExternalCalendarEvent.objects.filter(feed=feed).count() == 2

    @patch("studiosync_core.lessons.import_calendar_views.requests.get", side_effect=_mock_fetch_ok)
    def test_webcal_scheme_normalized(self, mock_get, authenticated_client):
        """webcal:// scheme is normalized to https:// before saving."""
        url = reverse("external-calendar-feed-list")
        data = {
            "name": "Apple iCal",
            "url": "webcal://p09-caldav.icloud.com/published/2/abcdef.ics",
            "color": "#6366f1",
        }
        response = authenticated_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        feed = ExternalCalendarFeed.objects.first()
        assert feed.url.startswith("https://")

    def test_create_feed_missing_url(self, authenticated_client):
        """Creating a feed without a URL returns 400."""
        url = reverse("external-calendar-feed-list")
        data = {"name": "No URL Feed"}
        response = authenticated_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("studiosync_core.lessons.import_calendar_views.requests.get", side_effect=_mock_fetch_ok)
    def test_user_isolation(self, mock_get, api_client, admin_user, teacher_user):
        """Users can only see their own feeds."""
        from rest_framework.test import APIClient

        admin_client = APIClient()
        admin_client.force_authenticate(user=admin_user)

        teacher_client = APIClient()
        teacher_client.force_authenticate(user=teacher_user)

        list_url = reverse("external-calendar-feed-list")

        # admin creates a feed
        admin_client.post(
            list_url,
            {"name": "Admin Calendar", "url": "https://example.com/admin.ics"},
            format="json",
        )

        # teacher creates their own feed
        teacher_client.post(
            list_url,
            {"name": "Teacher Calendar", "url": "https://example.com/teacher.ics"},
            format="json",
        )

        # Admin sees only their own feed
        admin_resp = admin_client.get(list_url)
        assert admin_resp.status_code == status.HTTP_200_OK
        admin_results = admin_resp.data.get("results", admin_resp.data)
        assert len(admin_results) == 1
        assert admin_results[0]["name"] == "Admin Calendar"

        # Teacher sees only their own feed
        teacher_resp = teacher_client.get(list_url)
        assert teacher_resp.status_code == status.HTTP_200_OK
        teacher_results = teacher_resp.data.get("results", teacher_resp.data)
        assert len(teacher_results) == 1
        assert teacher_results[0]["name"] == "Teacher Calendar"

    @patch("studiosync_core.lessons.import_calendar_views.requests.get", side_effect=_mock_fetch_ok)
    def test_refresh_action(self, mock_get, authenticated_client, admin_user):
        """POST /refresh/ fetches and upserts events, returns count."""
        feed = ExternalCalendarFeed.objects.create(
            user=admin_user,
            name="Manual Feed",
            url="https://example.com/manual.ics",
        )
        url = reverse("external-calendar-feed-refresh", args=[feed.id])
        response = authenticated_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["events_synced"] == 2
        assert ExternalCalendarEvent.objects.filter(feed=feed).count() == 2

    @patch(
        "studiosync_core.lessons.import_calendar_views.requests.get",
        side_effect=Exception("Connection refused"),
    )
    def test_refresh_network_error_stored(self, mock_get, authenticated_client, admin_user):
        """A network failure during refresh stores the error message and returns 502."""
        import requests as _requests

        mock_get.side_effect = _requests.RequestException("Connection refused")
        feed = ExternalCalendarFeed.objects.create(
            user=admin_user,
            name="Bad Feed",
            url="https://example.com/bad.ics",
        )
        url = reverse("external-calendar-feed-refresh", args=[feed.id])
        response = authenticated_client.post(url)
        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        feed.refresh_from_db()
        assert "Connection refused" in feed.last_error

    @patch("studiosync_core.lessons.import_calendar_views.requests.get", side_effect=_mock_fetch_ok)
    def test_delete_feed_cascades_events(self, mock_get, authenticated_client, admin_user):
        """Deleting a feed also removes all cached events."""
        feed = ExternalCalendarFeed.objects.create(
            user=admin_user,
            name="To Delete",
            url="https://example.com/delete.ics",
        )
        ExternalCalendarEvent.objects.create(
            feed=feed,
            uid="evt-001@del.com",
            title="Will be deleted",
            start_dt=datetime(2026, 3, 10, 19, tzinfo=timezone.utc),
            end_dt=datetime(2026, 3, 10, 21, tzinfo=timezone.utc),
        )
        detail_url = reverse("external-calendar-feed-detail", args=[feed.id])
        response = authenticated_client.delete(detail_url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not ExternalCalendarFeed.objects.filter(id=feed.id).exists()
        assert not ExternalCalendarEvent.objects.filter(feed__id=feed.id).exists()


@pytest.mark.api
@pytest.mark.django_db
class TestExternalCalendarEventAPI:
    """Test the /api/lessons/external-events/ read-only endpoints."""

    @pytest.fixture
    def feed_with_events(self, admin_user):
        feed = ExternalCalendarFeed.objects.create(
            user=admin_user,
            name="Test Feed",
            url="https://example.com/test.ics",
            is_enabled=True,
        )
        ExternalCalendarEvent.objects.create(
            feed=feed,
            uid="evt-a@test.com",
            title="Morning Gig",
            start_dt=datetime(2026, 3, 10, 10, tzinfo=timezone.utc),
            end_dt=datetime(2026, 3, 10, 12, tzinfo=timezone.utc),
        )
        ExternalCalendarEvent.objects.create(
            feed=feed,
            uid="evt-b@test.com",
            title="Evening Gig",
            start_dt=datetime(2026, 3, 15, 20, tzinfo=timezone.utc),
            end_dt=datetime(2026, 3, 15, 23, tzinfo=timezone.utc),
        )
        return feed

    def test_list_events_unauthenticated(self, api_client):
        """Unauthenticated access is rejected."""
        url = reverse("external-calendar-event-list")
        assert api_client.get(url).status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_events_returns_own_only(self, authenticated_client, feed_with_events):
        """Authenticated user only sees their own events."""
        url = reverse("external-calendar-event-list")
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        results = response.data.get("results", response.data)
        assert len(results) == 2
        assert results[0]["feed_name"] == "Test Feed"

    def test_date_range_filter(self, authenticated_client, feed_with_events):
        """?start= and ?end= correctly narrow the result set."""
        url = reverse("external-calendar-event-list")
        # Only events that overlap the 10th
        response = authenticated_client.get(
            url, {"start": "2026-03-10T00:00:00Z", "end": "2026-03-10T23:59:59Z"}
        )
        assert response.status_code == status.HTTP_200_OK
        results = response.data.get("results", response.data)
        titles = [e["title"] for e in results]
        assert "Morning Gig" in titles
        assert "Evening Gig" not in titles

    def test_disabled_feed_events_hidden(self, authenticated_client, feed_with_events):
        """Events from disabled feeds are excluded by default."""
        feed_with_events.is_enabled = False
        feed_with_events.save()
        url = reverse("external-calendar-event-list")
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        results = response.data.get("results", response.data)
        assert len(results) == 0

    def test_disabled_feed_visible_with_flag(self, authenticated_client, feed_with_events):
        """?enabled_only=false includes events from disabled feeds."""
        feed_with_events.is_enabled = False
        feed_with_events.save()
        url = reverse("external-calendar-event-list")
        response = authenticated_client.get(url, {"enabled_only": "false"})
        assert response.status_code == status.HTTP_200_OK
        results = response.data.get("results", response.data)
        assert len(results) == 2
