from __future__ import annotations

import pytest

from s3_mcp_proxy.config import ConfigurationError, Settings


def set_valid_environment(monkeypatch) -> None:
    monkeypatch.setenv("S3_BUCKET", "grounding-bucket")
    monkeypatch.setenv("S3_PREFIX", "lab5/aws")
    monkeypatch.setenv("S3_MCP_API_KEY", "x" * 32)


def test_settings_normalize_and_bound_prefix(monkeypatch) -> None:
    set_valid_environment(monkeypatch)
    settings = Settings.from_env()
    assert settings.prefix == "lab5/aws/"
    assert settings.max_keys == 25
    assert settings.max_object_bytes == 524_288


def test_settings_reject_empty_prefix(monkeypatch) -> None:
    set_valid_environment(monkeypatch)
    monkeypatch.setenv("S3_PREFIX", " ")
    with pytest.raises(ConfigurationError, match="S3_PREFIX"):
        Settings.from_env()


def test_settings_reject_short_api_key(monkeypatch) -> None:
    set_valid_environment(monkeypatch)
    monkeypatch.setenv("S3_MCP_API_KEY", "short")
    with pytest.raises(ConfigurationError, match="32"):
        Settings.from_env()
