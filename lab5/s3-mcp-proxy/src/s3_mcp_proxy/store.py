"""Bounded, prefix-safe S3 document operations."""

from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath
from typing import Any

from .config import Settings

_TEXT_EXTENSIONS = {
    ".csv",
    ".html",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
_TEXT_APPLICATION_TYPES = {
    "application/json",
    "application/xml",
    "application/x-yaml",
    "application/yaml",
}


class S3DocumentStore:
    """Expose one bucket/prefix without accepting bucket or credential inputs."""

    def __init__(self, settings: Settings, client: Any) -> None:
        self.settings = settings
        self.client = client

    def list_objects(
        self,
        prefix: str = "",
        *,
        max_keys: int | None = None,
        continuation_token: str | None = None,
    ) -> dict[str, Any]:
        full_prefix = self._resolve_prefix(prefix)
        requested_max = max_keys or self.settings.max_keys
        if not 1 <= requested_max <= self.settings.max_keys:
            raise ValueError(
                f"max_keys 必須介於 1 到 {self.settings.max_keys}。"
            )

        request: dict[str, Any] = {
            "Bucket": self.settings.bucket,
            "Prefix": full_prefix,
            "MaxKeys": requested_max,
        }
        if continuation_token:
            request["ContinuationToken"] = continuation_token

        response = self.client.list_objects_v2(**request)
        documents = [
            self._object_metadata_document(item)
            for item in response.get("Contents", [])
            if item.get("Key")
        ]
        return {
            "documents": documents,
            "nextContinuationToken": response.get("NextContinuationToken"),
            "isTruncated": bool(response.get("IsTruncated", False)),
        }

    def read_object(self, key: str) -> dict[str, Any]:
        full_key = self._resolve_key(key)
        metadata = self.client.head_object(
            Bucket=self.settings.bucket, Key=full_key
        )
        size = int(metadata.get("ContentLength", 0))
        if size > self.settings.max_object_bytes:
            raise ValueError(
                f"物件大小 {size} bytes 超過上限 "
                f"{self.settings.max_object_bytes} bytes。"
            )

        content_type = str(metadata.get("ContentType", "")).split(";", 1)[0].lower()
        if not self._is_text_object(full_key, content_type):
            raise ValueError(
                f"物件 {full_key!r} 不是允許的文字格式（Content-Type: "
                f"{content_type or 'unknown'}）。"
            )

        response = self.client.get_object(
            Bucket=self.settings.bucket, Key=full_key
        )
        raw = response["Body"].read(self.settings.max_object_bytes + 1)
        if len(raw) > self.settings.max_object_bytes:
            raise ValueError("物件內容超過讀取上限。")
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"物件 {full_key!r} 不是 UTF-8 文字。") from error

        document = {
            "id": full_key,
            "title": PurePosixPath(full_key).name,
            "content": content,
            "url": f"s3://{self.settings.bucket}/{full_key}",
            "metadata": {
                "bucket": self.settings.bucket,
                "key": full_key,
                "size": size,
                "contentType": content_type or None,
                "etag": str(metadata.get("ETag", "")).strip('"') or None,
                "lastModified": _format_datetime(metadata.get("LastModified")),
            },
        }
        return {"documents": [document]}

    def _resolve_prefix(self, requested: str) -> str:
        value = requested.strip().lstrip("/")
        self._reject_unsafe(value)
        if not value:
            return self.settings.prefix
        if value.startswith(self.settings.prefix):
            return value
        return f"{self.settings.prefix}{value}"

    def _resolve_key(self, requested: str) -> str:
        value = requested.strip().lstrip("/")
        self._reject_unsafe(value)
        if not value:
            raise ValueError("key 不可為空。")
        full_key = (
            value
            if value.startswith(self.settings.prefix)
            else f"{self.settings.prefix}{value}"
        )
        if not full_key.startswith(self.settings.prefix):
            raise ValueError("key 超出允許的 S3 prefix。")
        return full_key

    @staticmethod
    def _reject_unsafe(value: str) -> None:
        lowered = value.lower()
        if lowered.startswith(("s3://", "http://", "https://", "arn:")):
            raise ValueError("只接受核准 prefix 內的相對 key 或 prefix。")
        if ".." in value.split("/"):
            raise ValueError("key 或 prefix 不可包含 '..'。")

    @staticmethod
    def _is_text_object(key: str, content_type: str) -> bool:
        suffix = PurePosixPath(key).suffix.lower()
        return (
            content_type.startswith("text/")
            or content_type in _TEXT_APPLICATION_TYPES
            or suffix in _TEXT_EXTENSIONS
        )

    def _object_metadata_document(self, item: dict[str, Any]) -> dict[str, Any]:
        key = str(item["Key"])
        size = int(item.get("Size", 0))
        return {
            "id": key,
            "title": PurePosixPath(key).name,
            "content": (
                f"S3 object {key}; size={size} bytes; "
                f"lastModified={_format_datetime(item.get('LastModified')) or 'unknown'}."
            ),
            "url": f"s3://{self.settings.bucket}/{key}",
            "metadata": {
                "bucket": self.settings.bucket,
                "key": key,
                "size": size,
                "etag": str(item.get("ETag", "")).strip('"') or None,
                "lastModified": _format_datetime(item.get("LastModified")),
            },
        }


def _format_datetime(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return None
    return str(value)
