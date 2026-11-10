from unittest.mock import MagicMock, patch

import pytest

from services.storage_service import CloudStorageService, upload_video_to_storage


@pytest.fixture
def temp_video_file(tmp_path):
    video_path = tmp_path / "test_promo.mp4"
    video_path.write_bytes(b"dummy mp4 video bytes")
    return str(video_path)


def test_storage_unconfigured_fallback(temp_video_file):
    service = CloudStorageService()
    # Force unconfigured
    with patch.object(service, "is_configured", return_value=False):
        url = service.upload_file(temp_video_file)
        assert url == "/api/v1/videos/download/test_promo.mp4"


def test_storage_s3_upload_aws(temp_video_file):
    service = CloudStorageService()
    service.storage_config.s3_bucket_name = "editframes-bucket"
    service.storage_config.aws_region = "us-west-2"
    service.storage_config.s3_endpoint_url = None
    service.storage_config.public_url_prefix = None

    mock_s3 = MagicMock()
    with patch.object(service, "get_client", return_value=mock_s3):
        url = service.upload_file(temp_video_file, destination_key="videos/promo.mp4")

        mock_s3.upload_file.assert_called_once_with(
            Filename=temp_video_file,
            Bucket="editframes-bucket",
            Key="videos/promo.mp4",
            ExtraArgs={"ContentType": "video/mp4"},
        )
        assert (
            url
            == "https://editframes-bucket.s3.us-west-2.amazonaws.com/videos/promo.mp4"
        )


def test_storage_s3_upload_minio(temp_video_file):
    service = CloudStorageService()
    service.storage_config.s3_bucket_name = "minio-bucket"
    service.storage_config.s3_endpoint_url = "http://minio:9000"
    service.storage_config.public_url_prefix = None

    mock_s3 = MagicMock()
    with patch.object(service, "get_client", return_value=mock_s3):
        url = service.upload_file(
            temp_video_file, destination_key="videos/promo_minio.mp4"
        )

        assert url == "http://minio:9000/minio-bucket/videos/promo_minio.mp4"


def test_storage_s3_upload_cdn_prefix(temp_video_file):
    service = CloudStorageService()
    service.storage_config.s3_bucket_name = "cdn-bucket"
    service.storage_config.public_url_prefix = "https://cdn.editframes.com"

    mock_s3 = MagicMock()
    with patch.object(service, "get_client", return_value=mock_s3):
        url = service.upload_file(temp_video_file, destination_key="videos/custom.mp4")

        assert url == "https://cdn.editframes.com/videos/custom.mp4"


def test_storage_file_not_found():
    service = CloudStorageService()
    service.storage_config.s3_bucket_name = "test-bucket"
    with pytest.raises(FileNotFoundError):
        service.upload_file("nonexistent_path/fake.mp4")


def test_upload_video_to_storage_helper(temp_video_file):
    with patch(
        "services.storage_service.storage_service.upload_file",
        return_value="https://s3/test.mp4",
    ) as mock_upload:
        res = upload_video_to_storage(temp_video_file)
        assert res == "https://s3/test.mp4"
        mock_upload.assert_called_once()
