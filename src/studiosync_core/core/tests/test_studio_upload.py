import pytest
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from studiosync_core.core.models import Studio

@pytest.mark.api
@pytest.mark.django_db
class TestStudioUploadAPI:
    """Test studio cover image and logo upload functionality."""

    @pytest.fixture(autouse=True)
    def setup_method(self, db, studio):
        self.studio = studio

    def test_upload_cover_image(self, authenticated_client, studio):
        """Test uploading a cover image via PATCH."""
        url = reverse("studio-current")
        
        # Create a dummy image file
        image_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        cover_file = SimpleUploadedFile("test_cover.png", image_content, content_type="image/png")
        
        data = {"cover_image": cover_file}
        response = authenticated_client.patch(url, data, format="multipart")
        
        assert response.status_code == status.HTTP_200_OK
        studio.refresh_from_db()
        assert studio.cover_image.name.endswith("test_cover.png")
        assert "cover_image" in response.data
        assert "/media/" in response.data["cover_image"]

    def test_upload_logo(self, authenticated_client, studio):
        """Test uploading a studio logo via PATCH."""
        url = reverse("studio-current")
        
        # Create a dummy image file
        image_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        logo_file = SimpleUploadedFile("test_logo.png", image_content, content_type="image/png")
        
        data = {"logo": logo_file}
        response = authenticated_client.patch(url, data, format="multipart")
        
        assert response.status_code == status.HTTP_200_OK
        studio.refresh_from_db()
        assert studio.logo.name.endswith("test_logo.png")
        assert "logo" in response.data
        assert "/media/" in response.data["logo"]
