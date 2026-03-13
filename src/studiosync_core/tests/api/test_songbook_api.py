"""
Tests for Songbook API functionality
"""

from django.core.files.uploadedfile import SimpleUploadedFile

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from studiosync_core.core.models import Studio, Teacher, User
from studiosync_core.resources.models import Resource


@pytest.mark.django_db
class TestSongbookAPI:
    """Test suite for songbook-specific resource functionality"""

    @pytest.fixture
    def setup_data(self):
        """Create test data"""
        # Create studio owner
        owner = User.objects.create_user(
            email="owner@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Owner",
            role="admin",
        )

        # Create studio
        studio = Studio.objects.create(name="Test Studio", owner=owner, email="studio@test.com")

        # Create teacher
        teacher_user = User.objects.create_user(
            email="teacher@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Teacher",
            role="teacher",
        )
        teacher = Teacher.objects.create(user=teacher_user, studio=studio)

        return {"studio": studio, "teacher_user": teacher_user, "teacher": teacher}

    def test_upload_sheet_music(self, setup_data):
        """Test uploading sheet music with music-specific fields"""
        client = APIClient()
        client.force_authenticate(user=setup_data["teacher_user"])

        # Create a fake PDF file
        pdf_file = SimpleUploadedFile(
            "test_sheet.pdf", b"fake pdf content", content_type="application/pdf"
        )

        data = {
            "title": "Für Elise",
            "description": "Classic piano piece",
            "resource_type": "sheet_music",
            "instrument": "Piano",
            "composer": "Beethoven",
            "key_signature": "A minor",
            "tempo": "Andante",
            "file": pdf_file,
        }

        response = client.post("/api/resources/library/", data, format="multipart")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "Für Elise"
        assert response.data["instrument"] == "Piano"
        assert response.data["composer"] == "Beethoven"

    def test_music_resource_requires_instrument(self, setup_data):
        """Test that music resources require instrument field"""
        client = APIClient()
        client.force_authenticate(user=setup_data["teacher_user"])

        pdf_file = SimpleUploadedFile(
            "test_chart.pdf", b"fake pdf content", content_type="application/pdf"
        )

        data = {
            "title": "Test Chart",
            "resource_type": "chord_chart",
            "file": pdf_file,
            # Missing instrument field
        }

        response = client.post("/api/resources/library/", data, format="multipart")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "instrument" in response.data

    def test_filter_by_instrument(self, setup_data):
        """Test filtering resources by instrument"""
        client = APIClient()
        client.force_authenticate(user=setup_data["teacher_user"])

        # Create piano resource
        Resource.objects.create(
            studio=setup_data["studio"],
            uploaded_by=setup_data["teacher_user"],
            title="Piano Scales",
            resource_type="sheet_music",
            instrument="Piano",
        )

        # Create guitar resource
        Resource.objects.create(
            studio=setup_data["studio"],
            uploaded_by=setup_data["teacher_user"],
            title="Guitar Chords",
            resource_type="chord_chart",
            instrument="Guitar",
        )

        # Filter by Piano
        response = client.get("/api/resources/library/?instrument=Piano")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["instrument"] == "Piano"

    def test_search_by_composer(self, setup_data):
        """Test searching resources by composer name"""
        client = APIClient()
        client.force_authenticate(user=setup_data["teacher_user"])

        Resource.objects.create(
            studio=setup_data["studio"],
            uploaded_by=setup_data["teacher_user"],
            title="Moonlight Sonata",
            resource_type="sheet_music",
            instrument="Piano",
            composer="Beethoven",
        )

        response = client.get("/api/resources/library/?search=Beethoven")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
        assert "Beethoven" in response.data[0]["composer"]
