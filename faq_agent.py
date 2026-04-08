"""
faq_agent.py
------------
FAQ agent built on the Microsoft Agent Framework.
Uses Azure AI Search as a RAG data source and maintains multi-turn
conversations via AgentSession.

Usage:
    python faq_agent.py
"""

import asyncio
import os
from typing import Annotated

from agent_framework import Agent, InMemoryHistoryProvider, tool
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
FOUNDRY_ENDPOINT = os.environ["AZURE_FOUNDRY_ENDPOINT"]
FOUNDRY_MODEL = os.environ.get("AZURE_FOUNDRY_MODEL", "gpt-4o")

SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
INDEX_NAME = os.environ.get("AZURE_SEARCH_INDEX_NAME", "faq-index")

OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
EMBEDDING_DEPLOYMENT = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")

# ---------------------------------------------------------------------------
# Azure clients (initialised once at module load)
# ---------------------------------------------------------------------------
_search_credential = AzureCliCredential()

_search_client = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name=INDEX_NAME,
    credential=_search_credential,
)

# Keyless authentication via Azure CLI — no API key required for Foundry resources
_token_provider = get_bearer_token_provider(
    AzureCliCredential(),
    "https://cognitiveservices.azure.com/.default",
)

_openai_client = AzureOpenAI(
    azure_endpoint=OPENAI_ENDPOINT,
    azure_ad_token_provider=_token_provider,
    api_version="2024-10-21",
)


# ---------------------------------------------------------------------------
# RAG tool: look up FAQ entries in Azure AI Search
# ---------------------------------------------------------------------------
# NOTE: approval_mode="never_require" is for development brevity.
# Use "always_require" in production for user confirmation before tool execution.
@tool(approval_mode="never_require")
def search_faq(
    query: Annotated[str, "The question or topic to search for."],
    top: Annotated[int, "Number of results to return (default: 3)."] = 3,
) -> str:
    """
    Search the FAQ database for entries relevant to the given query.
    Returns matching questions and answers as formatted text.
    Always call this tool before answering any FAQ-related question.
    """
    # Generate an embedding for the search query
    embedding_response = _openai_client.embeddings.create(
        input=query,
        model=EMBEDDING_DEPLOYMENT,
    )
    query_vector = embedding_response.data[0].embedding

    # Hybrid search: full-text + vector + semantic reranking
    vector_query = VectorizedQuery(
        vector=query_vector,
        k=top,
        fields="question_vector",
    )

    results = _search_client.search(
        search_text=query,
        vector_queries=[vector_query],
        query_type="semantic",
        semantic_configuration_name="faq-semantic-config",
        top=top,
        select=["id", "question", "answer", "category"],
    )

    hits = list(results)

    if not hits:
        return "No matching FAQ entries found."

    formatted = []
    for hit in hits:
        formatted.append(
            f"[Category: {hit['category']}]\n"
            f"Q: {hit['question']}\n"
            f"A: {hit['answer']}"
        )

    return "\n\n---\n\n".join(formatted)


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------
SYSTEM_INSTRUCTIONS = """
You are a friendly FAQ assistant. Your job is to answer user questions
accurately and helpfully.

Rules:
- ALWAYS call the search_faq tool before answering any question.
- Answer questions solely based on the FAQ entries returned by the tool.
- If no matching FAQ entry is found, say so honestly and recommend
  the user contact human support.
- Do not hallucinate information that is not present in the FAQ results.
- Always respond in the language of the user.
- Keep answers clear and concise.
""".strip()


def create_agent() -> Agent:
    client = FoundryChatClient(
        project_endpoint=FOUNDRY_ENDPOINT,
        model=FOUNDRY_MODEL,
        credential=AzureCliCredential(),
    )

    return Agent(
        client=client,
        name="FAQAgent",
        instructions=SYSTEM_INSTRUCTIONS,
        tools=[search_faq],
        context_providers=[
            InMemoryHistoryProvider(load_messages=True),
        ],
    )


# ---------------------------------------------------------------------------
# Interactive console loop
# ---------------------------------------------------------------------------
async def run_interactive() -> None:
    print("=" * 60)
    print("  FAQ Agent started (Microsoft Agent Framework + Azure AI Search)")
    print("  Type 'exit' or press Ctrl+C to quit")
    print("=" * 60)

    agent = create_agent()
    session = agent.create_session()

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        result = await agent.run(user_input, session=session)
        print(f"\nAgent: {result}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(run_interactive())