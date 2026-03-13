"""
Tests for the Setup Wizard API.

Covers:
- GET /api/core/setup/status/  — before and after setup
- POST /api/core/setup/complete/ — happy path + validation errors + idempotency
- Feature flag data surfaces in status response
- Sample data creation flag
"""

import json

from django.test import TestCase

from rest_framework import status
from rest_framework.test import APIClient

from studiosync_core.core.models import SetupStatus, Student, Studio, Teacher, User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_SETUP_PAYLOAD = {
    # Studio
    "studio_name": "Harmony Music Academy",
    "studio_email": "contact@harmony.com",
    "studio_phone": "555-0100",
    "address_line1": "1 Melody Lane",
    "city": "Nashville",
    "state": "TN",
    "postal_code": "37201",
    "country": "US",
    "timezone": "America/Chicago",
    "currency": "USD",
    # Admin
    "admin_email": "admin@harmony.com",
    "admin_first_name": "Jane",
    "admin_last_name": "Doe",
    "admin_password": "Secur3P@ss!",
    "admin_phone": "555-0101",
    # Features
    "billing_enabled": True,
    "inventory_enabled": False,
    "messaging_enabled": True,
    "resources_enabled": True,
    "goals_enabled": True,
    "bands_enabled": False,
    "analytics_enabled": True,
    "practice_rooms_enabled": False,
    # Quick Settings
    "default_lesson_duration": 60,
    "business_start_hour": 9,
    "business_end_hour": 18,
    # Sample data
    "create_sample_data": False,
}


def setup_url(name: str) -> str:
    return f"/api/core/{name}/"


# ---------------------------------------------------------------------------
# Setup Status Tests
# ---------------------------------------------------------------------------


class SetupStatusViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_status_before_setup_returns_not_completed(self):
        """Fresh install — no SetupStatus row."""
        response = self.client.get(setup_url("setup/status"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertFalse(data["is_completed"])
        self.assertTrue(data["setup_required"])
        self.assertIn("features_enabled", data)

    def test_status_after_setup_returns_completed(self):
        """After running complete/, status should reflect completion."""
        SetupStatus.objects.create(
            is_completed=True,
            setup_version="1.0",
            features_enabled={"billing": True, "inventory": False},
        )
        response = self.client.get(setup_url("setup/status"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["is_completed"])
        self.assertFalse(data["setup_required"])
        self.assertEqual(data["features_enabled"]["billing"], True)
        self.assertEqual(data["features_enabled"]["inventory"], False)

    def test_status_endpoint_is_unauthenticated(self):
        """Status must be reachable without auth (needed before first login)."""
        # No credentials set — request should still 200
        response = self.client.get(setup_url("setup/status"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Complete Setup Tests
# ---------------------------------------------------------------------------


class CompleteSetupViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_complete_setup_happy_path(self):
        """Full valid payload creates admin, studio, and tokens."""
        response = self.client.post(
            setup_url("setup/complete"),
            data=json.dumps(VALID_SETUP_PAYLOAD),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.json())
        data = response.json()

        # Check response shape
        self.assertIn("tokens", data)
        self.assertIn("access", data["tokens"])
        self.assertIn("refresh", data["tokens"])
        self.assertIn("studio", data)
        self.assertEqual(data["studio"]["name"], VALID_SETUP_PAYLOAD["studio_name"])
        self.assertIn("user", data)
        self.assertEqual(data["user"]["email"], VALID_SETUP_PAYLOAD["admin_email"])
        self.assertEqual(data["user"]["role"], "admin")

    def test_complete_setup_creates_admin_user(self):
        """Admin user must be created with correct fields."""
        self.client.post(
            setup_url("setup/complete"),
            data=json.dumps(VALID_SETUP_PAYLOAD),
            content_type="application/json",
        )
        user = User.objects.get(email=VALID_SETUP_PAYLOAD["admin_email"])
        self.assertEqual(user.first_name, "Jane")
        self.assertEqual(user.last_name, "Doe")
        self.assertEqual(user.role, "admin")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_active)

    def test_complete_setup_creates_studio(self):
        """Studio must be created linking back to the admin user."""
        self.client.post(
            setup_url("setup/complete"),
            data=json.dumps(VALID_SETUP_PAYLOAD),
            content_type="application/json",
        )
        studio = Studio.objects.get(name=VALID_SETUP_PAYLOAD["studio_name"])
        admin = User.objects.get(email=VALID_SETUP_PAYLOAD["admin_email"])
        self.assertEqual(studio.owner, admin)
        self.assertEqual(studio.currency, "USD")
        self.assertEqual(studio.timezone, "America/Chicago")

    def test_complete_setup_marks_setup_status(self):
        """SetupStatus row must be created and marked complete."""
        self.client.post(
            setup_url("setup/complete"),
            data=json.dumps(VALID_SETUP_PAYLOAD),
            content_type="application/json",
        )
        setup = SetupStatus.objects.first()
        self.assertIsNotNone(setup)
        self.assertTrue(setup.is_completed)
        self.assertIsNotNone(setup.completed_at)

    def test_complete_setup_persists_feature_flags(self):
        """Feature selections must be stored in SetupStatus.features_enabled."""
        payload = {**VALID_SETUP_PAYLOAD, "billing_enabled": False, "bands_enabled": True}
        self.client.post(
            setup_url("setup/complete"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        setup = SetupStatus.objects.first()
        self.assertIsNotNone(setup)
        # Backend stores without _enabled suffix
        self.assertFalse(setup.features_enabled.get("billing", True))
        self.assertTrue(setup.features_enabled.get("bands", False))

    def test_complete_setup_idempotent_blocked(self):
        """Calling complete/ a second time must return 400."""
        self.client.post(
            setup_url("setup/complete"),
            data=json.dumps(VALID_SETUP_PAYLOAD),
            content_type="application/json",
        )
        # Second call with different email
        payload2 = {**VALID_SETUP_PAYLOAD, "admin_email": "admin2@harmony.com"}
        response = self.client.post(
            setup_url("setup/complete"),
            data=json.dumps(payload2),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.json())

    def test_complete_setup_rejects_duplicate_admin_email(self):
        """If admin_email already exists, validation must fail."""
        User.objects.create_user(
            email="admin@harmony.com",
            password="SomePass1!",
            first_name="Existing",
            last_name="User",
        )
        response = self.client.post(
            setup_url("setup/complete"),
            data=json.dumps(VALID_SETUP_PAYLOAD),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn("admin_email", data)

    def test_complete_setup_requires_studio_name(self):
        """Missing studio_name must return a validation error."""
        payload = {k: v for k, v in VALID_SETUP_PAYLOAD.items() if k != "studio_name"}
        response = self.client.post(
            setup_url("setup/complete"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("studio_name", response.json())

    def test_complete_setup_requires_strong_password(self):
        """Admin password must be at least 8 characters."""
        payload = {**VALID_SETUP_PAYLOAD, "admin_password": "short"}
        response = self.client.post(
            setup_url("setup/complete"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("admin_password", response.json())

    def test_complete_setup_is_unauthenticated(self):
        """The complete/ endpoint must be reachable without auth."""
        # No credentials — should succeed (201) or fail with validation, not 401
        response = self.client.post(
            setup_url("setup/complete"),
            data=json.dumps(VALID_SETUP_PAYLOAD),
            content_type="application/json",
        )
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# Sample Data Tests
# ---------------------------------------------------------------------------


class SampleDataTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_sample_data_creates_teacher_and_students(self):
        """When create_sample_data=True, teachers and students must be seeded."""
        payload = {**VALID_SETUP_PAYLOAD, "create_sample_data": True}
        response = self.client.post(
            setup_url("setup/complete"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.json())
        self.assertGreater(Teacher.objects.count(), 0)
        self.assertGreater(Student.objects.count(), 0)

    def test_no_sample_data_when_flag_false(self):
        """When create_sample_data=False, no extra users must be created."""
        payload = {**VALID_SETUP_PAYLOAD, "create_sample_data": False}
        self.client.post(
            setup_url("setup/complete"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        # Only the admin user should exist — no teachers or students
        self.assertEqual(Teacher.objects.count(), 0)
        self.assertEqual(Student.objects.count(), 0)


# ---------------------------------------------------------------------------
# SetupStatus model unit tests
# ---------------------------------------------------------------------------


class SetupStatusModelTests(TestCase):
    def test_is_setup_complete_returns_false_when_no_row(self):
        self.assertFalse(SetupStatus.is_setup_complete())

    def test_is_setup_complete_returns_false_when_incomplete(self):
        SetupStatus.objects.create(is_completed=False)
        self.assertFalse(SetupStatus.is_setup_complete())

    def test_is_setup_complete_returns_true_when_done(self):
        SetupStatus.objects.create(is_completed=True)
        self.assertTrue(SetupStatus.is_setup_complete())

    def test_mark_complete_sets_timestamp(self):
        s = SetupStatus.objects.create(is_completed=False)
        self.assertIsNone(s.completed_at)
        s.mark_complete()
        s.refresh_from_db()
        self.assertTrue(s.is_completed)
        self.assertIsNotNone(s.completed_at)
