"""
Configuration loader for application settings.

This module defines a configuration class that loads service
settings from environment variables using `dotenv`. It provides a centralized
and consistent way to access configuration details like API keys, endpoints,
and deployment names throughout the application. It also includes a
health check to verify connections to external services on startup.
"""

import os
import logging
import warnings
from dotenv import load_dotenv

# Suppress torch warnings about __path__._path
warnings.filterwarnings('ignore', message='.*torch.classes.*')
warnings.filterwarnings('ignore', message='.*Tried to instantiate class.*')

# Configure langchain globals to use new API
try:
    from langchain import globals as langchain_globals
    langchain_globals.set_verbose(False)
except ImportError:
    pass

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class IndexConfig:
    """
    Configuration for a single Azure Search index.
    
    This class encapsulates all the metadata needed to interact with a specific
    Azure Search index, including its schema-specific fields and search configuration.
    """
    
    def __init__(
        self,
        name: str,
        vector_field: str = "vector",
        search_fields: list = None,
        semantic_config: str = None,
        description: str = ""
    ):
        """
        Initialize an index configuration.
        
        Args:
            name: The Azure Search index name
            vector_field: Name of the vector field for similarity search
            search_fields: List of fields to include in keyword search
            semantic_config: Name of the semantic configuration to use
            description: Human-readable description of the index contents
        """
        self.name = name
        self.vector_field = vector_field
        self.search_fields = search_fields or []
        self.semantic_config = semantic_config
        self.description = description
    
    def __repr__(self):
        return (f"IndexConfig(name='{self.name}', vector_field='{self.vector_field}', "
                f"search_fields={self.search_fields}, semantic_config='{self.semantic_config}')")


class AppConfig:
    """
    A container for all application configuration parameters.

    This class reads environment variables related to Azure services,
    and stores them as instance attributes. It also provides health checks
    to validate service connections at startup.
    """
    def __init__(self):
        """
        Initializes the configuration object by loading environment variables.
        """
        # Load environment variables from .env file
        load_dotenv()
        
        # General settings
        self.agent_temperature = float(os.getenv("AGENT_TEMPERATURE", 0.7))

        # Azure OpenAI settings
        self.azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        self.azure_openai_chat_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
        self.azure_openai_embedding_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")

        # Azure AI Search settings
        self.azure_ai_search_endpoint = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
        self.azure_ai_search_api_key = os.getenv("AZURE_AI_SEARCH_API_KEY")
        self.pcornet_icd_index = os.getenv("PCORNET_ICD_INDEX_NAME", "pcornet-icd-index")
        
        # Search configuration
        self.search_top_k = int(os.getenv("AZURE_SEARCH_TOP_K", os.getenv("SEARCH_TOP_K", "10")))
        
        # Multi-Index Registry: Define all available search indices with their configurations
        self.indices = {
            "icd": IndexConfig(
                name=os.getenv("PCORNET_ICD_INDEX_NAME", "pcornet-icd-index"),
                vector_field="content_vector",  # Updated to match actual index schema
                search_fields=["STR", "CODE"],  # REL is retrievable but not searchable
                semantic_config=None,  # Temporarily disabled - semantic config may not exist
                description="ICD-10 diagnosis codes with SNOMED CT relationships and OHDSI mappings"
            ),
            "snomed": IndexConfig(
                name=os.getenv("PCORNET_SNOMED_INDEX_NAME", "pcornet-snomedus-index_v1"),
                vector_field="content_vector",
                search_fields=["STR", "CODE", "SAB"],
                semantic_config="pcornet-semantic-config",
                description="SNOMED CT US Edition clinical terminology concepts and relationships"
            )
        }

        # Additional properties for compatibility
        self.endpoint = self.azure_openai_endpoint
        self.api_key = self.azure_openai_api_key
        self.api_version = self.azure_openai_api_version
        self.chat_deployment = self.azure_openai_chat_deployment
        
        # Validation settings
        self.agent_max_tokens = int(os.getenv("AGENT_MAX_TOKENS", "2000"))
        self.request_timeout = int(os.getenv("REQUEST_TIMEOUT", "30"))
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        self.max_conversation_messages = int(os.getenv("MAX_CONVERSATION_MESSAGES", "20"))

        # Log loaded variables for verification
        self._log_loaded_variables()
        
        # General settings
        self.agent_temperature = float(os.getenv("AGENT_TEMPERATURE", 0.7))

        # Azure OpenAI settings
        self.azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        self.azure_openai_chat_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
        self.azure_openai_embedding_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")

        # Azure AI Search settings
        self.azure_ai_search_endpoint = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
        self.azure_ai_search_api_key = os.getenv("AZURE_AI_SEARCH_API_KEY")
        self.pcornet_icd_index = os.getenv("PCORNET_ICD_INDEX_NAME", "pcornet-icd-index")
        
        # Search configuration
        self.search_top_k = int(os.getenv("AZURE_SEARCH_TOP_K", os.getenv("SEARCH_TOP_K", "10")))
        
        # Multi-Index Registry: Define all available search indices with their configurations
        self.indices = {
            "icd": IndexConfig(
                name=os.getenv("PCORNET_ICD_INDEX_NAME", "pcornet-icd-index"),
                vector_field="content_vector",  # Updated to match actual index schema
                search_fields=["STR", "CODE"],  # REL is retrievable but not searchable
                semantic_config=None,  # Temporarily disabled - semantic config may not exist
                description="ICD-10 diagnosis codes with SNOMED CT relationships and OHDSI mappings"
            ),
            "snomed": IndexConfig(
                name=os.getenv("PCORNET_SNOMED_INDEX_NAME", "pcornet-snomedus-index_v1"),
                vector_field="content_vector",
                search_fields=["STR", "CODE", "SAB"],
                semantic_config="pcornet-semantic-config",
                description="SNOMED CT US Edition clinical terminology concepts and relationships"
            )
        }

        # Additional properties for compatibility
        self.endpoint = self.azure_openai_endpoint
        self.api_key = self.azure_openai_api_key
        self.api_version = self.azure_openai_api_version
        self.chat_deployment = self.azure_openai_chat_deployment
        
        # Validation settings
        self.agent_max_tokens = int(os.getenv("AGENT_MAX_TOKENS", "2000"))
        self.request_timeout = int(os.getenv("REQUEST_TIMEOUT", "30"))
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        self.max_conversation_messages = int(os.getenv("MAX_CONVERSATION_MESSAGES", "20"))

        # Log loaded variables for verification
        self._log_loaded_variables()

    def _log_loaded_variables(self):
        """Logs the loaded configuration variables for verification."""
        logging.info("--- Configuration Variables Loaded ---")
        logging.info(f"AGENT_TEMPERATURE: {self.agent_temperature}")
        logging.info(f"AGENT_MAX_TOKENS: {self.agent_max_tokens}")
        logging.info(f"AZURE_OPENAI_ENDPOINT: {self.azure_openai_endpoint}")
        logging.info(f"AZURE_OPENAI_API_KEY: {'*' * 8 if self.azure_openai_api_key else 'Not Set'}")
        logging.info(f"AZURE_OPENAI_API_VERSION: {self.azure_openai_api_version}")
        logging.info(f"AZURE_OPENAI_CHAT_DEPLOYMENT: {self.azure_openai_chat_deployment}")
        logging.info(f"AZURE_OPENAI_EMBEDDING_DEPLOYMENT: {self.azure_openai_embedding_deployment}")
        logging.info(f"AZURE_AI_SEARCH_ENDPOINT: {self.azure_ai_search_endpoint}")
        logging.info(f"AZURE_AI_SEARCH_API_KEY: {'*' * 8 if self.azure_ai_search_api_key else 'Not Set'}")
        logging.info(f"PCORNET_ICD_INDEX_NAME: {self.pcornet_icd_index}")
        logging.info(f"AZURE_SEARCH_TOP_K: {self.search_top_k}")
        logging.info("--- Registered Search Indices ---")
        for key, idx_config in self.indices.items():
            logging.info(f"  [{key}] {idx_config.name}")
            logging.info(f"    - Vector field: {idx_config.vector_field}")
            logging.info(f"    - Search fields: {', '.join(idx_config.search_fields)}")
            logging.info(f"    - Description: {idx_config.description}")
        logging.info("------------------------------------")

    def get_azure_openai_kwargs(self) -> dict:
        """
        Returns a dictionary of keyword arguments for AzureChatOpenAI.
        """
        return {
            "azure_endpoint": self.azure_openai_endpoint,
            "api_key": self.azure_openai_api_key,
            "api_version": self.azure_openai_api_version,
            "azure_deployment": self.azure_openai_chat_deployment
        }
    
    def get_index_config(self, index_key: str) -> IndexConfig:
        """
        Retrieve the configuration for a specific index by its key.
        
        Args:
            index_key: The registry key for the index (e.g., "icd", "snomed")
            
        Returns:
            IndexConfig: The configuration object for the specified index
            
        Raises:
            ValueError: If the index_key is not found in the registry
        """
        if index_key not in self.indices:
            available = ", ".join(self.indices.keys())
            raise ValueError(
                f"Unknown index key: '{index_key}'. "
                f"Available indices: {available}"
            )
        return self.indices[index_key]

    def health_check(self):
        """
        Performs a health check on the configured Azure services.
        Returns True if all checks pass, False otherwise.
        """
        logging.info("\n--- Performing Health Checks ---")
        services_ok = True

        # Check Azure OpenAI connection
        if not all([self.azure_openai_endpoint, self.azure_openai_api_key, self.azure_openai_api_version]):
            logging.error("Azure OpenAI environment variables are not fully set.")
            services_ok = False
        else:
            try:
                from openai import AzureOpenAI
                client = AzureOpenAI(
                    azure_endpoint=self.azure_openai_endpoint,
                    api_key=self.azure_openai_api_key,
                    api_version=self.azure_openai_api_version,
                    timeout=10.0,
                )
                client.models.list()
                logging.info("✅ Azure OpenAI connection successful.")
            except ImportError:
                logging.error("❌ 'openai' SDK is not installed. Please run 'pip install openai'.")
                services_ok = False
            except Exception as e:
                logging.error(f"❌ Azure OpenAI connection failed: {e}")
                services_ok = False

        # Check Azure AI Search connection
        if not all([self.azure_ai_search_endpoint, self.azure_ai_search_api_key, self.pcornet_icd_index]):
            logging.error("Azure AI Search environment variables are not fully set.")
            services_ok = False
        else:
            try:
                from azure.core.credentials import AzureKeyCredential
                from azure.search.documents import SearchClient
                credential = AzureKeyCredential(self.azure_ai_search_api_key)
                search_client = SearchClient(
                    endpoint=self.azure_ai_search_endpoint,
                    index_name=self.pcornet_icd_index,
                    credential=credential
                )
                search_client.get_document_count()
                logging.info("✅ Azure AI Search connection successful.")
            except ImportError:
                logging.error("❌ 'azure-search-documents' SDK is not installed. Please run 'pip install azure-search-documents'.")
                services_ok = False
            except Exception as e:
                logging.error(f"❌ Azure AI Search connection failed: {e}")
                services_ok = False
        
        logging.info("--------------------------------")
        if not services_ok:
            logging.critical("🚨 One or more health checks failed. The application may not function correctly. Please check your .env file and service status.")
        
        return services_ok


# Legacy compatibility class
class AzureOpenAIConfig:
    """
    Legacy compatibility wrapper that provides validation similar to the original implementation.
    Provides backward compatibility for existing code that uses AzureOpenAIConfig.
    """
    def __init__(self):
        # For testing purposes, we need to respect the current environment state
        # Check environment variables first (this respects test manipulations)
        self.endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        self.api_key = os.getenv('AZURE_OPENAI_API_KEY')
        self.chat_deployment = os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT')
        self.api_version = os.getenv('AZURE_OPENAI_API_VERSION')
        
        # Only load from .env if environment variables are not set
        # This allows tests to override by setting environment variables
        if not any([self.endpoint, self.api_key, self.chat_deployment]):
            # Import here to avoid circular imports and ensure fresh load_dotenv call
            from dotenv import load_dotenv
            load_dotenv()
            
            self.endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
            self.api_key = os.getenv('AZURE_OPENAI_API_KEY')
            self.chat_deployment = os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT')
        
        # Set defaults
        if not self.api_version:
            self.api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')
        
        # Default values for compatibility
        self.agent_temperature = float(os.getenv("AGENT_TEMPERATURE", "1.0"))
        self.agent_max_tokens = int(os.getenv("AGENT_MAX_TOKENS", "2000"))
        self.request_timeout = int(os.getenv("REQUEST_TIMEOUT", "30"))
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        self.max_conversation_messages = int(os.getenv("MAX_CONVERSATION_MESSAGES", "20"))
        
        # Validation for required fields (maintaining existing test behavior)
        required_fields = [
            ("AZURE_OPENAI_ENDPOINT", self.endpoint),
            ("AZURE_OPENAI_API_KEY", self.api_key),
            ("AZURE_OPENAI_CHAT_DEPLOYMENT", self.chat_deployment),
        ]
        
        for field_name, field_value in required_fields:
            if not field_value:
                raise ValueError(f"{field_name} is required")
    
    def get_azure_openai_kwargs(self) -> dict:
        """Returns a dictionary of keyword arguments for AzureChatOpenAI."""
        return {
            "azure_endpoint": self.endpoint,
            "api_key": self.api_key,
            "api_version": self.api_version,
            "azure_deployment": self.chat_deployment
        }


# Create a single, global instance of the configuration (lazy initialization)
config = None

def get_config():
    """Get the global AppConfig instance, creating it if necessary."""
    global config
    if config is None:
        config = AppConfig()
    return config

def create_chat_llm(max_tokens: int = None, temperature: float = None):
    """
    Creates and returns a standardized AzureChatOpenAI instance.
    
    This helper method centralizes the creation of LLM clients for agents,
    ensuring consistent configuration across the application.
    
    Args:
        max_tokens: Maximum tokens for the response (default: from AGENT_MAX_TOKENS env var or 2000)
        temperature: Temperature for response generation (default: from config)
    
    Returns:
        AzureChatOpenAI: Configured LLM client instance
    """
    from langchain_openai import AzureChatOpenAI
    
    cfg = get_config()
    temp = temperature if temperature is not None else cfg.agent_temperature
    tokens = max_tokens if max_tokens is not None else cfg.agent_max_tokens
    
    return AzureChatOpenAI(
        deployment_name=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        temperature=temp,
        max_tokens=tokens,
        azure_endpoint=cfg.azure_openai_endpoint,
        api_version=cfg.azure_openai_api_version,
        openai_api_key=cfg.azure_openai_api_key
    )

def create_openai_client():
    """
    Creates and returns a standardized AzureOpenAI client instance.
    
    This helper method centralizes the creation of OpenAI clients for
    operations like embeddings, fact extraction, and classifications.
    
    Returns:
        AzureOpenAI: Configured OpenAI client instance
    """
    from openai import AzureOpenAI
    
    cfg = get_config()
    
    return AzureOpenAI(
        api_version=cfg.azure_openai_api_version,
        azure_endpoint=cfg.azure_openai_endpoint,
        api_key=cfg.azure_openai_api_key,
    )

def invoke_llm_with_retry(llm_callable, max_retries=3, initial_delay=2):
    """
    Wrapper to invoke any LLM with automatic retry on rate limit errors.
    
    Args:
        llm_callable: A callable that invokes the LLM (e.g., lambda: llm.invoke(messages))
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds before first retry (default: 2)
    
    Returns:
        The result from the LLM invocation
    
    Raises:
        RateLimitError: If rate limit is still exceeded after all retries
        Exception: For other errors during invocation
    
    Example:
        result = invoke_llm_with_retry(lambda: llm.invoke([msg1, msg2]))
    """
    import time
    from openai import RateLimitError
    
    logger = logging.getLogger(__name__)
    
    for attempt in range(max_retries):
        try:
            return llm_callable()
            
        except RateLimitError as e:
            if attempt < max_retries - 1:
                wait_time = initial_delay * (2 ** attempt)  # Exponential backoff: 2s, 4s, 8s
                logger.warning(f"⚠️ Rate limit hit, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                logger.error(f"❌ Rate limit exceeded after {max_retries} attempts")
                raise
        
        except Exception as e:
            logger.error(f"❌ LLM invocation error: {e}")
            raise
    
    raise Exception("Failed to invoke LLM after all retry attempts")

# Prompt Templates
CONCEPT_SET_CLASSIFICATION_PROMPT = """
You are an expert at classifying user intent. Your task is to determine if the user's query is asking to create, generate, or find a "concept set".
A "concept set" is a group of medical codes (like ICD-10) related to a specific clinical idea, such as "Diabetes" or "Heart Failure".

Respond with "True" if the query is about creating a concept set.
Respond with "False" if the query is about anything else.

User Query: "{query}"
"""

CONCEPT_SET_FORMATTING_PROMPT = """
You are a helpful AI assistant specializing in medical coding. Your task is to format the provided data into a clear and readable format based on the user's original request.

🔒 CRITICAL: The data you are given is the ONLY source of information. Do not add any codes or information not in the provided data.

⚠️ IMPORTANT OHDSI FIELD: If the data includes an OHDSI field, it contains mappings to other vocabularies in JSON format:
- The OHDSI field has a "maps" array
- Each map contains: vocabulary_id, concept_code, concept_name, relationship_id, domain_id
- When vocabulary_id="SNOMED", the concept_code is the SNOMED CT code and concept_name is its description
- If the user asks for SNOMED codes, extract them from the OHDSI field - they are already there!

User's original request: "{query}"
Data to format:
---
{context_data}
---

MANDATORY RULES:
1. Use ONLY the data provided above
2. For SNOMED requests: Parse the OHDSI field, find vocabulary_id="SNOMED", extract concept_code and concept_name
3. If user asks for SNOMED codes and OHDSI field exists, include a SNOMED column in your table
4. Format as requested (table, JSON, list, etc.)
5. If the user asks for a table, create a markdown table
6. If the user does not specify a format, default to a markdown table with appropriate columns
7. If OHDSI data is present and user mentions SNOMED, automatically include SNOMED codes
8. Do not say "no SNOMED codes provided" if OHDSI field exists - extract them!

Based on the user's request, present the data in the best possible format.
"""