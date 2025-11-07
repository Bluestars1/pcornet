"""
Episodic Memory: Stores and retrieves past conversations using semantic search.

Maintains a vector database of conversation episodes that can be searched
by semantic similarity, enabling the agent to recall relevant past interactions.
"""
import logging
import os
import warnings
from typing import List, Dict, Any, Optional
from datetime import datetime

# Suppress torch warnings before importing chromadb
warnings.filterwarnings('ignore', message='.*torch.classes.*')
warnings.filterwarnings('ignore', message='.*Tried to instantiate class.*')

import chromadb
from chromadb.config import Settings
from .embeddings import embedding_service

logger = logging.getLogger(__name__)

class EpisodicMemory:
    """
    Manages episodic memory using vector similarity search.
    
    Stores past conversation snippets and enables semantic search
    to find relevant past interactions when processing new queries.
    """
    
    def __init__(self, persist_directory: str = "data/memory/episodic"):
        """
        Initialize episodic memory with LAZY ChromaDB initialization.
        
        Args:
            persist_directory: Directory to persist the vector database
        """
        self.persist_directory = persist_directory
        self.client = None
        self.collection = None
        logger.info(f"EpisodicMemory initialized (lazy-loading from: {persist_directory})")
    
    def _ensure_initialized(self):
        """Lazy initialize ChromaDB on first use."""
        if self.client is None:
            try:
                # Ensure directory exists
                os.makedirs(self.persist_directory, exist_ok=True)
                
                logger.info(f"⏳ Loading ChromaDB (first use)...")
                # Initialize ChromaDB client
                self.client = chromadb.PersistentClient(path=self.persist_directory)
                
                # Create or get collection
                self.collection = self.client.get_or_create_collection(
                    name="conversation_episodes",
                    metadata={"description": "Past conversation episodes for semantic search"}
                )
                
                logger.info(f"✅ Episodic memory initialized: {self.collection.count()} episodes stored")
                
            except Exception as e:
                logger.exception(f"Failed to initialize episodic memory: {e}")
                raise e
    
    def add_turn(self, 
                 turn_id: str,
                 user_query: str, 
                 assistant_response: str, 
                 metadata: Dict[str, Any]) -> bool:
        """
        Store a conversation turn in episodic memory.
        
        Args:
            turn_id: Unique identifier for this turn
            user_query: User's query
            assistant_response: Assistant's response
            metadata: Additional context (session_id, timestamp, etc.)
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self._ensure_initialized()
            
            # Format as Q&A pair for better semantic matching
            text = f"User: {user_query}\nAssistant: {assistant_response}"
            
            # Generate embedding
            embedding = embedding_service.embed_text(text)
            
            if not embedding:
                logger.error(f"Failed to generate embedding for turn {turn_id}")
                return False
            
            # Add to collection
            self.collection.add(
                ids=[turn_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[metadata]
            )
            
            logger.debug(f"Stored conversation turn: {turn_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add turn to episodic memory: {e}")
            return False
    
    def search_similar(self, 
                       query: str, 
                       n_results: int = 3,
                       filter_metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Find similar past conversations using semantic search.
        
        Args:
            query: Query text to search for
            n_results: Number of results to return
            filter_metadata: Optional metadata filters
            
        Returns:
            List of similar episodes with metadata
        """
        try:
            self._ensure_initialized()
            
            # Generate query embedding
            query_embedding = embedding_service.embed_text(query)
            
            if not query_embedding:
                logger.warning("Failed to generate query embedding")
                return []
            
            # Search collection
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=filter_metadata
            )
            
            # Format results
            episodes = []
            if results and results['documents']:
                for i, doc in enumerate(results['documents'][0]):
                    episodes.append({
                        'id': results['ids'][0][i],
                        'text': doc,
                        'metadata': results['metadatas'][0][i],
                        'distance': results['distances'][0][i] if results['distances'] else None,
                        'similarity': 1.0 - (results['distances'][0][i] if results['distances'] else 0)
                    })
            
            logger.debug(f"Found {len(episodes)} similar episodes for query: {query[:50]}...")
            return episodes
            
        except Exception as e:
            logger.error(f"Failed to search episodic memory: {e}")
            return []
    
    def get_recent_episodes(self, n_results: int = 10) -> List[Dict[str, Any]]:
        """
        Get most recent episodes.
        
        Args:
            n_results: Number of episodes to return
            
        Returns:
            List of recent episodes
        """
        try:
            # Get episodes (limited by n_results)
            results = self.collection.get(limit=n_results)
            
            episodes = []
            if results and results['documents']:
                for i, doc in enumerate(results['documents']):
                    episodes.append({
                        'id': results['ids'][i],
                        'text': doc,
                        'metadata': results['metadatas'][i]
                    })
            
            # Sort by timestamp if available
            episodes.sort(
                key=lambda x: x['metadata'].get('timestamp', ''),
                reverse=True
            )
            
            return episodes[:n_results]
            
        except Exception as e:
            logger.error(f"Failed to get recent episodes: {e}")
            return []
    
    def delete_episode(self, episode_id: str) -> bool:
        """Delete an episode from memory."""
        try:
            self.collection.delete(ids=[episode_id])
            logger.debug(f"Deleted episode: {episode_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete episode: {e}")
            return False
    
    def clear_all(self) -> bool:
        """Clear all episodic memory."""
        try:
            self.client.delete_collection(name="conversation_episodes")
            self.collection = self.client.create_collection(
                name="conversation_episodes",
                metadata={"description": "Past conversation episodes for semantic search"}
            )
            logger.info("✅ Cleared all episodic memory")
            return True
        except Exception as e:
            logger.error(f"Failed to clear episodic memory: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about episodic memory.
        
        Returns:
            Dictionary with episode count and collection info
        """
        try:
            if self.collection is None:
                return {'total_episodes': 0, 'collection_name': 'not_loaded', 'status': 'lazy_not_initialized'}
            return {
                'total_episodes': self.collection.count(),
                'collection_name': self.collection.name,
                'status': 'loaded'
            }
        except Exception as e:
            logger.error(f"Failed to get episodic memory stats: {e}")
            return {'total_episodes': 0, 'collection_name': 'unknown', 'status': 'error'}
    
    def prune_old_episodes(self, max_age_days: int = 30, max_episodes: int = 1000) -> Dict[str, int]:
        """
        Prune old episodes to prevent unbounded growth.
        
        Args:
            max_age_days: Delete episodes older than this many days
            max_episodes: Keep at most this many episodes (most recent)
            
        Returns:
            Dict with pruning statistics
        """
        try:
            self._ensure_initialized()
            
            from datetime import timedelta
            
            stats = {
                'episodes_before': self.collection.count(),
                'episodes_deleted': 0,
                'episodes_after': 0
            }
            
            if stats['episodes_before'] == 0:
                logger.info("No episodes to prune")
                return stats
            
            # Get all episodes with metadata
            all_data = self.collection.get(include=['metadatas'])
            
            if not all_data or not all_data['ids']:
                return stats
            
            cutoff_time = datetime.now() - timedelta(days=max_age_days)
            ids_to_delete = []
            
            # Find episodes older than cutoff
            for i, metadata in enumerate(all_data['metadatas']):
                if 'timestamp' in metadata:
                    try:
                        episode_time = datetime.fromisoformat(metadata['timestamp'])
                        if episode_time < cutoff_time:
                            ids_to_delete.append(all_data['ids'][i])
                    except:
                        pass
            
            # If still too many episodes, delete oldest ones
            if (stats['episodes_before'] - len(ids_to_delete)) > max_episodes:
                # Get episodes sorted by timestamp (oldest first)
                episodes_with_time = []
                for i, metadata in enumerate(all_data['metadatas']):
                    if all_data['ids'][i] not in ids_to_delete and 'timestamp' in metadata:
                        try:
                            episode_time = datetime.fromisoformat(metadata['timestamp'])
                            episodes_with_time.append((all_data['ids'][i], episode_time))
                        except:
                            pass
                
                episodes_with_time.sort(key=lambda x: x[1])
                
                # Calculate how many more to delete
                current_count = stats['episodes_before'] - len(ids_to_delete)
                need_to_delete = current_count - max_episodes
                
                if need_to_delete > 0:
                    ids_to_delete.extend([ep_id for ep_id, _ in episodes_with_time[:need_to_delete]])
            
            # Delete episodes in batches
            if ids_to_delete:
                batch_size = 100
                for i in range(0, len(ids_to_delete), batch_size):
                    batch = ids_to_delete[i:i + batch_size]
                    self.collection.delete(ids=batch)
                    stats['episodes_deleted'] += len(batch)
            
            stats['episodes_after'] = self.collection.count()
            
            logger.info(f"🧹 Pruned {stats['episodes_deleted']} old episodes (kept {stats['episodes_after']})")
            return stats
            
        except Exception as e:
            logger.error(f"Error pruning episodes: {e}")
            return {'error': str(e)}

# Global instance
episodic_memory = EpisodicMemory()
