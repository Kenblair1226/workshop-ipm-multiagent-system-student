"""Streamable HTTP MCP server exposing only bounded S3 read operations."""

from __future__ import annotations

import secrets
from typing import Any

import boto3
import uvicorn
from botocore.config import Config as BotoConfig
from dotenv import load_dotenv
from mcp.server import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .config import Settings
from .store import S3DocumentStore


def create_s3_client(settings: Settings) -> Any:
    options: dict[str, Any] = {
        "config": BotoConfig(
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=30,
        )
    }
    if settings.region:
        options["region_name"] = settings.region
    return boto3.client("s3", **options)


def build_server(settings: Settings, s3_client: Any | None = None) -> MCPServer:
    store = S3DocumentStore(settings, s3_client or create_s3_client(settings))
    server = MCPServer(
        name="s3-read-only-grounding",
        description="Prefix-bound, read-only S3 document access for Foundry IQ.",
        instructions=(
            "Use list_objects to discover keys under the fixed prefix, then "
            "read_object for one UTF-8 text object. No write or generic AWS tool exists."
        ),
    )

    @server.tool()
    def list_objects(
        prefix: str = "",
        max_keys: int | None = None,
        continuation_token: str | None = None,
    ) -> dict[str, Any]:
        """List metadata for objects under the server's fixed bucket and prefix."""
        return store.list_objects(
            prefix,
            max_keys=max_keys,
            continuation_token=continuation_token,
        )

    @server.tool()
    def read_object(key: str) -> dict[str, Any]:
        """Read one bounded UTF-8 text object under the fixed prefix."""
        return store.read_object(key)

    @server.custom_route("/healthz", methods=["GET"])
    async def health(_: Request) -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "service": "s3-read-only-grounding",
                "tools": ["list_objects", "read_object"],
            }
        )

    return server


def _is_authorized(headers: list[tuple[bytes, bytes]], api_key: str) -> bool:
    expected = f"Bearer {api_key}".encode()
    for name, value in headers:
        if name.lower() == b"authorization":
            return secrets.compare_digest(value, expected)
    return False


class BearerAuthApp:
    """Require one static bearer token on MCP routes while keeping health public."""

    def __init__(self, app: ASGIApp, api_key: str) -> None:
        self.app = app
        self.api_key = api_key

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if (
            scope["type"] == "http"
            and scope.get("path") != "/healthz"
            and not _is_authorized(scope.get("headers", []), self.api_key)
        ):
            response = JSONResponse(
                {"error": "unauthorized"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


def create_application(
    settings: Settings, s3_client: Any | None = None
) -> BearerAuthApp:
    server = build_server(settings, s3_client)
    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        host=settings.host,
    )
    return BearerAuthApp(app, settings.api_key)


def main() -> None:
    load_dotenv()
    settings = Settings.from_env()
    uvicorn.run(
        create_application(settings),
        host=settings.host,
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
