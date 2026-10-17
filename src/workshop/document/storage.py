"""S3/MinIO storage adapter with pre-signed upload/download URLs.

Keys are namespaced per tenant:
`workshop/{tenantId}/{projectId}/documents/{documentId}/{versionId}/{fileName}`
"""

from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from workshop.common.errors import NotFoundError
from workshop.settings import get_settings


@lru_cache
def _client() -> Any:
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        config=Config(s3={"addressing_style": "path" if settings.s3_force_path_style else "auto"}),
    )


def build_key(
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    file_name: str,
) -> str:
    safe_name = file_name.replace("/", "_")
    return f"workshop/{tenant_id}/{project_id}/documents/{document_id}/{version_id}/{safe_name}"


def presigned_put_url(key: str, *, content_type: str, expires_in: int | None = None) -> str:
    settings = get_settings()
    return str(
        _client().generate_presigned_url(
            "put_object",
            Params={"Bucket": settings.s3_bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_in or settings.s3_presign_ttl_seconds,
        )
    )


def presigned_get_url(key: str, *, expires_in: int | None = None) -> str:
    settings = get_settings()
    return str(
        _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": key},
            ExpiresIn=expires_in or settings.s3_presign_ttl_seconds,
        )
    )


def object_exists(key: str) -> bool:
    settings = get_settings()
    try:
        _client().head_object(Bucket=settings.s3_bucket, Key=key)
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise


def download_bytes(key: str) -> bytes:
    settings = get_settings()
    try:
        response = _client().get_object(Bucket=settings.s3_bucket, Key=key)
    except ClientError as exc:
        raise NotFoundError(f"Object not found: {key}") from exc
    return bytes(response["Body"].read())


def upload_bytes(key: str, data: bytes, *, content_type: str) -> None:
    settings = get_settings()
    _client().put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type)


def delete_object(key: str) -> None:
    settings = get_settings()
    _client().delete_object(Bucket=settings.s3_bucket, Key=key)
