"""
Interactive Session Manager for Dynamic Data Manipulation

This module provides functionality for maintaining interactive chat sessions
where analysts can request to add, remove, or modify information like SNOMED
codes, ICD descriptions, and other data elements during their conversation.
"""

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

@dataclass
class InteractiveContext:
    """Maintains the current state of an interactive session."""
    session_id: str
    current_data: Dict[str, DataItem] = field(default_factory=dict)
    query_history: List[str] = field(default_factory=list)
    modifications: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

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
    
    def __init__(self):
        """Initialize the interactive session manager."""
        self.contexts: Dict[str, InteractiveContext] = {}
        self.current_session_id: Optional[str] = None
        
    def start_session(self, session_id: str) -> InteractiveContext:
        """Start a new interactive session."""
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

# Global instance for easy access
interactive_session = InteractiveSession()