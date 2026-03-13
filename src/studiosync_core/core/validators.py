"""
File Upload Validators and Utilities

Provides security validation for all file uploads including:
- File size limits
- File type validation
- Filename sanitization
- Malicious file detection
"""

import mimetypes
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible


@deconstructible
class FileValidator:
    """
    Validates uploaded files for size and type

    Usage:
        validate_avatar = FileValidator(
            max_size=settings.MAX_AVATAR_SIZE,
            allowed_extensions=settings.ALLOWED_IMAGE_EXTENSIONS
        )
    """

    def __init__(self, max_size=None, allowed_extensions=None, allowed_mimetypes=None):
        self.max_size = max_size
        self.allowed_extensions = allowed_extensions or []
        self.allowed_mimetypes = allowed_mimetypes or []

    def __call__(self, file):
        # Validate file size
        if self.max_size and file.size > self.max_size:
            max_size_mb = self.max_size / (1024 * 1024)
            raise ValidationError(
                f"File size must be under {max_size_mb:.1f}MB. Current size: {file.size / (1024 * 1024):.1f}MB"
            )

        # Validate file extension
        if self.allowed_extensions:
            ext = os.path.splitext(file.name)[1].lower()
            if ext not in self.allowed_extensions:
                raise ValidationError(
                    f'File type "{ext}" is not allowed. Allowed types: {", ".join(self.allowed_extensions)}'
                )

        # Validate MIME type
        if self.allowed_mimetypes:
            mime_type = mimetypes.guess_type(file.name)[0]
            if mime_type not in self.allowed_mimetypes:
                raise ValidationError(f'File MIME type "{mime_type}" is not allowed.')

        # Basic malicious file detection
        self._check_malicious_content(file)

    def _check_malicious_content(self, file):
        """Basic check for malicious content"""
        # Read first 1KB to check for suspicious patterns
        try:
            file.seek(0)
            header = file.read(1024)
            file.seek(0)

            # Check for executable signatures
            dangerous_signatures = [
                b"MZ",  # Windows executable
                b"\x7fELF",  # Linux executable
                b"#!/",  # Shell script
                b"<?php",  # PHP script
            ]

            for signature in dangerous_signatures:
                if header.startswith(signature):
                    raise ValidationError(
                        "File appears to contain executable code and cannot be uploaded."
                    )
        except Exception as e:
            # If we can't read the file, reject it
            if isinstance(e, ValidationError):
                raise
            raise ValidationError("Unable to validate file content.") from None


def sanitize_filename(filename):
    """
    Sanitize filename to prevent directory traversal and other attacks

    Args:
        filename: Original filename

    Returns:
        Sanitized filename safe for storage
    """
    # Get the base name (removes any path components)
    filename = os.path.basename(filename)

    # Replace spaces and special characters
    filename = filename.replace(" ", "_")

    # Remove any characters that aren't alphanumeric, dash, underscore, or dot
    import re

    filename = re.sub(r"[^a-zA-Z0-9._-]", "", filename)

    # Ensure filename isn't empty
    if not filename or filename == ".":
        filename = "unnamed_file"

    return filename


# Pre-configured validators for common use cases
validate_avatar = FileValidator(
    max_size=getattr(settings, "MAX_AVATAR_SIZE", 5 * 1024 * 1024),
    allowed_extensions=getattr(
        settings, "ALLOWED_IMAGE_EXTENSIONS", [".jpg", ".jpeg", ".png", ".gif", ".webp"]
    ),
)

validate_image = FileValidator(
    max_size=getattr(settings, "MAX_AVATAR_SIZE", 5 * 1024 * 1024),
    allowed_extensions=getattr(
        settings, "ALLOWED_IMAGE_EXTENSIONS", [".jpg", ".jpeg", ".png", ".gif", ".webp"]
    ),
)

validate_document = FileValidator(
    max_size=getattr(settings, "MAX_DOCUMENT_SIZE", 10 * 1024 * 1024),
    allowed_extensions=getattr(
        settings, "ALLOWED_DOCUMENT_EXTENSIONS", [".pdf", ".doc", ".docx", ".txt"]
    ),
)

validate_media = FileValidator(
    max_size=getattr(settings, "MAX_MEDIA_SIZE", 50 * 1024 * 1024),
    allowed_extensions=(
        getattr(settings, "ALLOWED_AUDIO_EXTENSIONS", [])
        + getattr(settings, "ALLOWED_VIDEO_EXTENSIONS", [])
    ),
)
