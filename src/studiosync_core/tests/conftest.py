"""
Pytest configuration and shared fixtures for all tests.
"""

from django.contrib.auth import get_user_model

import pytest
from rest_framework.test import APIClient

from studiosync_core.core.models import Student, Studio, Teacher
from studiosync_core.resources.models import Resource

User = get_user_model()


@pytest.fixture
def api_client():
    """Return an API client for making requests."""
    return APIClient()


@pytest.fixture
def admin_user(db):
    """Create and return an admin user."""
    return User.objects.create_user(
        email="admin@test.com",
        password="testpass123",
        first_name="Admin",
        last_name="User",
        role="admin",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def studio(db, admin_user):
    """Create and return a test studio."""
    return Studio.objects.create(
        name="Test Studio",
        owner=admin_user,
        email="studio@test.com",
        address_line1="123 Test St",
        city="Test City",
        state="TS",
    )


@pytest.fixture
def teacher_user(db):
    """Create and return a teacher user."""
    return User.objects.create_user(
        email="teacher@test.com",
        password="testpass123",
        first_name="Teacher",
        last_name="Test",
        role="teacher",
    )


@pytest.fixture
def teacher(db, studio, teacher_user):
    """Create and return a teacher instance."""
    return Teacher.objects.create(
        user=teacher_user, studio=studio, bio="Test teacher bio", hourly_rate=50.00
    )


@pytest.fixture
def student_user(db):
    """Create and return a student user."""
    return User.objects.create_user(
        email="student@test.com",
        password="testpass123",
        first_name="Student",
        last_name="Test",
        role="student",
    )


@pytest.fixture
def student(db, studio, teacher, student_user):
    """Create and return a student instance."""
    return Student.objects.create(
        user=student_user, studio=studio, primary_teacher=teacher, instrument="Piano"
    )


@pytest.fixture
def authenticated_client(api_client, admin_user):
    """Return an API client authenticated as admin user."""
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def teacher_authenticated_client(api_client, teacher_user):
    """Return an API client authenticated as teacher user."""
    api_client.force_authenticate(user=teacher_user)
    return api_client


@pytest.fixture
def student_authenticated_client(api_client, student_user):
    """Return an API client authenticated as student user."""
    api_client.force_authenticate(user=student_user)
    return api_client


@pytest.fixture
def resource(db, studio, teacher_user):
    """Create and return a test resource."""
    return Resource.objects.create(
        studio=studio,
        uploaded_by=teacher_user,
        title="Test Resource",
        resource_type="sheet_music",
        instrument="Piano",
    )
