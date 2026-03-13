import os

from storages.backends.s3boto3 import S3Boto3Storage


class R2Storage(S3Boto3Storage):
    """
    Custom storage backend for Cloudflare R2 compatibility.
    Uses class attributes to avoid ImproperlyConfigured errors while forcing R2 settings.
    """

    signature_version = "s3v4"
    addressing_style = "path"
    region_name = "auto"

    def __init__(self, *args, **kwargs):
        # Load endpoint from environment if not provided
        if "endpoint_url" not in kwargs:
            kwargs["endpoint_url"] = os.getenv("AWS_S3_ENDPOINT_URL")

        super().__init__(*args, **kwargs)

    def _get_security_token(self):
        return None
