"""
Tests for the export/import (backup & restore) views.
"""
import zipfile
from io import BytesIO

import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
class TestExportSystem:
    """Test the GET /core/system/export/ endpoint."""

    def test_export_requires_auth(self, api_client):
        url = reverse("system-export")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_export_requires_admin(self, teacher_authenticated_client):
        url = reverse("system-export")
        response = teacher_authenticated_client.get(url)
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

    def test_export_returns_zip(self, authenticated_client, studio):
        url = reverse("system-export")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.get("Content-Type") == "application/zip"

    def test_export_zip_contains_required_files(self, authenticated_client, studio):
        url = reverse("system-export")
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK

        # Load ZIP from response content
        content = b"".join(response.streaming_content)
        with zipfile.ZipFile(BytesIO(content)) as zf:
            names = zf.namelist()
            assert "db_dump.json" in names, f"db_dump.json missing from zip: {names}"
            assert "manifest.json" in names, f"manifest.json missing from zip: {names}"

    def test_export_manifest_has_correct_fields(self, authenticated_client, studio):
        import json

        url = reverse("system-export")
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK

        content = b"".join(response.streaming_content)
        with zipfile.ZipFile(BytesIO(content)) as zf:
            manifest = json.loads(zf.read("manifest.json"))

        assert "exported_at" in manifest
        assert "exported_by" in manifest
        assert "version" in manifest
        assert manifest["version"] == "1.0"


@pytest.mark.django_db
class TestImportSystem:
    """Test the POST /core/system/import/ endpoint."""

    def _build_zip(self, db_content=None, include_manifest=True):
        """Build a minimal valid backup ZIP in memory."""
        import json

        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            if db_content is None:
                db_content = "[]"
            zf.writestr("db_dump.json", db_content)
            if include_manifest:
                manifest = {
                    "version": "1.0",
                    "using_local_storage": False,
                    "exported_at": "2026-01-01T00:00:00+00:00",
                    "exported_by": "test@test.com",
                    "site_name": "StudioSync",
                }
                zf.writestr("manifest.json", json.dumps(manifest))
        buf.seek(0)
        return buf

    def test_import_requires_auth(self, api_client):
        url = reverse("system-import")
        response = api_client.post(url, {"file": BytesIO(b"fake")})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_import_requires_admin(self, teacher_authenticated_client):
        url = reverse("system-import")
        response = teacher_authenticated_client.post(
            url, {"file": self._build_zip()}, format="multipart"
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

    def test_import_rejects_missing_file(self, authenticated_client):
        url = reverse("system-import")
        response = authenticated_client.post(url, {}, format="multipart")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data

    def test_import_rejects_non_zip(self, authenticated_client):
        url = reverse("system-import")
        from django.core.files.uploadedfile import SimpleUploadedFile

        fake_file = SimpleUploadedFile("backup.txt", b"not a zip", content_type="text/plain")
        response = authenticated_client.post(url, {"file": fake_file}, format="multipart")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_import_rejects_zip_without_manifest(self, authenticated_client):
        url = reverse("system-import")
        zip_buf = self._build_zip(include_manifest=False)
        from django.core.files.uploadedfile import SimpleUploadedFile

        fake_file = SimpleUploadedFile("backup.zip", zip_buf.read(), content_type="application/zip")
        response = authenticated_client.post(url, {"file": fake_file}, format="multipart")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "manifest" in response.data.get("error", "").lower()

    def test_import_succeeds_with_empty_dump(self, authenticated_client, studio):
        url = reverse("system-import")
        zip_buf = self._build_zip(db_content="[]")
        from django.core.files.uploadedfile import SimpleUploadedFile

        fake_file = SimpleUploadedFile("backup.zip", zip_buf.read(), content_type="application/zip")
        response = authenticated_client.post(url, {"file": fake_file}, format="multipart")
        assert response.status_code == status.HTTP_200_OK
        assert "message" in response.data

    def test_export_then_import_round_trip(self, authenticated_client, studio):
        """Export the current data and then immediately import it back."""
        export_url = reverse("system-export")
        import_url = reverse("system-import")

        # Export
        export_response = authenticated_client.get(export_url)
        assert export_response.status_code == status.HTTP_200_OK
        zip_bytes = b"".join(export_response.streaming_content)

        # Import the exported zip back
        from django.core.files.uploadedfile import SimpleUploadedFile

        backup_file = SimpleUploadedFile("backup.zip", zip_bytes, content_type="application/zip")
        import_response = authenticated_client.post(
            import_url, {"file": backup_file}, format="multipart"
        )
        assert import_response.status_code == status.HTTP_200_OK, (
            f"Import failed: {import_response.data}"
        )
