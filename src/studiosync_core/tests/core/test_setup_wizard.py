"""
Tests for setup wizard functionality.
"""

from django.urls import reverse

import pytest
from rest_framework import status

from studiosync_core.core.models import Studio


@pytest.mark.unit
@pytest.mark.django_db
class TestSetupWizard:
    """Test setup wizard endpoints."""

    def test_check_setup_status_incomplete(self, api_client):
        """Test setup status returns incomplete when no studio exists."""
        url = reverse("check-setup-status")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_complete"] is False

    def test_check_setup_status_complete(self, api_client, studio):
        """Test setup status returns complete when studio exists."""
        url = reverse("check-setup-status")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_complete"] is True

    def test_complete_setup_wizard_success(self, authenticated_client):
        """Test successful completion of setup wizard."""
        url = reverse("complete-setup-wizard")
        data = {
            "studio": {
                "name": "New Music Studio",
                "email": "newstudio@test.com",
                "phone": "555-0123",
                "address_line1": "456 Music Ave",
                "city": "Music City",
                "state": "MC",
                "zip_code": "12345",
            },
            "admin": {"first_name": "Admin", "last_name": "User"},
        }
        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert Studio.objects.filter(name="New Music Studio").exists()

    def test_complete_setup_wizard_missing_data(self, authenticated_client):
        """Test setup wizard fails with missing required data."""
        url = reverse("complete-setup-wizard")
        data = {
            "studio": {
                "name": "Incomplete Studio"
                # Missing required fields
            }
        }
        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_complete_setup_wizard_unauthorized(self, api_client):
        """Test setup wizard requires authentication."""
        url = reverse("complete-setup-wizard")
        data = {"studio": {"name": "Test Studio", "email": "test@test.com"}}
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
