from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO

import pytest

from s3_mcp_proxy.config import Settings
from s3_mcp_proxy.store import S3DocumentStore


class FakeS3:
    def __init__(self) -> None:
        self.list_request = None
        self.head_request = None
        self.get_request = None

    def list_objects_v2(self, **kwargs):
        self.list_request = kwargs
        return {
            "Contents": [
                {
                    "Key": "lab5/aws/aws-operations.md",
                    "Size": 100,
                    "ETag": '"etag"',
                    "LastModified": datetime(2026, 8, 23, tzinfo=UTC),
                }
            ],
            "IsTruncated": False,
        }

    def head_object(self, **kwargs):
        self.head_request = kwargs
        return {
            "ContentLength": 28,
            "ContentType": "text/markdown",
            "ETag": '"etag"',
            "LastModified": datetime(2026, 8, 23, tzinfo=UTC),
        }

    def get_object(self, **kwargs):
        self.get_request = kwargs
        return {"Body": BytesIO("驗證代碼 CEDAR-S3-814".encode())}


def settings() -> Settings:
    return Settings(
        bucket="grounding-bucket",
        prefix="lab5/aws/",
        region="ap-northeast-1",
        api_key="x" * 32,
        max_keys=25,
        max_object_bytes=1024,
    )


def test_list_objects_cannot_escape_fixed_prefix() -> None:
    fake = FakeS3()
    store = S3DocumentStore(settings(), fake)
    result = store.list_objects("reports/")

    assert fake.list_request["Bucket"] == "grounding-bucket"
    assert fake.list_request["Prefix"] == "lab5/aws/reports/"
    assert result["documents"][0]["id"] == "lab5/aws/aws-operations.md"


def test_read_object_returns_rankable_document() -> None:
    fake = FakeS3()
    result = S3DocumentStore(settings(), fake).read_object("aws-operations.md")

    document = result["documents"][0]
    assert document["id"] == "lab5/aws/aws-operations.md"
    assert "CEDAR-S3-814" in document["content"]
    assert document["url"] == "s3://grounding-bucket/lab5/aws/aws-operations.md"


@pytest.mark.parametrize(
    "key", ["s3://other-bucket/file.txt", "../outside.txt", "https://example/file"]
)
def test_read_object_rejects_external_or_traversal_keys(key: str) -> None:
    with pytest.raises(ValueError):
        S3DocumentStore(settings(), FakeS3()).read_object(key)


def test_read_object_rejects_oversized_content() -> None:
    class Oversized(FakeS3):
        def head_object(self, **kwargs):
            return {"ContentLength": 2048, "ContentType": "text/plain"}

    with pytest.raises(ValueError, match="超過上限"):
        S3DocumentStore(settings(), Oversized()).read_object("large.txt")
