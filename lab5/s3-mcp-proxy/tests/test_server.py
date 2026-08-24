from __future__ import annotations

import asyncio

from mcp import Client

from s3_mcp_proxy.config import Settings
from s3_mcp_proxy.server import _is_authorized, build_server
from test_store import FakeS3


def settings() -> Settings:
    return Settings(
        bucket="grounding-bucket",
        prefix="lab5/aws/",
        region="ap-northeast-1",
        api_key="x" * 32,
        max_keys=25,
        max_object_bytes=1024,
    )


def test_server_exposes_only_two_read_tools() -> None:
    async def run() -> None:
        async with Client(build_server(settings(), FakeS3())) as client:
            result = await client.list_tools()
            assert [tool.name for tool in result.tools] == [
                "list_objects",
                "read_object",
            ]
            read_result = await client.call_tool(
                "read_object", {"key": "aws-operations.md"}
            )
            assert "CEDAR-S3-814" in str(read_result.structured_content)

    asyncio.run(run())


def test_bearer_header_validation_is_exact() -> None:
    api_key = "x" * 32
    assert _is_authorized(
        [(b"authorization", f"Bearer {api_key}".encode())], api_key
    )
    assert not _is_authorized(
        [(b"authorization", f"Bearer {api_key}extra".encode())], api_key
    )
