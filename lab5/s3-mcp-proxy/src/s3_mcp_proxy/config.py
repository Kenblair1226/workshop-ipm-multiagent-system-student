"""Strict environment configuration for the S3 MCP proxy."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

_BUCKET_PATTERN = re.compile(
    r"^(?=.{3,63}$)(?!\d+\.\d+\.\d+\.\d+$)[a-z0-9]"
    r"(?:[a-z0-9.-]*[a-z0-9])$"
)


class ConfigurationError(ValueError):
    """Proxy configuration is missing or unsafe."""


@dataclass(frozen=True)
class Settings:
    bucket: str
    prefix: str
    region: str | None
    api_key: str
    max_keys: int = 25
    max_object_bytes: int = 524_288
    host: str = "127.0.0.1"
    port: int = 8000

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(
            bucket=_require("S3_BUCKET"),
            prefix=_normalize_prefix(_require("S3_PREFIX")),
            region=os.environ.get("AWS_REGION", "").strip() or None,
            api_key=_require("S3_MCP_API_KEY"),
            max_keys=_read_int("S3_MAX_KEYS", 25),
            max_object_bytes=_read_int("S3_MAX_OBJECT_BYTES", 524_288),
            host=os.environ.get("MCP_HOST", "").strip() or "127.0.0.1",
            port=_read_int("MCP_PORT", 8000),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not _BUCKET_PATTERN.fullmatch(self.bucket):
            raise ConfigurationError("S3_BUCKET 不是有效的 S3 bucket 名稱。")
        if not self.prefix or self.prefix == "/":
            raise ConfigurationError("S3_PREFIX 必須限制在非空 prefix。")
        if len(self.api_key) < 32:
            raise ConfigurationError("S3_MCP_API_KEY 至少需要 32 個字元。")
        if not 1 <= self.max_keys <= 100:
            raise ConfigurationError("S3_MAX_KEYS 必須介於 1 到 100。")
        if not 1 <= self.max_object_bytes <= 4 * 1024 * 1024:
            raise ConfigurationError(
                "S3_MAX_OBJECT_BYTES 必須介於 1 byte 到 4 MiB。"
            )
        if not 1 <= self.port <= 65_535:
            raise ConfigurationError("MCP_PORT 必須是有效 TCP port。")


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value or (value.startswith("<") and value.endswith(">")):
        raise ConfigurationError(f"必要環境變數 {name} 尚未設定。")
    return value


def _read_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as error:
        raise ConfigurationError(f"{name} 必須是整數。") from error


def _normalize_prefix(prefix: str) -> str:
    value = prefix.strip().lstrip("/")
    if value.startswith("s3://") or ".." in value.split("/"):
        raise ConfigurationError("S3_PREFIX 必須是 bucket 內的相對 prefix。")
    return value.rstrip("/") + "/"
