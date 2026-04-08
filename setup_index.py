"""
setup_index.py
--------------
Creates the Azure AI Search index and uploads FAQ entries.
Re-running this script will delete and recreate the index from scratch,
ensuring the index always reflects the current state of contoso_faq.json.

Prerequisites:
    pip install -r requirements.txt
    Copy .env.example to .env and fill in your values
"""

import json
import os

from azure.identity import AzureCliCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration from environment variables
# ---------------------------------------------------------------------------
SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
INDEX_NAME = os.environ.get("AZURE_SEARCH_INDEX_NAME", "faq-index")

OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
EMBEDDING_DEPLOYMENT = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")

# ---------------------------------------------------------------------------
# Load FAQ data from JSON file
# ---------------------------------------------------------------------------
FAQ_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contoso_faq.json")

with open(FAQ_FILE, encoding="utf-8") as f:
    SAMPLE_FAQS = json.load(f)


# ---------------------------------------------------------------------------
# Helper: generate an embedding for a given text
# ---------------------------------------------------------------------------
def get_embedding(text: str, client: AzureOpenAI) -> list[float]:
    response = client.embeddings.create(input=text, model=EMBEDDING_DEPLOYMENT)
    return response.data[0].embedding


# ---------------------------------------------------------------------------
# Delete the existing index (if it exists)
# ---------------------------------------------------------------------------
def delete_index(index_client: SearchIndexClient) -> None:
    try:
        index_client.delete_index(INDEX_NAME)
        print(f"✓ Existing index '{INDEX_NAME}' deleted.")
    except Exception:
        print(f"No existing index '{INDEX_NAME}' found — skipping deletion.")


# ---------------------------------------------------------------------------
# Create the search index
# ---------------------------------------------------------------------------
def create_index(index_client: SearchIndexClient) -> None:
    print(f"Creating index '{INDEX_NAME}' ...")

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="question", type=SearchFieldDataType.String, analyzer_name="en.microsoft"),
        SearchableField(name="answer", type=SearchFieldDataType.String, analyzer_name="en.microsoft"),
        SimpleField(name="category", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchField(
            name="question_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=1536,
            vector_search_profile_name="faq-vector-profile",
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="faq-hnsw")],
        profiles=[VectorSearchProfile(name="faq-vector-profile", algorithm_configuration_name="faq-hnsw")],
    )

    semantic_config = SemanticConfiguration(
        name="faq-semantic-config",
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="question"),
            content_fields=[SemanticField(field_name="answer")],
        ),
    )

    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
        semantic_search=SemanticSearch(configurations=[semantic_config]),
    )

    index_client.create_or_update_index(index)
    print(f"✓ Index '{INDEX_NAME}' created successfully.")


# ---------------------------------------------------------------------------
# Upload FAQ entries to the index
# ---------------------------------------------------------------------------
def upload_documents(search_client: SearchClient, openai_client: AzureOpenAI) -> None:
    print(f"Uploading {len(SAMPLE_FAQS)} FAQ entries ...")

    documents = []
    for faq in SAMPLE_FAQS:
        # Generate an embedding for the question (used for vector search)
        embedding = get_embedding(faq["question"], openai_client)
        documents.append({**faq, "question_vector": embedding})

    result = search_client.upload_documents(documents=documents)
    succeeded = sum(1 for r in result if r.succeeded)
    print(f"✓ {succeeded}/{len(documents)} FAQ entries indexed successfully.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    # Keyless authentication via Azure CLI for all Azure resources
    credential = AzureCliCredential()
    token_provider = get_bearer_token_provider(
        credential,
        "https://cognitiveservices.azure.com/.default",
    )

    index_client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=credential)
    search_client = SearchClient(endpoint=SEARCH_ENDPOINT, index_name=INDEX_NAME, credential=credential)
    openai_client = AzureOpenAI(
        azure_endpoint=OPENAI_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version="2024-10-21",
    )

    delete_index(index_client)
    create_index(index_client)
    upload_documents(search_client, openai_client)

    print("\nSetup complete! You can now start faq_agent.py.")


if __name__ == "__main__":
    main()