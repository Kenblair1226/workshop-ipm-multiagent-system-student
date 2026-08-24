#!/usr/bin/env python3
"""Provision the cross-cloud Foundry IQ knowledge base and its agent connection."""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

SEARCH_API_VERSION = "2026-05-01-preview"
CONNECTION_API_VERSION = "2025-10-01-preview"
SEARCH_SCOPE = "https://search.azure.com/.default"
MANAGEMENT_SCOPE = "https://management.azure.com/.default"
GCS_MCP_ENDPOINT = "https://storage.googleapis.com/storage/mcp"
_NAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,126}[a-z0-9])?$")
_SENSITIVE_KEYS = {"authorization", "api-key", "clientsecret", "secret", "token"}


class ConfigurationError(ValueError):
    """The environment cannot produce a safe, complete resource definition."""


@dataclass(frozen=True)
class Settings:
    """All variable cloud resource names and endpoints used by this lab."""

    search_endpoint: str
    storage_resource_id: str
    blob_container: str
    blob_folder: str | None
    openai_endpoint: str
    chat_deployment: str
    chat_model: str
    embedding_deployment: str
    embedding_model: str
    foundry_project_resource_id: str
    gcs_connection_id: str
    s3_mcp_server_url: str
    s3_mcp_api_key: str
    blob_source_name: str
    gcs_source_name: str
    s3_source_name: str
    knowledge_base_name: str
    kb_connection_name: str

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from environment variables after loading lab5/.env."""
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
        settings = cls(
            search_endpoint=_require("AZURE_SEARCH_ENDPOINT").rstrip("/"),
            storage_resource_id=_require("AZURE_STORAGE_RESOURCE_ID").rstrip("/"),
            blob_container=_require("AZURE_BLOB_CONTAINER"),
            blob_folder=_optional("AZURE_BLOB_FOLDER"),
            openai_endpoint=_require("AZURE_OPENAI_ENDPOINT").rstrip("/"),
            chat_deployment=_require("AZURE_AI_MODEL_DEPLOYMENT_NAME"),
            chat_model=_require("AZURE_AI_MODEL_NAME"),
            embedding_deployment=_require("AZURE_AI_EMBEDDING_DEPLOYMENT_NAME"),
            embedding_model=_require("AZURE_AI_EMBEDDING_MODEL_NAME"),
            foundry_project_resource_id=_require(
                "FOUNDRY_PROJECT_RESOURCE_ID"
            ).rstrip("/"),
            gcs_connection_id=_require("GCS_FOUNDRY_CONNECTION_ID"),
            s3_mcp_server_url=_require("S3_MCP_SERVER_URL").rstrip("/"),
            s3_mcp_api_key=_require("S3_MCP_API_KEY"),
            blob_source_name=_optional(
                "AZURE_BLOB_KNOWLEDGE_SOURCE_NAME", "cross-cloud-blob-ks"
            ),
            gcs_source_name=_optional(
                "GCS_KNOWLEDGE_SOURCE_NAME", "cross-cloud-gcs-ks"
            ),
            s3_source_name=_optional(
                "S3_KNOWLEDGE_SOURCE_NAME", "cross-cloud-s3-ks"
            ),
            knowledge_base_name=_optional(
                "KNOWLEDGE_BASE_NAME", "cross-cloud-grounding-kb"
            ),
            kb_connection_name=_optional(
                "FOUNDRY_KB_CONNECTION_NAME", "cross-cloud-kb-mcp"
            ),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        for label, endpoint in (
            ("AZURE_SEARCH_ENDPOINT", self.search_endpoint),
            ("AZURE_OPENAI_ENDPOINT", self.openai_endpoint),
            ("S3_MCP_SERVER_URL", self.s3_mcp_server_url),
        ):
            parsed = urlparse(endpoint)
            if parsed.scheme != "https" or not parsed.netloc:
                raise ConfigurationError(f"{label} 必須是完整 HTTPS URL。")

        if not self.storage_resource_id.startswith("/subscriptions/"):
            raise ConfigurationError(
                "AZURE_STORAGE_RESOURCE_ID 必須是 Storage Account 的完整 ARM resource ID。"
            )
        if not self.foundry_project_resource_id.startswith("/subscriptions/"):
            raise ConfigurationError(
                "FOUNDRY_PROJECT_RESOURCE_ID 必須是 Foundry project 的完整 ARM resource ID。"
            )
        if "/connections/" not in self.gcs_connection_id:
            raise ConfigurationError(
                "GCS_FOUNDRY_CONNECTION_ID 必須是 custom OAuth project connection 的完整 ARM resource ID。"
            )
        if len(self.s3_mcp_api_key) < 32:
            raise ConfigurationError("S3_MCP_API_KEY 至少需要 32 個字元。")

        for name in (
            self.blob_source_name,
            self.gcs_source_name,
            self.s3_source_name,
            self.knowledge_base_name,
            self.kb_connection_name,
        ):
            if not _NAME_PATTERN.fullmatch(name):
                raise ConfigurationError(
                    f"資源名稱 {name!r} 只能使用小寫英數與連字號，且首尾需為英數字。"
                )

    @property
    def kb_mcp_endpoint(self) -> str:
        return (
            f"{self.search_endpoint}/knowledgebases/{self.knowledge_base_name}/mcp"
            f"?api-version={SEARCH_API_VERSION}"
        )


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value or (value.startswith("<") and value.endswith(">")):
        raise ConfigurationError(f"必要環境變數 {name} 尚未設定。")
    return value


def _optional(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or default


def _azure_openai_model(
    endpoint: str, deployment: str, model: str
) -> dict[str, Any]:
    return {
        "kind": "azureOpenAI",
        "azureOpenAIParameters": {
            "resourceUri": endpoint,
            "deploymentId": deployment,
            "modelName": model,
        },
    }


def build_blob_knowledge_source(settings: Settings) -> dict[str, Any]:
    """Build the native indexed Blob source that creates its own ingestion pipeline."""
    return {
        "name": settings.blob_source_name,
        "kind": "azureBlob",
        "description": (
            "Indexed Azure Blob documents. Azure AI Search creates and owns the "
            "data source, skillset, indexer, and search index."
        ),
        "encryptionKey": None,
        "azureBlobParameters": {
            "connectionString": f"ResourceId={settings.storage_resource_id};",
            "containerName": settings.blob_container,
            "folderPath": settings.blob_folder,
            "isADLSGen2": False,
            "ingestionParameters": {
                "identity": None,
                "disableImageVerbalization": True,
                "chatCompletionModel": _azure_openai_model(
                    settings.openai_endpoint,
                    settings.chat_deployment,
                    settings.chat_model,
                ),
                "embeddingModel": _azure_openai_model(
                    settings.openai_endpoint,
                    settings.embedding_deployment,
                    settings.embedding_model,
                ),
                "contentExtractionMode": "minimal",
                "ingestionSchedule": None,
            },
        },
    }


def build_gcs_knowledge_source(settings: Settings) -> dict[str, Any]:
    """Build the Google Cloud Storage MCP source with only object-read tools."""
    return {
        "name": settings.gcs_source_name,
        "kind": "mcpServer",
        "description": (
            "Live, read-only Google Cloud Storage object access. Use known bucket, "
            "prefix, or object names; this source is not semantic search."
        ),
        "mcpServerParameters": {
            "serverURL": GCS_MCP_ENDPOINT,
            "authentication": {
                "kind": "foundryConnection",
                "foundryConnectionParameters": {
                    "connectionId": settings.gcs_connection_id
                },
            },
            "tools": [
                {
                    "name": "list_objects",
                    "outputParsing": {"kind": "auto"},
                    "inclusionMode": "reranked",
                    "maxOutputTokens": 1000,
                },
                {
                    "name": "read_object",
                    "outputParsing": {
                        "kind": "split",
                        "splitParameters": {
                            "textSplitMode": "pages",
                            "maximumPageLength": 2000,
                            "pageOverlapLength": 200,
                        },
                    },
                    "inclusionMode": "reranked",
                    "maxOutputTokens": 2400,
                },
                {
                    "name": "get_object_metadata",
                    "outputParsing": {"kind": "auto"},
                    "inclusionMode": "reranked",
                    "maxOutputTokens": 600,
                },
            ],
        },
    }


def build_s3_knowledge_source(settings: Settings) -> dict[str, Any]:
    """Build the narrow S3 proxy source; no generic AWS execution tool is exposed."""
    return {
        "name": settings.s3_source_name,
        "kind": "mcpServer",
        "description": (
            "Live, read-only S3 access through a prefix-bound proxy. Use known keys "
            "or prefixes; this source is not semantic search."
        ),
        "mcpServerParameters": {
            "serverURL": settings.s3_mcp_server_url,
            "authentication": {
                "kind": "storedHeaders",
                "storedHeadersParameters": {
                    "headers": {
                        "Authorization": f"Bearer {settings.s3_mcp_api_key}"
                    }
                },
            },
            "tools": [
                {
                    "name": "list_objects",
                    "outputParsing": {
                        "kind": "json",
                        "jsonParameters": {
                            "documentsPath": "$.documents[*]",
                            "includeContext": False,
                        },
                    },
                    "inclusionMode": "reranked",
                    "maxOutputTokens": 1000,
                },
                {
                    "name": "read_object",
                    "outputParsing": {
                        "kind": "json",
                        "jsonParameters": {
                            "documentsPath": "$.documents[*]",
                            "includeContext": False,
                        },
                    },
                    "inclusionMode": "reranked",
                    "maxOutputTokens": 2400,
                },
            ],
        },
    }


def build_knowledge_base(settings: Settings) -> dict[str, Any]:
    """Build one knowledge base that plans retrieval across all three clouds."""
    return {
        "name": settings.knowledge_base_name,
        "description": (
            "Orchestrated grounding over indexed Azure Blob documents and live, "
            "read-only AWS S3 and Google Cloud Storage MCP sources."
        ),
        "retrievalInstructions": (
            f"Use {settings.blob_source_name} for indexed Azure documents. "
            f"Use {settings.s3_source_name} for the approved S3 bucket and prefix. "
            f"Use {settings.gcs_source_name} for Google Cloud Storage. For an "
            "object-store source, list a narrow prefix before reading an object. "
            "For cross-cloud questions, query every relevant source and preserve "
            "which source supports each fact."
        ),
        "answerInstructions": (
            "Answer only from retrieved evidence. Cite every material claim, identify "
            "the cloud source, and say that the information was not found when no "
            "retrieved reference supports it."
        ),
        "outputMode": "answerSynthesis",
        "knowledgeSources": [
            {"name": settings.blob_source_name},
            {"name": settings.s3_source_name},
            {"name": settings.gcs_source_name},
        ],
        "models": [
            _azure_openai_model(
                settings.openai_endpoint,
                settings.chat_deployment,
                settings.chat_model,
            )
        ],
        "encryptionKey": None,
        "retrievalReasoningEffort": {"kind": "low"},
    }


def build_project_connection(settings: Settings) -> dict[str, Any]:
    """Build the Foundry RemoteTool connection used by the toolbox."""
    return {
        "name": settings.kb_connection_name,
        "type": "Microsoft.MachineLearningServices/workspaces/connections",
        "properties": {
            "authType": "ProjectManagedIdentity",
            "category": "RemoteTool",
            "target": settings.kb_mcp_endpoint,
            "isSharedToAll": True,
            "audience": "https://search.azure.com/",
            "metadata": {"ApiType": "Azure"},
        },
    }


class RestClient:
    """Small bearer-token REST client with strict success handling."""

    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def request(
        self,
        method: str,
        path: str,
        *,
        api_version: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        separator = "&" if "?" in path else "?"
        url = f"{self.base_url}/{path.lstrip('/')}{separator}api-version={api_version}"
        try:
            response = requests.request(
                method, url, headers=self.headers, json=body, timeout=120
            )
        except requests.RequestException as error:
            raise RuntimeError(f"{method} {url} 無法連線：{error}") from error
        if response.status_code not in {200, 201, 202, 204}:
            raise RuntimeError(
                f"{method} {url} 失敗 ({response.status_code})：{response.text}"
            )
        return response.json() if response.content else {}


def build_plan(settings: Settings) -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (
            "search",
            f"knowledgesources/{settings.blob_source_name}",
            build_blob_knowledge_source(settings),
        ),
        (
            "search",
            f"knowledgesources/{settings.gcs_source_name}",
            build_gcs_knowledge_source(settings),
        ),
        (
            "search",
            f"knowledgesources/{settings.s3_source_name}",
            build_s3_knowledge_source(settings),
        ),
        (
            "search",
            f"knowledgebases/{settings.knowledge_base_name}",
            build_knowledge_base(settings),
        ),
        (
            "arm",
            (
                f"{settings.foundry_project_resource_id}/connections/"
                f"{settings.kb_connection_name}"
            ),
            build_project_connection(settings),
        ),
    ]


def _redact(value: Any, key: str = "") -> Any:
    if isinstance(value, dict):
        return {item_key: _redact(item, item_key) for item_key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, key) for item in value]
    if isinstance(value, str) and key.lower() in _SENSITIVE_KEYS:
        return "<redacted>"
    return value


def print_plan(settings: Settings) -> None:
    for target, path, body in build_plan(settings):
        print(f"\n[{target}] PUT {path}")
        print(json.dumps(_redact(body), ensure_ascii=False, indent=2))
    print(f"\nKnowledge Base MCP endpoint: {settings.kb_mcp_endpoint}")


def render_toolbox(settings: Settings) -> str:
    """Render an azd toolbox definition without placing credentials in the file."""
    return "\n".join(
        [
            "description: Cross-cloud Foundry IQ knowledge base behind one curated endpoint",
            "tools:",
            "  - type: mcp",
            "    name: knowledge_base",
            "    server_label: knowledge_base",
            f"    server_url: {settings.kb_mcp_endpoint}",
            f"    project_connection_id: {settings.kb_connection_name}",
            "    allowed_tools:",
            "      - knowledge_base_retrieve",
            "    require_approval: never",
            "",
        ]
    )


def apply(settings: Settings) -> None:
    credential = DefaultAzureCredential()
    try:
        search = RestClient(
            settings.search_endpoint, credential.get_token(SEARCH_SCOPE).token
        )
        management = RestClient(
            "https://management.azure.com",
            credential.get_token(MANAGEMENT_SCOPE).token,
        )
        for target, path, body in build_plan(settings):
            client = search if target == "search" else management
            api_version = (
                SEARCH_API_VERSION
                if target == "search"
                else CONNECTION_API_VERSION
            )
            print(f"PUT {path}")
            result = client.request(
                "PUT", path, api_version=api_version, body=body
            )
            created = (
                result.get("azureBlobParameters", {}).get("createdResources")
                if target == "search"
                else None
            )
            if created:
                print("  Blob ingestion resources:", json.dumps(created))
    finally:
        credential.close()
    print(f"\n完成。KB MCP endpoint：{settings.kb_mcp_endpoint}")


def check(settings: Settings) -> None:
    credential = DefaultAzureCredential()
    try:
        search = RestClient(
            settings.search_endpoint, credential.get_token(SEARCH_SCOPE).token
        )
        management = RestClient(
            "https://management.azure.com",
            credential.get_token(MANAGEMENT_SCOPE).token,
        )
        blob = search.request(
            "GET",
            f"knowledgesources/{settings.blob_source_name}",
            api_version=SEARCH_API_VERSION,
        )
        gcs = search.request(
            "GET",
            f"knowledgesources/{settings.gcs_source_name}",
            api_version=SEARCH_API_VERSION,
        )
        s3 = search.request(
            "GET",
            f"knowledgesources/{settings.s3_source_name}",
            api_version=SEARCH_API_VERSION,
        )
        kb = search.request(
            "GET",
            f"knowledgebases/{settings.knowledge_base_name}",
            api_version=SEARCH_API_VERSION,
        )
        connection = management.request(
            "GET",
            (
                f"{settings.foundry_project_resource_id}/connections/"
                f"{settings.kb_connection_name}"
            ),
            api_version=CONNECTION_API_VERSION,
        )
        validate_remote_definitions(settings, blob, gcs, s3, kb, connection)

        status = search.request(
            "GET",
            f"knowledgesources/{settings.blob_source_name}/status",
            api_version=SEARCH_API_VERSION,
        )
        synchronization = str(status.get("synchronizationStatus", "unknown"))
        last_state = status.get("lastSynchronizationState") or {}
        last_status = str(last_state.get("status", "unknown"))
        if synchronization.lower() in {"failed", "error"} or last_status.lower() in {
            "failed",
            "error",
        }:
            raise RuntimeError(
                f"Blob ingestion 失敗：synchronizationStatus={synchronization}, "
                f"lastStatus={last_status}"
            )
        print(
            "OK Blob ingestion status: "
            f"synchronizationStatus={synchronization}, lastStatus={last_status}"
        )
    finally:
        credential.close()


def validate_remote_definitions(
    settings: Settings,
    blob: dict[str, Any],
    gcs: dict[str, Any],
    s3: dict[str, Any],
    kb: dict[str, Any],
    connection: dict[str, Any],
) -> None:
    """Fail if cloud resources exist but no longer enforce the lab's boundaries."""
    errors: list[str] = []
    if blob.get("kind") != "azureBlob":
        errors.append("Blob knowledge source kind 不是 azureBlob")

    expected_gcs = ["list_objects", "read_object", "get_object_metadata"]
    actual_gcs = [
        tool.get("name")
        for tool in gcs.get("mcpServerParameters", {}).get("tools", [])
    ]
    if actual_gcs != expected_gcs:
        errors.append(f"GCS tools 不符：{actual_gcs}")

    expected_s3 = ["list_objects", "read_object"]
    actual_s3 = [
        tool.get("name")
        for tool in s3.get("mcpServerParameters", {}).get("tools", [])
    ]
    if actual_s3 != expected_s3:
        errors.append(f"S3 tools 不符：{actual_s3}")

    expected_sources = [
        settings.blob_source_name,
        settings.s3_source_name,
        settings.gcs_source_name,
    ]
    actual_sources = [item.get("name") for item in kb.get("knowledgeSources", [])]
    if actual_sources != expected_sources:
        errors.append(f"Knowledge Base sources 不符：{actual_sources}")
    if kb.get("retrievalReasoningEffort") != {"kind": "low"}:
        errors.append("Knowledge Base retrievalReasoningEffort 不是 low")

    properties = connection.get("properties", {})
    if properties.get("authType") != "ProjectManagedIdentity":
        errors.append("RemoteTool authType 不是 ProjectManagedIdentity")
    if properties.get("audience") != "https://search.azure.com/":
        errors.append("RemoteTool audience 不正確")
    if properties.get("target") != settings.kb_mcp_endpoint:
        errors.append("RemoteTool target 不是目前 Knowledge Base MCP endpoint")

    if errors:
        raise RuntimeError("遠端設定驗證失敗：" + "；".join(errors))
    print("OK 遠端設定：三個 sources、combined KB 與 ProjectManagedIdentity connection")


def delete(settings: Settings) -> None:
    credential = DefaultAzureCredential()
    try:
        search = RestClient(
            settings.search_endpoint, credential.get_token(SEARCH_SCOPE).token
        )
        management = RestClient(
            "https://management.azure.com",
            credential.get_token(MANAGEMENT_SCOPE).token,
        )
        management.request(
            "DELETE",
            (
                f"{settings.foundry_project_resource_id}/connections/"
                f"{settings.kb_connection_name}"
            ),
            api_version=CONNECTION_API_VERSION,
        )
        search.request(
            "DELETE",
            f"knowledgebases/{settings.knowledge_base_name}",
            api_version=SEARCH_API_VERSION,
        )
        for name in (
            settings.gcs_source_name,
            settings.s3_source_name,
            settings.blob_source_name,
        ):
            search.request(
                "DELETE",
                f"knowledgesources/{name}",
                api_version=SEARCH_API_VERSION,
            )
            print(f"DELETE knowledgesources/{name}")
    finally:
        credential.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Provision the Lab 5 Foundry IQ cross-cloud knowledge base."
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="plan",
        choices=("plan", "apply", "check", "toolbox", "delete"),
    )
    args = parser.parse_args()

    try:
        settings = Settings.from_env()
        if args.command == "plan":
            print_plan(settings)
        elif args.command == "apply":
            apply(settings)
        elif args.command == "check":
            check(settings)
        elif args.command == "toolbox":
            print(render_toolbox(settings), end="")
        else:
            delete(settings)
    except (ConfigurationError, RuntimeError) as error:
        print(f"錯誤：{error}", file=os.sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
