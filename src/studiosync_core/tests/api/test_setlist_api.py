"""
Tests for Setlist API functionality
"""

import pytest
from rest_framework import status

from studiosync_core.resources.models import Resource, Setlist


@pytest.mark.django_db
class TestSetlistAPI:
    """Test suite for setlist-specific functionality"""

    def test_create_setlist(self, teacher_authenticated_client):
        """Test creating a new setlist"""
        data = {
            "name": "My First Setlist",
            "description": "A collection of my favorite songs.",
        }

        response = teacher_authenticated_client.post(
            "/api/resources/setlists/", data, format="json"
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "My First Setlist"
        assert Setlist.objects.count() == 1

    def test_add_resource_to_setlist(self, teacher_authenticated_client, teacher_user):
        """Test adding a resource to a setlist"""
        studio = teacher_user.teacher_profile.studio
        resource = Resource.objects.create(
            studio=studio,
            uploaded_by=teacher_user,
            title="Test Resource",
            resource_type="sheet_music",
            instrument="Piano",
        )
        # Create a setlist
        setlist = Setlist.objects.create(
            studio=studio,
            created_by=teacher_user,
            name="Test Setlist",
        )

        data = {
            "resource_id": str(resource.id),
        }

        response = teacher_authenticated_client.post(
            f"/api/resources/setlists/{setlist.id}/add-resource/", data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["resources"]) == 1
        assert response.data["resources"][0]["resource"]["id"] == str(resource.id)

    def test_list_setlists(self, teacher_authenticated_client, teacher_user):
        """Test listing setlists"""
        studio = teacher_user.teacher_profile.studio
        Setlist.objects.create(
            studio=studio,
            created_by=teacher_user,
            name="Test Setlist 1",
        )
        Setlist.objects.create(
            studio=studio,
            created_by=teacher_user,
            name="Test Setlist 2",
        )

        response = teacher_authenticated_client.get("/api/resources/setlists/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2
