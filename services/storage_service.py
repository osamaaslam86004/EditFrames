import logging
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

from core.config import get_settings

logger = logging.getLogger(__name__)


class CloudStorageService:
    """
    S3-compatible Object Storage Adapter supporting AWS S3 and MinIO.
    Uploads generated media artifacts (.mp4) and resolves persistent object URLs.
    """

    def __init__(self):
        self.settings = get_settings()
        self.storage_config = self.settings.storage

    @property
    def bucket_name(self) -> str | None:
        return self.storage_config.s3_bucket_name

    @property
    def endpoint_url(self) -> str | None:
        return self.storage_config.s3_endpoint_url

    @property
    def region(self) -> str:
        return self.storage_config.aws_region or "us-east-1"

    @property
    def public_url_prefix(self) -> str | None:
        return self.storage_config.public_url_prefix

    def is_configured(self) -> bool:
        """Checks if S3 bucket configuration is provided."""
        return bool(self.bucket_name)

    def get_client(self) -> Any:
        """Creates and returns an active boto3 S3 client."""
        client_kwargs: dict[str, Any] = {
            "service_name": "s3",
            "region_name": self.region,
        }

        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url

        if self.storage_config.aws_access_key_id:
            client_kwargs["aws_access_key_id"] = (
                self.storage_config.aws_access_key_id.get_secret_value()
            )

        if self.storage_config.aws_secret_access_key:
            client_kwargs["aws_secret_access_key"] = (
                self.storage_config.aws_secret_access_key.get_secret_value()
            )

        return boto3.client(**client_kwargs)

    def upload_file(
        self,
        local_path: str,
        destination_key: str | None = None,
        content_type: str = "video/mp4",
    ) -> str:
        """
        Uploads a local media file to S3-compatible cloud storage.
        Returns the persistent cloud storage object URL.
        Falls back to the local API download path if cloud storage is unconfigured.
        """
        filename = os.path.basename(local_path)
        if not destination_key:
            destination_key = f"videos/{filename}"

        # Normalize key slashes
        destination_key = destination_key.lstrip("/")

        if not self.is_configured():
            logger.info(
                "Cloud storage bucket not configured; serving via local download URL."
            )
            return f"/api/v1/videos/download/{filename}"

        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Local file not found for upload: {local_path}")

        bucket = self.bucket_name
        extra_args = {"ContentType": content_type}

        try:
            s3 = self.get_client()
            logger.info(
                "Uploading %s to S3 bucket '%s' with key '%s'...",
                local_path,
                bucket,
                destination_key,
            )
            s3.upload_file(
                Filename=local_path,
                Bucket=bucket,
                Key=destination_key,
                ExtraArgs=extra_args,
            )

            # Compute public or persistent object URL
            if self.public_url_prefix:
                object_url = f"{self.public_url_prefix.rstrip('/')}/{destination_key}"
            elif self.endpoint_url:
                # Custom S3 or MinIO URL
                endpoint = self.endpoint_url.rstrip("/")
                object_url = f"{endpoint}/{bucket}/{destination_key}"
            else:
                # Standard AWS S3 URL
                object_url = (
                    f"https://{bucket}.s3.{self.region}.amazonaws.com/{destination_key}"
                )

            logger.info(
                "Successfully uploaded %s to cloud storage: %s", filename, object_url
            )
            return object_url

        except ClientError as e:
            logger.error("Failed uploading to S3: %s", str(e), exc_info=True)
            raise e


# Singleton service instance
storage_service = CloudStorageService()


def upload_video_to_storage(local_path: str, destination_key: str | None = None) -> str:
    """Convenience helper to upload rendered video and return persistent cloud URL."""
    return storage_service.upload_file(
        local_path=local_path, destination_key=destination_key, content_type="video/mp4"
    )
