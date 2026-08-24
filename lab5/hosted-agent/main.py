# Copyright (c) Microsoft. All rights reserved.
"""Hosted Agent that consumes only the Foundry IQ toolbox endpoint."""

from __future__ import annotations

import asyncio
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import FoundryToolbox, ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

from settings import INSTRUCTIONS, missing_environment_variables


async def main() -> None:
    load_dotenv()
    missing = missing_environment_variables()
    if missing:
        raise RuntimeError(
            "Missing required environment variables: " + ", ".join(missing)
        )

    credential = DefaultAzureCredential()
    toolbox = FoundryToolbox(credential, name="knowledge_base")
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=credential,
    )
    agent = Agent(
        client=client,
        instructions=INSTRUCTIONS,
        tools=toolbox,
        default_options={"store": False},
    )
    server = ResponsesHostServer(agent)
    await server.run_async()


if __name__ == "__main__":
    asyncio.run(main())
