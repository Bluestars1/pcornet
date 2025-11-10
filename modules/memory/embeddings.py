"""
Embedding service for semantic search and similarity matching.

Provides text-to-vector conversion using sentence-transformers for
efficient semantic search across conversations and facts.

**Performance:** Imports are deferred until first use to prevent 3+ second
startup delay from loading sentence_transformers library.
"""
import logging
import warnings
from typing import List

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Generates embeddings for semantic similarity search.
    
    Uses sentence-transformers with a lightweight, fast model
    that provides good quality embeddings (384 dimensions).
    
    **Lazy Loading:** Model is only loaded on first use to prevent
    startup delays. First call will take 2-3 seconds.
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize embedding service with lazy loading.
        
        Args:
            model_name: HuggingFace model name for embeddings.
                       Default 'all-MiniLM-L6-v2' is fast and efficient.
        """
        self.model_name = model_name
        self.model = None
        self.dimension = None
        logger.info(f"EmbeddingService initialized (lazy-loading: {model_name})")
    
    def _ensure_model_loaded(self):
        """Load the model if not already loaded (lazy initialization)."""
        if self.model is None:
            try:
                logger.info(f"⏳ Loading embedding model (first use): {self.model_name}...")
                
                # Import here to avoid 3+ second startup delay
                warnings.filterwarnings('ignore', message='.*torch.classes.*')
                warnings.filterwarnings('ignore', message='.*Tried to instantiate class.*')
                from sentence_transformers import SentenceTransformer
                
                self.model = SentenceTransformer(self.model_name)
                self.dimension = self.model.get_sentence_embedding_dimension()
                logger.info(f"✅ Embedding model loaded: {self.model_name} ({self.dimension}D)")
            except Exception as e:
                logger.exception(f"Failed to load embedding model: {e}")
                raise e
    
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        try:
            self._ensure_model_loaded()
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Failed to embed text: {e}")
            return []
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts (batched for efficiency).
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        try:
            self._ensure_model_loaded()
            embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Failed to embed batch: {e}")
            return []
    
    def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score (0-1, higher is more similar)
        """
        try:
            import numpy as np
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
                
            return float(np.dot(vec1, vec2) / (norm1 * norm2))
        except Exception as e:
            logger.error(f"Failed to compute similarity: {e}")
            return 0.0

# Global instance for easy access
embedding_service = EmbeddingService()
