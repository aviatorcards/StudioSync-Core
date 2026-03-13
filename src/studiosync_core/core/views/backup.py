import json
import logging
import os
import shutil
import tempfile
import traceback
from datetime import datetime

logger = logging.getLogger(__name__)

from django.conf import settings
from django.core.management import call_command
from django.http import FileResponse, HttpResponse
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([IsAdminUser])
def export_system(request):
    """
    Export the entire system data and media files for migration.
    Creates a ZIP file containing:
    - db_dump.json: Full database dump
    - media/: All media files (if local storage)
    - manifest.json: Metadata about the export
    """
    # Create a temporary directory for the export
    with tempfile.TemporaryDirectory() as temp_dir:
        # 1. Create database dump
        db_dump_path = os.path.join(temp_dir, "db_dump.json")
        with open(db_dump_path, "w") as f:
            call_command("dumpdata", exclude=["contenttypes", "auth.Permission"], indent=2, stdout=f)

        # 2. Copy media files (only if using local FileSystemStorage)
        using_local_storage = not getattr(settings, "AWS_ACCESS_KEY_ID", None)
        if using_local_storage and os.path.exists(settings.MEDIA_ROOT):
            media_dest = os.path.join(temp_dir, "media")
            shutil.copytree(settings.MEDIA_ROOT, media_dest, dirs_exist_ok=True)

        # 3. Create manifest
        manifest = {
            "exported_at": timezone.now().isoformat(),
            "exported_by": request.user.email,
            "site_name": getattr(settings, "SITE_NAME", "StudioSync"),
            "using_local_storage": using_local_storage,
            "version": "1.0",
        }
        with open(os.path.join(temp_dir, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2)

        # 4. Create ZIP archive
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_base_name = f"studiosync_export_{timestamp}"
        archive_path = shutil.make_archive(
            os.path.join(tempfile.gettempdir(), archive_base_name), "zip", temp_dir
        )

        # 5. Return the file
        response = FileResponse(open(archive_path, "rb"), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{archive_base_name}.zip"'
        
        # Note: We should probably delete the archive_path after sending, 
        # but FileResponse doesn't make that easy without a custom wrapper.
        # For simplicity in this script, we'll leave it in temp.
        
        return response


@api_view(["POST"])
@permission_classes([IsAdminUser])
def import_system(request):
    """
    Import system data from a previously exported ZIP file.
    WARNING: This will overwrite existing data.
    """
    if "file" not in request.FILES:
        return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

    backup_file = request.FILES["file"]
    
    # Check extension
    if not backup_file.name.endswith(".zip"):
        return Response({"error": "Only ZIP files are supported"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save uploaded file to temp
            zip_path = os.path.join(temp_dir, "backup.zip")
            with open(zip_path, "wb") as f:
                for chunk in backup_file.chunks():
                    f.write(chunk)

            # Extract
            extract_dir = os.path.join(temp_dir, "extract")
            shutil.unpack_archive(zip_path, extract_dir)

            # Validate manifest
            manifest_path = os.path.join(extract_dir, "manifest.json")
            if not os.path.exists(manifest_path):
                return Response({"error": "Invalid export: manifest.json missing"}, status=status.HTTP_400_BAD_REQUEST)

            # 1. Restore Media (if applicable)
            media_src = os.path.join(extract_dir, "media")
            using_local_storage = not getattr(settings, "AWS_ACCESS_KEY_ID", None)
            if using_local_storage and os.path.exists(media_src):
                shutil.copytree(media_src, settings.MEDIA_ROOT, dirs_exist_ok=True)

            # 2. Restore Database
            db_dump_path = os.path.join(extract_dir, "db_dump.json")
            if not os.path.exists(db_dump_path):
                return Response({"error": "Invalid export: db_dump.json missing"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                call_command(
                    "loaddata",
                    db_dump_path,
                    ignorenonexistent=True,
                    verbosity=0,
                )
            except Exception as e:
                tb = traceback.format_exc()
                logger.error("loaddata failed during import:\n%s", tb)
                return Response(
                    {"error": f"Database restore failed: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

    except Exception as e:
        tb = traceback.format_exc()
        logger.error("Unexpected error during system import:\n%s", tb)
        return Response(
            {"error": f"Import failed: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response({"message": "System restored successfully"})
