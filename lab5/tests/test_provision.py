from __future__ import annotations

from foundry_iq.provision import (
    SEARCH_API_VERSION,
    Settings,
    _redact,
    build_blob_knowledge_source,
    build_gcs_knowledge_source,
    build_knowledge_base,
    build_project_connection,
    build_s3_knowledge_source,
    render_toolbox,
    validate_remote_definitions,
)


def settings() -> Settings:
    return Settings(
        search_endpoint="https://search-example.search.windows.net",
        storage_resource_id=(
            "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Storage/"
            "storageAccounts/store"
        ),
        blob_container="grounding",
        blob_folder="lab5/azure",
        openai_endpoint="https://foundry.services.ai.azure.com",
        chat_deployment="chat-deployment",
        chat_model="gpt-5.4-mini",
        embedding_deployment="embedding-deployment",
        embedding_model="text-embedding-3-large",
        foundry_project_resource_id=(
            "/subscriptions/sub/resourceGroups/rg/providers/"
            "Microsoft.CognitiveServices/accounts/foundry/projects/project"
        ),
        gcs_connection_id=(
            "/subscriptions/sub/resourceGroups/rg/providers/"
            "Microsoft.CognitiveServices/accounts/foundry/projects/project/"
            "connections/gcs-oauth"
        ),
        s3_mcp_server_url="https://s3-mcp.example.com/mcp",
        s3_mcp_api_key="x" * 32,
        blob_source_name="cross-cloud-blob-ks",
        gcs_source_name="cross-cloud-gcs-ks",
        s3_source_name="cross-cloud-s3-ks",
        knowledge_base_name="cross-cloud-grounding-kb",
        kb_connection_name="cross-cloud-kb-mcp",
    )


def test_blob_source_uses_native_indexed_pipeline() -> None:
    payload = build_blob_knowledge_source(settings())
    assert payload["kind"] == "azureBlob"
    assert payload["azureBlobParameters"]["connectionString"].startswith("ResourceId=")
    ingestion = payload["azureBlobParameters"]["ingestionParameters"]
    assert ingestion["contentExtractionMode"] == "minimal"
    assert ingestion["embeddingModel"]["kind"] == "azureOpenAI"


def test_mcp_sources_expose_only_read_tools_and_bound_outputs() -> None:
    lab_settings = settings()
    gcs = build_gcs_knowledge_source(lab_settings)
    s3 = build_s3_knowledge_source(lab_settings)

    assert [tool["name"] for tool in gcs["mcpServerParameters"]["tools"]] == [
        "list_objects",
        "read_object",
        "get_object_metadata",
    ]
    assert [tool["name"] for tool in s3["mcpServerParameters"]["tools"]] == [
        "list_objects",
        "read_object",
    ]
    assert all(
        tool["inclusionMode"] == "reranked"
        and 0 < tool["maxOutputTokens"] <= 2400
        for payload in (gcs, s3)
        for tool in payload["mcpServerParameters"]["tools"]
    )
    assert (
        gcs["mcpServerParameters"]["authentication"]["kind"]
        == "foundryConnection"
    )
    assert (
        s3["mcpServerParameters"]["authentication"]["kind"] == "storedHeaders"
    )


def test_combined_kb_and_remote_tool_connection() -> None:
    lab_settings = settings()
    kb = build_knowledge_base(lab_settings)
    connection = build_project_connection(lab_settings)

    assert kb["retrievalReasoningEffort"] == {"kind": "low"}
    assert kb["outputMode"] == "answerSynthesis"
    assert [item["name"] for item in kb["knowledgeSources"]] == [
        "cross-cloud-blob-ks",
        "cross-cloud-s3-ks",
        "cross-cloud-gcs-ks",
    ]
    assert connection["properties"]["authType"] == "ProjectManagedIdentity"
    assert connection["properties"]["audience"] == "https://search.azure.com/"
    assert SEARCH_API_VERSION in connection["properties"]["target"]


def test_plan_redacts_s3_bearer_secret() -> None:
    payload = build_s3_knowledge_source(settings())
    redacted = _redact(payload)
    headers = redacted["mcpServerParameters"]["authentication"][
        "storedHeadersParameters"
    ]["headers"]
    assert headers["Authorization"] == "<redacted>"


def test_rendered_toolbox_allows_only_kb_retrieve() -> None:
    rendered = render_toolbox(settings())
    assert "allowed_tools:\n      - knowledge_base_retrieve" in rendered
    assert "aws___run_script" not in rendered


def test_remote_definition_validation_detects_tool_expansion() -> None:
    lab_settings = settings()
    blob = build_blob_knowledge_source(lab_settings)
    gcs = build_gcs_knowledge_source(lab_settings)
    s3 = build_s3_knowledge_source(lab_settings)
    kb = build_knowledge_base(lab_settings)
    connection = build_project_connection(lab_settings)

    validate_remote_definitions(
        lab_settings, blob, gcs, s3, kb, connection
    )

    s3["mcpServerParameters"]["tools"].append({"name": "delete_object"})
    import pytest

    with pytest.raises(RuntimeError, match="S3 tools"):
        validate_remote_definitions(
            lab_settings, blob, gcs, s3, kb, connection
        )
