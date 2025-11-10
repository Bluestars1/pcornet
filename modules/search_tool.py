"""Provides a helper class for performing hybrid searches on Azure AI Search.

This module defines the `Search` class, which encapsulates the logic for
executing a hybrid search (vector + semantic + keyword) against a specified
Azure AI Search index. It handles configuration, embedding generation via
Azure OpenAI, and the search execution itself, returning a structured list of
results.

Key Features:
- Reads configuration from environment variables (e.g., endpoints, keys).
- Automatically generates query embeddings if not provided.
- Supports semantic ranking and keyword search fields.
- Uses the `azure-search-documents` SDK for executing the search.

Exceptions:
- `SearchError`: Raised for configuration issues or runtime search failures.
"""

from __future__ import annotations

import os
import json

import logging
from typing import Any, Dict, List, Optional

from .config import get_config, create_openai_client

logger = logging.getLogger(__name__)

try:
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient
    from azure.search.documents.models import VectorizedQuery
except Exception as e:  # pragma: no cover - import errors are surfaced at runtime
    # Defer the import error to runtime usage to keep module import time flexible in tests
    AzureKeyCredential = None
    SearchClient = None
    VectorizedQuery = None


class SearchError(Exception):
    """Custom exception for errors raised by the Search class."""
    pass


class Search:
    """
    Performs a hybrid search on an Azure AI Search index.

    This class orchestrates a complex search query involving vector similarity,
    semantic reranking, and traditional keyword matching. It can either take a
    pre-computed embedding vector or generate one on-the-fly for the query.

    Attributes:
        index (str): The name of the search index to query.
        query (str): The user's search query.
        top (int): The number of results to return.
        semantic_config (str, optional): The name of the semantic configuration
                                         to use.
    """

    def __init__(
        self,
        index: str,
        query: str,
        *,
        top: int = 20,
        embedding: Optional[List[float]] = None,
        semantic_config: Optional[str] = None,
        search_fields: Optional[List[str]] = None,
        vector_field: Optional[str] = None,
        use_index_config: bool = True,
    ) -> None:
        """
        Initializes the Search object with query parameters and configuration.

        Args:
            index (str): The name or registry key of the target search index.
                If use_index_config=True, attempts to load from registry first.
            query (str): The search query string.
            top (int): The maximum number of results to retrieve. Defaults to 20.
            embedding (List[float], optional): A pre-computed embedding vector
                for the query. If None, one will be generated.
            semantic_config (str, optional): The name of the semantic
                configuration to apply. Overrides index config if provided.
            search_fields (List[str], optional): A list of field names to use
                for keyword search. Overrides index config if provided.
            vector_field (str, optional): The name of the vector field in the
                index. Overrides index config if provided.
            use_index_config (bool): If True, attempts to load configuration from
                the index registry. If False or key not found, uses direct index name.
                Defaults to True for new code, backward compatible.
        """
        self.query = query
        self.top = int(top)
        self._embedding = embedding

        # Load Azure Cognitive Search config from configuration system
        config = get_config()
        self.search_endpoint = config.azure_ai_search_endpoint
        self.search_api_key = config.azure_ai_search_api_key

        # Try to load from index registry first if enabled
        index_config_loaded = False
        if use_index_config and index in config.indices:
            index_config = config.get_index_config(index)
            self.index = index_config.name
            self.vector_field = vector_field or index_config.vector_field
            self.search_fields = search_fields or index_config.search_fields
            self.semantic_config = semantic_config or index_config.semantic_config
            index_config_loaded = True
            logger.info(f"Using index config for '{index}': {index_config.name}")
        else:
            # Fallback to direct index name (backward compatible)
            self.index = index
            self.vector_field = vector_field or os.getenv("AZURE_SEARCH_VECTOR_FIELD", "content_vector")
            
            # Optionally override search fields passed directly or from env
            env_search_fields = os.getenv("AZURE_SEARCH_SEARCH_FIELDS")
            if search_fields:
                self.search_fields = search_fields
            elif env_search_fields:
                self.search_fields = [f.strip() for f in env_search_fields.split(",") if f.strip()]
            else:
                self.search_fields = None
            
            self.semantic_config = semantic_config

        # Log the loaded values for debugging
        logger.info(f"Loaded Azure AI Search Endpoint: {self.search_endpoint}")
        logger.info(f"Loaded Azure AI Search API Key: {'[REDACTED]' if self.search_api_key else 'None'}")

        self.search_api_version = os.getenv("AZURE_SEARCH_API_VERSION", "2023-07-01-Preview")

        # OpenAI embedding deployment (optional) - will use Azure OpenAI config if set
        self.embedding_deployment = config.azure_openai_embedding_deployment

        self._validate_config()

    def _validate_config(self) -> None:
        """
        Validates that required search configuration is present.

        Raises:
            SearchError: If the search endpoint or API key is not configured in
                         the environment.
        """
        if not self.search_endpoint:
            raise SearchError("AZURE_AI_SEARCH_ENDPOINT is required in environment or .env")
        if not self.search_api_key:
            raise SearchError("AZURE_AI_SEARCH_API_KEY is required in environment or .env")

    def _get_embedding(self, text: str) -> List[float]:
        """
        Generates an embedding vector for the given text using Azure OpenAI.

        This method requires the `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` environment
        variable to be set. It uses the `azure-ai-openai` SDK to communicate
        with the embeddings endpoint.

        Args:
            text (str): The input text to embed.

        Returns:
            List[float]: The resulting embedding vector.

        Raises:
            SearchError: If the embedding deployment is not configured or if
                         the SDK call fails.
        """
        deployment = self.embedding_deployment or os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        if not deployment:
            raise SearchError(
                "Embedding deployment not configured. Set AZURE_OPENAI_EMBEDDING_DEPLOYMENT in .env "
                "or provide an `embedding` directly to Search()."
            )

        try:
            client = create_openai_client()
            resp = client.embeddings.create(model=deployment, input=text)
            embedding = resp.data[0].embedding
            return embedding
        except Exception as e:
            logger.exception("Failed to create embedding via SDK")
            raise SearchError(f"Failed to create embedding via SDK: {e}") from e

    def _build_search_body(self, embedding: List[float]) -> Dict[str, Any]:
        """
        Constructs the request body for the search REST API call.

        Note: This method is currently not used as the implementation favors the
        `azure-search-documents` SDK over raw REST calls.

        Args:
            embedding (List[float]): The query embedding vector.

        Returns:
            Dict[str, Any]: A dictionary representing the JSON body for the
                            search request.
        """
        body: Dict[str, Any] = {}

        # Vector (k nearest neighbors)
        if embedding is not None:
            body["vector"] = {"value": embedding, "fields": self.vector_field, "k": self.top}

        # Query text (keyword/semantic)
        # When using semantic ranking, set queryType to 'semantic' and provide semantic config
        if self.semantic_config:
            body["queryType"] = "semantic"
            body["semantic"] = {"configuration": self.semantic_config}

        # Provide the query string - used for keyword match and semantic ranking
        body["query"] = self.query
        body["top"] = self.top

        if self.search_fields:
            body["searchFields"] = ",".join(self.search_fields)

        return body

    def run(self) -> List[Dict[str, Any]]:
        """
        Executes the hybrid search against the Azure AI Search index.

        This is the main method of the class. It orchestrates the search by:
        1. Preparing the query vector (if applicable).
        2. Initializing the `SearchClient`.
        3. Executing the search using the SDK's `search` method.
        4. Formatting the raw results into a standardized list of dictionaries.

        Returns:
            List[Dict[str, Any]]: A list of search results. Each result is a
            dictionary containing a 'score', the 'document' itself, and
            optional 'highlights'.

        Raises:
            SearchError: If the `azure-search-documents` SDK is not installed
                         or if the search call fails for any reason.
        """
        embedding = self._embedding

        # If no embedding is provided, generate one.
        if embedding is None and self.query:
            embedding = self._get_embedding(self.query)

        if SearchClient is None or AzureKeyCredential is None:
            raise SearchError("azure-search-documents SDK is not installed; cannot run search")

        try:
            credential = AzureKeyCredential(self.search_api_key)
            client = SearchClient(endpoint=self.search_endpoint, index_name=self.index, credential=credential)

            # Prepare vector for search
            vect = VectorizedQuery(vector=embedding, fields=self.vector_field, k_nearest_neighbors=self.top) if embedding else None

            # Build search parameters
            search_text = self.query
            search_kwargs = {"top": self.top}
            if self.search_fields:
                search_kwargs["search_fields"] = self.search_fields
            if self.semantic_config:
                search_kwargs["query_type"] = "semantic"
                search_kwargs["semantic_configuration_name"] = self.semantic_config

            results = client.search(search_text, vector_queries=[vect] if vect else None, **search_kwargs)

            hits: List[Dict[str, Any]] = []
            for r in results:
                # results items may be dict-like or objects; try dict access first
                score = r.get("@search.score") if isinstance(r, dict) else getattr(r, "@search.score", None)

                # Document content is available via mapping or object interface
                try:
                    document = dict(r)
                except (TypeError, ValueError):
                    # fallback: try to build dict from attributes
                    document = {k: getattr(r, k) for k in dir(r) if not k.startswith("_")}
                
                hit = {"score": score, "document": document}
                
                # Highlights may be provided in r['@search.highlights']
                if "@search.highlights" in r:
                    hit["highlights"] = r["@search.highlights"]
                
                hits.append(hit)

            return hits
        except Exception as e:
            logger.exception("Search SDK call failed: %s", e)
            raise SearchError(f"Search SDK call failed: {e}") from e


__all__ = ["Search", "SearchError"]
