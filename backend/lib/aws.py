"""
AWS client helpers for S3, Bedrock, and Polly.

All clients are lazily initialized singletons.
Use the `get_*_client()` functions from service code.
"""

import asyncio

import boto3
from config import get_settings

_s3_client = None
_bedrock_client = None
_polly_client = None


def get_s3_client():
    """Returns a boto3 S3 client."""
    global _s3_client
    if _s3_client is None:
        settings = get_settings()
        if not settings.aws_enabled:
            raise RuntimeError("AWS integration is disabled")
        _s3_client = boto3.client("s3", region_name=settings.aws_region)
    return _s3_client


def get_bedrock_client():
    """Returns a boto3 Bedrock Runtime client."""
    global _bedrock_client
    if _bedrock_client is None:
        settings = get_settings()
        _bedrock_client = boto3.client(
            "bedrock-runtime", region_name=settings.aws_region
        )
    return _bedrock_client


def get_polly_client():
    """Returns a boto3 Polly client."""
    global _polly_client
    if _polly_client is None:
        settings = get_settings()
        _polly_client = boto3.client("polly", region_name=settings.polly_region)
    return _polly_client


async def upload_to_s3(key: str, body: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload bytes to S3 and return the key."""
    settings = get_settings()
    await asyncio.to_thread(
        get_s3_client().put_object,
        Bucket=settings.s3_bucket,
        Key=key,
        Body=body,
        ContentType=content_type,
    )
    return key


async def download_from_s3(key: str) -> bytes:
    """Download an object from S3 and return the raw bytes."""
    settings = get_settings()

    def read_object() -> bytes:
        response = get_s3_client().get_object(
            Bucket=settings.s3_bucket,
            Key=key,
        )
        return response["Body"].read()

    return await asyncio.to_thread(read_object)


def generate_signed_url(key: str, expires_in: int = 3600) -> str:
    """Generate a pre-signed GET URL for an S3 object."""
    settings = get_settings()
    return get_s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expires_in,
    )


async def check_s3_access() -> None:
    """Verify that the configured bucket is reachable by the backend."""
    settings = get_settings()
    await asyncio.to_thread(
        get_s3_client().head_bucket,
        Bucket=settings.s3_bucket,
    )
