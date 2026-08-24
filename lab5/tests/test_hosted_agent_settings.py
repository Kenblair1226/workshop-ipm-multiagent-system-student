from __future__ import annotations

import sys
from pathlib import Path

HOSTED_AGENT = Path(__file__).resolve().parents[1] / "hosted-agent"
sys.path.insert(0, str(HOSTED_AGENT))

from settings import (  # noqa: E402
    INSTRUCTIONS,
    REQUIRED_ENVIRONMENT_VARIABLES,
    missing_environment_variables,
)


def test_hosted_agent_requires_only_foundry_and_toolbox_configuration(
    monkeypatch,
) -> None:
    for name in (
        "FOUNDRY_PROJECT_ENDPOINT",
        "AZURE_AI_MODEL_DEPLOYMENT_NAME",
        "TOOLBOX_ENDPOINT",
    ):
        monkeypatch.delenv(name, raising=False)

    assert missing_environment_variables() == [
        "FOUNDRY_PROJECT_ENDPOINT",
        "AZURE_AI_MODEL_DEPLOYMENT_NAME",
        "TOOLBOX_ENDPOINT",
    ]
    assert not any(
        name.startswith(("AWS_", "GOOGLE_", "AZURE_STORAGE_"))
        for name in REQUIRED_ENVIRONMENT_VARIABLES
    )


def test_instructions_require_grounded_cited_answers() -> None:
    assert "knowledge base" in INSTRUCTIONS.lower()
    assert "citation" in INSTRUCTIONS.lower()
    assert "I don't know" in INSTRUCTIONS
