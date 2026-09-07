"""S3/MinIO object storage for webcam snapshots and handwritten answer scans.

Degrades gracefully: if MinIO is unreachable the API keeps serving and uploads fail with a
clear 503 instead of a stack trace, so a missing object store never takes an exam down.
"""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from functools import lru_cache

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger("storage")


@lru_cache
def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=Config(signature_version="s3v4", retries={"max_attempts": 2}),
    )


def ensure_bucket() -> bool:
    """Create the bucket if missing. Returns False when storage is unavailable."""
    if not settings.STORAGE_ENABLED:
        return False
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.S3_BUCKET)
        return True
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in {"404", "NoSuchBucket", "NotFound"}:
            try:
                client.create_bucket(Bucket=settings.S3_BUCKET)
                logger.info("Created bucket %s", settings.S3_BUCKET)
                return True
            except (ClientError, BotoCoreError) as create_exc:
                logger.error("Could not create bucket: %s", create_exc)
                return False
        logger.error("Bucket check failed: %s", exc)
        return False
    except BotoCoreError as exc:
        logger.warning("Object storage unreachable at %s: %s", settings.S3_ENDPOINT_URL, exc)
        return False


def build_key(*, prefix: str, session_id: uuid.UUID, extension: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    return f"{prefix}/{session_id}/{stamp}-{uuid.uuid4().hex[:8]}.{extension.lstrip('.')}"


def put_object(*, key: str, data: bytes, content_type: str) -> str:
    if not settings.STORAGE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="File storage is disabled on this deployment",
        )
    try:
        get_s3_client().upload_fileobj(
            io.BytesIO(data),
            settings.S3_BUCKET,
            key,
            ExtraArgs={"ContentType": content_type},
        )
    except (ClientError, BotoCoreError) as exc:
        logger.error("Upload failed for %s: %s", key, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="File storage is currently unavailable",
        ) from exc
    return key


def presigned_url(key: str | None, expires: int | None = None) -> str | None:
    """Time-limited read URL, used by the examiner review panel."""
    if not key or not settings.STORAGE_ENABLED:
        return None
    try:
        return get_s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": key},
            ExpiresIn=expires or settings.S3_PRESIGN_EXPIRE_SECONDS,
        )
    except (ClientError, BotoCoreError) as exc:
        logger.warning("Could not presign %s: %s", key, exc)
        return None


def get_object_bytes(key: str) -> bytes | None:
    """Fetch an object - used when a grader needs to read a handwritten answer image."""
    try:
        response = get_s3_client().get_object(Bucket=settings.S3_BUCKET, Key=key)
        return response["Body"].read()
    except (ClientError, BotoCoreError) as exc:
        logger.warning("Could not read %s: %s", key, exc)
        return None
