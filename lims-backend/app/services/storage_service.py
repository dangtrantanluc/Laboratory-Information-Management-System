"""Storage service — MinIO/S3 qua boto3 (attachments dùng chung M1/M2/M3/M5).

Cung cấp: ensure_bucket, put_object (upload), presigned_get_url (tải), remove_object.
Interface ổn định để M1/M2 upload file (CoA/MSDS/raw data...).
"""
import logging
import uuid
from typing import Optional

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger("lims.storage")


def _client(endpoint: Optional[str] = None):
    return boto3.client(
        "s3",
        endpoint_url=endpoint or settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        region_name=settings.minio_region,
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket() -> None:
    """Tạo bucket nếu chưa có (gọi lúc startup)."""
    client = _client()
    try:
        client.head_bucket(Bucket=settings.minio_bucket)
    except ClientError:
        try:
            client.create_bucket(Bucket=settings.minio_bucket)
            logger.info("Created MinIO bucket", extra={"bucket": settings.minio_bucket})
        except ClientError as exc:
            logger.error("Cannot create bucket", extra={"error": str(exc)})


def build_object_key(owner_type: str, owner_id: uuid.UUID, file_name: str) -> str:
    """Sinh key có cấu trúc: <owner_type>/<owner_id>/<uuid>_<file_name>."""
    safe_name = file_name.replace("/", "_").replace("\\", "_")
    return f"{owner_type}/{owner_id}/{uuid.uuid4().hex}_{safe_name}"


def put_object(file_key: str, data: bytes, content_type: Optional[str] = None) -> None:
    client = _client()
    extra = {"ContentType": content_type} if content_type else {}
    client.put_object(
        Bucket=settings.minio_bucket, Key=file_key, Body=data, **extra
    )


def presigned_get_url(
    file_key: str, file_name: Optional[str] = None, inline: bool = False
) -> str:
    """Trả presigned URL TTL 15 phút (contract #30). Dùng public endpoint cho FE."""
    client = _client(endpoint=settings.minio_public_endpoint)
    params: dict = {"Bucket": settings.minio_bucket, "Key": file_key}
    if file_name:
        disposition = "inline" if inline else "attachment"
        params["ResponseContentDisposition"] = f'{disposition}; filename="{file_name}"'
    return client.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=settings.presigned_url_ttl_seconds,
    )


def remove_object(file_key: str) -> None:
    """Xóa object MinIO (dùng bởi job dọn dẹp — KHÔNG gọi trực tiếp khi soft-delete)."""
    client = _client()
    try:
        client.delete_object(Bucket=settings.minio_bucket, Key=file_key)
    except ClientError as exc:
        logger.warning("Cannot delete object", extra={"key": file_key, "error": str(exc)})
