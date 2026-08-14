"""Azure AI Search: index management and hybrid retrieval."""

import logging

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from azure.search.documents.models import VectorizedQuery
from langchain_openai import AzureOpenAIEmbeddings

from ..config import get_settings

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSIONS = 1536  # text-embedding-3-small


def _credential() -> AzureKeyCredential:
    return AzureKeyCredential(get_settings().azure_search_api_key)


def get_embeddings() -> AzureOpenAIEmbeddings:
    s = get_settings()
    return AzureOpenAIEmbeddings(
        azure_endpoint=s.azure_openai_endpoint,
        api_key=s.azure_openai_api_key,
        api_version=s.azure_openai_api_version,
        azure_deployment=s.azure_openai_embedding_deployment,
    )


def ensure_index() -> None:
    """Create the index if it doesn't exist. Safe to call on startup."""
    s = get_settings()
    client = SearchIndexClient(endpoint=s.azure_search_endpoint, credential=_credential())
    if s.azure_search_index in [name for name in client.list_index_names()]:
        return

    index = SearchIndex(
        name=s.azure_search_index,
        fields=[
            SimpleField(name="chunk_id", type=SearchFieldDataType.String, key=True),
            SimpleField(name="document", type=SearchFieldDataType.String, filterable=True),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SimpleField(name="item_name", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="unit", type=SearchFieldDataType.String),
            SimpleField(name="unit_price", type=SearchFieldDataType.Double, filterable=True),
            SearchField(
                name="embedding",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=EMBEDDING_DIMENSIONS,
                vector_search_profile_name="default-profile",
            ),
        ],
        vector_search=VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="default-hnsw")],
            profiles=[
                VectorSearchProfile(
                    name="default-profile", algorithm_configuration_name="default-hnsw"
                )
            ],
        ),
    )
    client.create_index(index)
    logger.info("Created index %s", s.azure_search_index)


def upsert_chunks(chunks: list[dict]) -> int:
    """Embed and upload chunks. Each chunk: {chunk_id, document, content, item_name, unit, unit_price}."""
    s = get_settings()
    embeddings = get_embeddings()
    vectors = embeddings.embed_documents([c["content"] for c in chunks])
    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = vector

    client = SearchClient(
        endpoint=s.azure_search_endpoint,
        index_name=s.azure_search_index,
        credential=_credential(),
    )
    result = client.upload_documents(documents=chunks)
    return sum(1 for r in result if r.succeeded)


def hybrid_search(query: str, top: int = 8) -> list[dict]:
    """Hybrid (keyword + vector) retrieval. Returns raw hits with scores."""
    s = get_settings()
    query_vector = get_embeddings().embed_query(query)
    client = SearchClient(
        endpoint=s.azure_search_endpoint,
        index_name=s.azure_search_index,
        credential=_credential(),
    )
    results = client.search(
        search_text=query,
        vector_queries=[
            VectorizedQuery(vector=query_vector, k_nearest_neighbors=top, fields="embedding")
        ],
        top=top,
        select=["chunk_id", "document", "content", "item_name", "unit", "unit_price"],
    )
    return [
        {
            "chunk_id": r["chunk_id"],
            "document": r["document"],
            "content": r["content"],
            "item_name": r.get("item_name"),
            "unit": r.get("unit"),
            "unit_price": r.get("unit_price"),
            "score": r["@search.score"],
        }
        for r in results
    ]
