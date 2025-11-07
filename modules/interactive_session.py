"""
Interactive Session Manager for Dynamic Data Manipulation

This module provides functionality for maintaining interactive chat sessions
where analysts can request to add, remove, or modify information like SNOMED
codes, ICD descriptions, and other data elements during their conversation.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class DataItem:
    """Represents a single data item in the interactive session."""
    item_type: str  # 'icd_code', 'snomed_code', 'description', etc.
    key: str        # Unique identifier (e.g., 'I10', '59621000')
    value: str      # Display value
    metadata: Dict[str, Any] = field(default_factory=dict)
    added_at: datetime = field(default_factory=datetime.now)
    source_query: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize DataItem to dictionary for JSON storage."""
        return {
            'item_type': self.item_type,
            'key': self.key,
            'value': self.value,
            'metadata': self.metadata,
            'added_at': self.added_at.isoformat(),
            'source_query': self.source_query
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'DataItem':
        """Deserialize DataItem from dictionary."""
        return DataItem(
            item_type=data['item_type'],
            key=data['key'],
            value=data['value'],
            metadata=data.get('metadata', {}),
            added_at=datetime.fromisoformat(data['added_at']),
            source_query=data.get('source_query', '')
        )

@dataclass
class InteractiveContext:
    """Maintains the current state of an interactive session."""
    session_id: str
    current_data: Dict[str, DataItem] = field(default_factory=dict)
    query_history: List[str] = field(default_factory=list)
    modifications: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize InteractiveContext to dictionary for JSON storage."""
        return {
            'session_id': self.session_id,
            'current_data': {key: item.to_dict() for key, item in self.current_data.items()},
            'query_history': self.query_history,
            'modifications': self.modifications,
            'created_at': self.created_at.isoformat()
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'InteractiveContext':
        """Deserialize InteractiveContext from dictionary."""
        context = InteractiveContext(
            session_id=data['session_id'],
            query_history=data.get('query_history', []),
            modifications=data.get('modifications', []),
            created_at=datetime.fromisoformat(data['created_at'])
        )
        # Deserialize current_data
        for key, item_data in data.get('current_data', {}).items():
            context.current_data[key] = DataItem.from_dict(item_data)
        return context

class InteractiveSession:
    """
    Manages interactive chat sessions with dynamic data manipulation capabilities.
    
    This class allows analysts to:
    - View current data set
    - Add specific SNOMED codes, ICD codes, or descriptions
    - Remove unwanted information
    - Modify existing data
    - Request different data formats or additional details
    """
    
    def __init__(self, storage_dir: str = "data/sessions"):
        """Initialize the interactive session manager with persistence support."""
        self.contexts: Dict[str, InteractiveContext] = {}
        self.current_session_id: Optional[str] = None
        self.storage_dir = storage_dir
        
        # Create storage directory if it doesn't exist
        os.makedirs(self.storage_dir, exist_ok=True)
        logger.info(f"Interactive session manager initialized with storage: {self.storage_dir}")
        
    def start_session(self, session_id: str) -> InteractiveContext:
        """Start a new interactive session or load existing one from disk."""
        # Check if already in memory
        if session_id in self.contexts:
            self.current_session_id = session_id
            return self.contexts[session_id]
        
        # Try to load from disk
        if self.load_session(session_id):
            self.current_session_id = session_id
            return self.contexts[session_id]
        
        # Create new session
        context = InteractiveContext(session_id=session_id)
        self.contexts[session_id] = context
        self.current_session_id = session_id
        logger.info(f"Started new interactive session: {session_id}")
        return context
    
    def get_current_context(self) -> Optional[InteractiveContext]:
        """Get the current session context."""
        if self.current_session_id and self.current_session_id in self.contexts:
            return self.contexts[self.current_session_id]
        return None
    
    def get_context(self, session_id: str) -> Optional[InteractiveContext]:
        """Get a session context by ID."""
        return self.contexts.get(session_id)
    
    def is_modification_request(self, query: str) -> bool:
        """
        Detect if the query is requesting to modify the current data set.
        
        Args:
            query: User's input query
            
        Returns:
            True if this is a modification request
        """
        import re
        
        query_lower = query.lower()
        
        # Addition keywords
        add_keywords = [
            "add", "include", "also show", "also include", "plus",
            "with", "and also", "append", "insert"
        ]
        
        # Removal keywords  
        remove_keywords = [
            "remove", "exclude", "delete", "without", "drop",
            "hide", "omit", "take out", "get rid of"
        ]
        
        # Format modification keywords
        format_keywords = [
            "format as", "show as", "display as", "convert to",
            "in format", "as json", "as table", "as list"
        ]
        
        # Data type keywords
        data_keywords = [
            "snomed", "icd", "description", "code", "mapping",
            "concept", "relationship", "hierarchy"
        ]
        
        # Check for modification patterns
        has_modifier = any(keyword in query_lower for keyword in 
                          add_keywords + remove_keywords + format_keywords)
        has_data_reference = any(keyword in query_lower for keyword in data_keywords)
        
        # Also check for pronouns referring to current context
        context_references = ["this", "these", "current", "existing", "shown"]
        has_context_ref = any(ref in query_lower for ref in context_references)
        
        # NEW: Check if query contains ICD or SNOMED code patterns
        # ICD pattern: Letter followed by digits (e.g., R52, E11.9, I10)
        icd_pattern = r'\b[A-Z]\d{1,3}(?:\.\d+)?\b'
        # SNOMED pattern: 6-10 digit numbers
        snomed_pattern = r'\b\d{6,10}\b'
        
        has_code_pattern = bool(re.search(icd_pattern, query.upper()) or 
                                re.search(snomed_pattern, query))
        
        # If has modifier + code pattern, it's a modification request
        # E.g., "remove R52" or "add 73211009"
        if has_modifier and has_code_pattern:
            return True
        
        # Original logic: modifier + (data reference or context reference)
        return has_modifier and (has_data_reference or has_context_ref)
    
    def detect_modification_type(self, query: str) -> str:
        """
        Determine the type of modification being requested.
        
        Returns:
            'add', 'remove', 'format', 'filter', or 'modify'
        """
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["add", "include", "also show", "plus", "with"]):
            return "add"
        elif any(word in query_lower for word in ["remove", "exclude", "delete", "without"]):
            return "remove"
        elif any(word in query_lower for word in ["format", "show as", "display as", "convert"]):
            return "format"
        elif any(word in query_lower for word in ["filter", "only show", "just", "limit to"]):
            return "filter"
        else:
            return "modify"
    
    def extract_data_types(self, query: str) -> List[str]:
        """
        Extract what types of data are being referenced in the query.
        
        Returns:
            List of data types like ['snomed_code', 'icd_code', 'description']
        """
        query_lower = query.lower()
        data_types = []
        
        # Map keywords to data types
        type_mappings = {
            'snomed': 'snomed_code',
            'icd': 'icd_code', 
            'description': 'description',
            'name': 'name',
            'code': 'code',
            'mapping': 'mapping',
            'relationship': 'relationship',
            'hierarchy': 'hierarchy',
            'parent': 'parent_code',
            'child': 'child_code'
        }
        
        for keyword, data_type in type_mappings.items():
            if keyword in query_lower:
                data_types.append(data_type)
        
        return list(set(data_types))  # Remove duplicates
    
    def add_data_item(self, session_id: str, item: DataItem) -> bool:
        """Add a data item to the session context."""
        if session_id not in self.contexts:
            return False
            
        context = self.contexts[session_id]
        context.current_data[item.key] = item
        
        # Log the modification
        context.modifications.append({
            "action": "add",
            "item_type": item.item_type,
            "key": item.key,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"Added {item.item_type} {item.key} to session {session_id}")
        
        # Auto-save after modification
        self.auto_save_session(session_id)
        
        return True
    
    def remove_data_item(self, session_id: str, key: str) -> bool:
        """Remove a data item from the session context."""
        if session_id not in self.contexts:
            return False
            
        context = self.contexts[session_id]
        if key in context.current_data:
            removed_item = context.current_data.pop(key)
            
            # Log the modification
            context.modifications.append({
                "action": "remove", 
                "item_type": removed_item.item_type,
                "key": key,
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"Removed {key} from session {session_id}")
            
            # Auto-save after modification
            self.auto_save_session(session_id)
            
            return True
        return False
    
    def get_current_data_summary(self, session_id: str) -> str:
        """Get a summary of current data in the session."""
        if session_id not in self.contexts:
            return "No active session found."
            
        context = self.contexts[session_id]
        if not context.current_data:
            return "No data currently loaded in this session."
        
        summary_lines = ["**Current Data in Session:**"]
        
        # Group by data type
        by_type: Dict[str, List[DataItem]] = {}
        for item in context.current_data.values():
            if item.item_type not in by_type:
                by_type[item.item_type] = []
            by_type[item.item_type].append(item)
        
        # Format each type
        for data_type, items in by_type.items():
            summary_lines.append(f"\n**{data_type.replace('_', ' ').title()}s:**")
            for item in items:
                # Clean up value: replace HTML br tags with newlines for better readability
                cleaned_value = str(item.value)
                cleaned_value = cleaned_value.replace("<br>", "\n  ")
                cleaned_value = cleaned_value.replace("<br/>", "\n  ")
                cleaned_value = cleaned_value.replace("<br />", "\n  ")
                summary_lines.append(f"- {item.key}: {cleaned_value}")
        
        summary_lines.append(f"\nTotal items: {len(context.current_data)}")
        
        return "\n".join(summary_lines)
    
    def get_data_by_type(self, session_id: str, data_type: str) -> List[DataItem]:
        """Get all data items of a specific type from the session."""
        if session_id not in self.contexts:
            return []
            
        context = self.contexts[session_id]
        return [item for item in context.current_data.values() 
                if item.item_type == data_type]
    
    def clear_session(self, session_id: str) -> bool:
        """Clear all data from a session."""
        if session_id in self.contexts:
            self.contexts[session_id].current_data.clear()
            self.contexts[session_id].modifications.append({
                "action": "clear_all",
                "timestamp": datetime.now().isoformat()
            })
            logger.info(f"Cleared session {session_id}")
            return True
        return False
    
    def format_data_as_json(self, session_id: str) -> str:
        """Export current session data as JSON."""
        if session_id not in self.contexts:
            return json.dumps({"error": "Session not found"})
            
        context = self.contexts[session_id]
        export_data = {
            "session_id": session_id,
            "created_at": context.created_at.isoformat(),
            "data_count": len(context.current_data),
            "data": {}
        }
        
        for key, item in context.current_data.items():
            export_data["data"][key] = {
                "type": item.item_type,
                "value": item.value,
                "metadata": item.metadata,
                "added_at": item.added_at.isoformat(),
                "source_query": item.source_query
            }
        
        return json.dumps(export_data, indent=2)
    
    def format_data_as_table(self, session_id: str) -> str:
        """Format current session data as a markdown table."""
        if session_id not in self.contexts:
            return "| Error | Session not found |"
            
        context = self.contexts[session_id]
        if not context.current_data:
            return "| Info | No data in session |"
        
        # Create table headers
        table_lines = ["| Type | Key | Value | Added At |"]
        table_lines.append("|------|-----|-------|----------|")
        
        # Add data rows
        for item in context.current_data.values():
            formatted_time = item.added_at.strftime("%H:%M:%S")
            
            # Clean up value: replace HTML br tags and newlines with commas for table display
            cleaned_value = str(item.value)
            # First replace br tags with a marker
            cleaned_value = cleaned_value.replace("<br>", "|||")
            cleaned_value = cleaned_value.replace("<br/>", "|||")
            cleaned_value = cleaned_value.replace("<br />", "|||")
            # Remove any newlines and extra whitespace
            cleaned_value = " ".join(cleaned_value.split())
            # Replace markers with comma-space
            cleaned_value = cleaned_value.replace("|||", ", ")
            
            # Truncate very long values and add ellipsis
            if len(cleaned_value) > 150:
                cleaned_value = cleaned_value[:147] + "..."
            
            table_lines.append(f"| {item.item_type} | {item.key} | {cleaned_value} | {formatted_time} |")
        
        return "\n".join(table_lines)
    
    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """Get statistics about the current session."""
        if session_id not in self.contexts:
            return {"error": "Session not found"}
            
        context = self.contexts[session_id]
        
        # Count by data type
        type_counts = {}
        for item in context.current_data.values():
            type_counts[item.item_type] = type_counts.get(item.item_type, 0) + 1
        
        return {
            "session_id": session_id,
            "created_at": context.created_at.isoformat(),
            "total_items": len(context.current_data),
            "item_types": type_counts,
            "queries_processed": len(context.query_history),
            "modifications_made": len(context.modifications)
        }
    
    # ========================================================================
    # SESSION PERSISTENCE METHODS
    # ========================================================================
    
    def save_session(self, session_id: str) -> bool:
        """
        Save session data to disk.
        
        Args:
            session_id: ID of the session to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if session_id not in self.contexts:
                logger.warning(f"Cannot save session {session_id}: not found in memory")
                return False
            
            context = self.contexts[session_id]
            filepath = os.path.join(self.storage_dir, f"{session_id}.json")
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(context.to_dict(), f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Saved session data for {session_id} ({len(context.current_data)} items)")
            return True
            
        except Exception as e:
            logger.error(f"Error saving session {session_id}: {e}")
            return False
    
    def load_session(self, session_id: str) -> bool:
        """
        Load session data from disk.
        
        Args:
            session_id: ID of the session to load
            
        Returns:
            True if successful, False if file doesn't exist or error occurs
        """
        try:
            filepath = os.path.join(self.storage_dir, f"{session_id}.json")
            
            if not os.path.exists(filepath):
                return False
            
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            context = InteractiveContext.from_dict(data)
            self.contexts[session_id] = context
            
            logger.info(f"📂 Loaded session data for {session_id} ({len(context.current_data)} items)")
            return True
            
        except Exception as e:
            logger.error(f"Error loading session {session_id}: {e}")
            return False
    
    def auto_save_session(self, session_id: str) -> None:
        """
        Auto-save session after modifications. Logs errors but doesn't fail.
        
        Args:
            session_id: ID of the session to auto-save
        """
        try:
            self.save_session(session_id)
        except Exception as e:
            logger.error(f"Auto-save failed for session {session_id}: {e}")
    
    def set_active_chat(self, session_id: str) -> None:
        """
        Switch to a different chat session, loading from disk if needed.
        
        Args:
            session_id: ID of the session to activate
        """
        # Try to load from disk if not in memory
        if session_id not in self.contexts:
            loaded = self.load_session(session_id)
            if loaded:
                logger.info(f"🔄 Active chat set to: {session_id} (loaded from disk)")
            else:
                # Create new session
                self.start_session(session_id)
                logger.info(f"🔄 Active chat set to: {session_id} (new session)")
        else:
            logger.info(f"🔄 Active chat set to: {session_id} (already in memory)")
        
        self.current_session_id = session_id
    
    def has_session(self, session_id: str) -> bool:
        """
        Check if a session exists (in memory or on disk).
        
        Args:
            session_id: ID of the session to check
            
        Returns:
            True if session exists
        """
        if session_id in self.contexts:
            return True
        
        filepath = os.path.join(self.storage_dir, f"{session_id}.json")
        return os.path.exists(filepath)
    
    def save_all_sessions(self) -> int:
        """
        Save all active sessions to disk.
        
        Returns:
            Number of sessions successfully saved
        """
        saved_count = 0
        for session_id in self.contexts.keys():
            if self.save_session(session_id):
                saved_count += 1
        
        logger.info(f"💾 Saved {saved_count}/{len(self.contexts)} sessions to disk")
        return saved_count
    
    def list_saved_sessions(self) -> List[str]:
        """
        List all session IDs that have saved files.
        
        Returns:
            List of session IDs
        """
        try:
            if not os.path.exists(self.storage_dir):
                return []
            
            files = os.listdir(self.storage_dir)
            session_ids = [f.replace('.json', '') for f in files if f.endswith('.json')]
            return session_ids
            
        except Exception as e:
            logger.error(f"Error listing saved sessions: {e}")
            return []
    
    def clear_session(self, session_id: str, delete_file: bool = False) -> bool:
        """
        Clear session from memory and optionally delete from disk.
        
        Args:
            session_id: ID of the session to clear
            delete_file: If True, also delete the file from disk
            
        Returns:
            True if successful
        """
        try:
            # Remove from memory
            if session_id in self.contexts:
                del self.contexts[session_id]
                logger.info(f"🗑️ Cleared session {session_id} from memory")
            
            # Optionally delete file
            if delete_file:
                filepath = os.path.join(self.storage_dir, f"{session_id}.json")
                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.info(f"🗑️ Deleted session file: {filepath}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error clearing session {session_id}: {e}")
            return False
    
    def cleanup_old_sessions(self, max_age_days: int = 7, max_memory_sessions: int = 10) -> Dict[str, int]:
        """
        Clean up old sessions to prevent memory bloat and disk accumulation.
        
        Args:
            max_age_days: Delete session files older than this many days
            max_memory_sessions: Keep only this many sessions in memory
            
        Returns:
            Dict with cleanup statistics
        """
        try:
            from datetime import timedelta
            
            stats = {
                'memory_sessions_before': len(self.contexts),
                'memory_sessions_cleared': 0,
                'disk_files_deleted': 0,
                'disk_files_total': 0
            }
            
            # 1. Clean up memory: keep only most recent sessions
            if len(self.contexts) > max_memory_sessions:
                # Sort by creation time, keep newest
                sorted_sessions = sorted(
                    self.contexts.items(),
                    key=lambda x: x[1].created_at,
                    reverse=True
                )
                
                # Keep only the newest max_memory_sessions
                sessions_to_keep = {sid: ctx for sid, ctx in sorted_sessions[:max_memory_sessions]}
                sessions_to_remove = [sid for sid, _ in sorted_sessions[max_memory_sessions:]]
                
                for session_id in sessions_to_remove:
                    # Save before removing from memory
                    self.save_session(session_id)
                    del self.contexts[session_id]
                    stats['memory_sessions_cleared'] += 1
                
                self.contexts = sessions_to_keep
                logger.info(f"🧹 Cleared {stats['memory_sessions_cleared']} sessions from memory (kept {len(self.contexts)})")
            
            # 2. Clean up disk: delete old session files
            if os.path.exists(self.storage_dir):
                cutoff_time = datetime.now() - timedelta(days=max_age_days)
                
                for filename in os.listdir(self.storage_dir):
                    if not filename.endswith('.json'):
                        continue
                    
                    filepath = os.path.join(self.storage_dir, filename)
                    stats['disk_files_total'] += 1
                    
                    # Check file age
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    
                    if file_mtime < cutoff_time:
                        os.remove(filepath)
                        stats['disk_files_deleted'] += 1
                        logger.debug(f"🗑️ Deleted old session file: {filename} (age: {datetime.now() - file_mtime})")
            
            logger.info(f"🧹 Session cleanup complete: memory cleared={stats['memory_sessions_cleared']}, disk deleted={stats['disk_files_deleted']}/{stats['disk_files_total']}")
            return stats
            
        except Exception as e:
            logger.error(f"Error during session cleanup: {e}")
            return {'error': str(e)}
    
    def get_memory_usage_stats(self) -> Dict[str, Any]:
        """
        Get statistics about current memory usage by sessions.
        
        Returns:
            Dict with memory usage statistics
        """
        total_items = 0
        total_size_estimate = 0
        
        for session_id, context in self.contexts.items():
            session_items = len(context.current_data)
            total_items += session_items
            
            # Rough size estimate (bytes)
            for item in context.current_data.values():
                total_size_estimate += len(str(item.value))
                total_size_estimate += len(str(item.metadata))
        
        return {
            'total_sessions_in_memory': len(self.contexts),
            'total_data_items': total_items,
            'estimated_size_bytes': total_size_estimate,
            'estimated_size_mb': round(total_size_estimate / (1024 * 1024), 2),
            'sessions': {
                sid: {
                    'items': len(ctx.current_data),
                    'created': ctx.created_at.isoformat(),
                    'modifications': len(ctx.modifications)
                }
                for sid, ctx in self.contexts.items()
            }
        }

# Global instance for easy access
interactive_session = InteractiveSession()