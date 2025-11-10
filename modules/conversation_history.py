"""
Manages the conversation history for the chat application.

This module provides the `ConversationHistory` class, which is responsible for
storing, managing, and persisting chat messages. It supports adding messages from
different roles (user, assistant, system), maintaining a rolling window of recent
messages, and serializing the history to and from a JSON file. The `ChatMessage`
dataclass defines the structure for individual messages.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging
import json
import os
import re

logger = logging.getLogger(__name__)

@dataclass
class ChatMessage:
    """
    A structured representation of a single message in a conversation.

    This dataclass holds the content of a message, its role (e.g., 'user',
    'assistant'), a timestamp, and optional metadata about the agent that
    generated it.
    """
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: datetime
    agent_type: Optional[str] = None  # Which agent generated this response
    metadata: Optional[Dict[str, Any]] = None

class ConversationHistory:
    """
    Manages a list of chat messages, providing functionality for history
    retention, formatting, and persistence.

    This class acts as a stateful manager for a conversation. It keeps messages
    in a list, enforces a maximum history size, and offers methods to format the
    history for different consumers (e.g., LLMs, LangChain) and to save/load
    the history to a file.
    """
    
    def __init__(self, max_messages: int = 20, storage_file: str = "data/conversation_history.json"):
        """
        Initializes the ConversationHistory manager.

        Args:
            max_messages (int): The maximum number of messages to keep in the
                                rolling history window.
            storage_file (str): The path to the JSON file used for persisting
                                the conversation history.
        """
        self.max_messages = max_messages
        self.storage_file = storage_file
        self.messages: List[ChatMessage] = []
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(storage_file), exist_ok=True)
        
        logger.info(f"ConversationHistory initialized with max_messages={max_messages}, storage_file={storage_file}")
    
    def add_user_message(self, content: str) -> None:
        """
        Adds a message from the user to the history.

        Args:
            content (str): The text content of the user's message.
        """
        message = ChatMessage(
            role="user",
            content=content,
            timestamp=datetime.now()
        )
        self._add_message(message)
        logger.debug(f"Added user message: {content[:50]}...")
    
    def add_assistant_message(self, content: str, agent_type: str = "master", metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Adds a message from the assistant (an agent) to the history.

        Args:
            content (str): The text content of the assistant's response.
            agent_type (str): The identifier of the agent that generated the
                              response (e.g., 'chat', 'icd').
            metadata (dict, optional): Any additional metadata to store with
                                       the message.
        """
        message = ChatMessage(
            role="assistant",
            content=content,
            timestamp=datetime.now(),
            agent_type=agent_type,
            metadata=metadata or {}
        )
        self._add_message(message)
        logger.debug(f"Added assistant message from {agent_type}: {content[:50]}...")
    
    def add_system_message(self, content: str) -> None:
        """
        Adds a system-level message to the history.

        System messages are typically used to provide instructions or context to
        the language model.

        Args:
            content (str): The content of the system message.
        """
        message = ChatMessage(
            role="system",
            content=content,
            timestamp=datetime.now()
        )
        self._add_message(message)
        logger.debug(f"Added system message: {content[:50]}...")
    
    def _add_message(self, message: ChatMessage) -> None:
        """
        A private helper to add a message and trim the history if it exceeds
        the maximum size.

        Args:
            message (ChatMessage): The message object to add.
        """
        self.messages.append(message)
        
        # Maintain rolling window - keep only the last max_messages
        if len(self.messages) > self.max_messages:
            removed_count = len(self.messages) - self.max_messages
            self.messages = self.messages[-self.max_messages:]
            logger.debug(f"Trimmed {removed_count} old messages from history")
    
    def get_messages_for_llm(self, include_system: bool = True) -> List[Dict[str, str]]:
        """
        Formats the message history for consumption by a generic LLM API.

        This method converts the list of `ChatMessage` objects into a list of
        dictionaries, each with 'role' and 'content' keys, which is a common
        format for chat-based language models.

        Args:
            include_system (bool): If True, system messages are included in the
                                   output.

        Returns:
            List[Dict[str, str]]: A list of message dictionaries.
        """
        formatted_messages = []
        
        for message in self.messages:
            if not include_system and message.role == "system":
                continue
                
            formatted_message = {
                "role": message.role,
                "content": message.content
            }
            
            # Add agent context for assistant messages
            if message.role == "assistant" and message.agent_type:
                formatted_message["content"] = f"[{message.agent_type} agent]: {message.content}"
            
            formatted_messages.append(formatted_message)
        
        return formatted_messages
    
    def get_langchain_messages(self):
        """
        Converts the message history into a list of LangChain message objects.

        This method is useful for integrating with LangChain components that
        expect a list of `HumanMessage`, `AIMessage`, or `SystemMessage` objects.

        Returns:
            list: A list of LangChain message objects.
        """
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
        
        langchain_messages = []
        
        for message in self.messages:
            content = message.content
            
            # Add agent context for assistant messages
            if message.role == "assistant" and message.agent_type:
                content = f"[{message.agent_type} agent]: {content}"
            
            if message.role == "user":
                langchain_messages.append(HumanMessage(content=content))
            elif message.role == "assistant":
                langchain_messages.append(AIMessage(content=content))
            elif message.role == "system":
                langchain_messages.append(SystemMessage(content=content))
        
        return langchain_messages
    
    def get_recent_context(self, num_messages: int = 10) -> str:
        """
        Generates a human-readable string of the most recent conversation.

        Args:
            num_messages (int): The number of recent messages to include in the
                                formatted string.

        Returns:
            str: A formatted string representing the recent conversation history.
        """
        recent_messages = self.messages[-num_messages:] if num_messages > 0 else self.messages
        
        if not recent_messages:
            return "No previous conversation context."
        
        context_lines = ["Recent conversation context:"]
        
        for message in recent_messages:
            timestamp_str = message.timestamp.strftime("%H:%M")
            
            if message.role == "user":
                context_lines.append(f"[{timestamp_str}] User: {message.content}")
            elif message.role == "assistant":
                agent_info = f" ({message.agent_type})" if message.agent_type else ""
                context_lines.append(f"[{timestamp_str}] Assistant{agent_info}: {message.content}")
        
        return "\n".join(context_lines)
    
    def get_last_n_responses(self, n: int = 3) -> str:
        """
        Gets the last N assistant responses to use as context for the next request.
        
        This provides the AI with recent conversation context to maintain continuity
        and understand what has been discussed.

        Args:
            n (int): The number of recent assistant responses to retrieve (default: 3).

        Returns:
            str: A formatted string containing the last N assistant responses,
                 or empty string if no responses exist.
        """
        # Filter for assistant messages only
        assistant_messages = [m for m in self.messages if m.role == "assistant"]
        
        if not assistant_messages:
            return ""
        
        # Get the last N assistant messages
        recent_responses = assistant_messages[-n:] if len(assistant_messages) >= n else assistant_messages
        
        if not recent_responses:
            return ""
        
        # Format as context
        context_lines = ["Previous responses for context:"]
        
        for i, message in enumerate(recent_responses, 1):
            timestamp_str = message.timestamp.strftime("%H:%M")
            agent_info = f" [{message.agent_type}]" if message.agent_type else ""
            
            # Process content for proper formatting
            content = message.content
            
            # Normalize line breaks (handle both \r\n and \n)
            content = content.replace('\r\n', '\n').replace('\r', '\n')
            
            # Collapse multiple consecutive line breaks into max 2
            content = re.sub(r'\n{3,}', '\n\n', content)
            
            # Truncate very long responses to avoid token bloat
            if len(content) > 500:
                # Try to truncate at a line break if possible
                truncate_pos = content.rfind('\n', 0, 500)
                if truncate_pos > 300:  # Only use line break if it's reasonably far in
                    content = content[:truncate_pos] + f"\n... [truncated, {len(message.content)} chars total]"
                else:
                    content = content[:500] + f"... [truncated, {len(message.content)} chars total]"
            
            # Add response header
            context_lines.append(f"\nResponse {i}{agent_info} ({timestamp_str}):")
            
            # Indent the content for better visual separation
            indented_content = '\n'.join('  ' + line if line.strip() else '' for line in content.split('\n'))
            context_lines.append(indented_content)
        
        return "\n".join(context_lines)
    
    def clear_history(self) -> None:
        """
        Removes all messages from the in-memory history.
        """
        message_count = len(self.messages)
        self.messages.clear()
        logger.info(f"Cleared {message_count} messages from conversation history")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Computes and returns statistics about the current conversation history.

        The statistics include total message counts, counts by role, agent usage,
        and timestamps of the oldest and newest messages.

        Returns:
            Dict[str, Any]: A dictionary of conversation statistics.
        """
        if not self.messages:
            return {
                "total_messages": 0,
                "user_messages": 0,
                "assistant_messages": 0,
                "system_messages": 0,
                "agent_usage": {},
                "oldest_message": None,
                "newest_message": None
            }
        
        stats = {
            "total_messages": len(self.messages),
            "user_messages": sum(1 for m in self.messages if m.role == "user"),
            "assistant_messages": sum(1 for m in self.messages if m.role == "assistant"),
            "system_messages": sum(1 for m in self.messages if m.role == "system"),
            "agent_usage": {},
            "oldest_message": self.messages[0].timestamp.isoformat(),
            "newest_message": self.messages[-1].timestamp.isoformat()
        }
        
        # Count usage by agent type
        for message in self.messages:
            if message.role == "assistant" and message.agent_type:
                agent_type = message.agent_type
                stats["agent_usage"][agent_type] = stats["agent_usage"].get(agent_type, 0) + 1
        
        return stats
    
    def __len__(self) -> int:
        """
        Returns the current number of messages in the history.
        """
        return len(self.messages)
    
    def __str__(self) -> str:
        """
        Returns a string representation of the ConversationHistory object.
        """
        return f"ConversationHistory({len(self.messages)} messages, max={self.max_messages})"
    
    def save_to_disk(self) -> bool:
        """
        Serializes the current conversation history to a JSON file.

        The data is saved to the `storage_file` path specified during
        initialization.

        Returns:
            bool: True if the save operation was successful, False otherwise.
        """
        try:
            # CRITICAL: Enforce rolling window BEFORE saving to prevent file bloat
            if len(self.messages) > self.max_messages:
                original_count = len(self.messages)
                self.messages = self.messages[-self.max_messages:]
                logger.warning(f"Trimmed conversation history before save: {original_count} → {len(self.messages)} messages")
            
            # Convert messages to serializable format
            serializable_messages = []
            for message in self.messages:
                msg_dict = {
                    "role": message.role,
                    "content": message.content,
                    "timestamp": message.timestamp.isoformat(),
                    "agent_type": message.agent_type,
                    "metadata": message.metadata
                }
                serializable_messages.append(msg_dict)
            
            # Save to file
            data = {
                "max_messages": self.max_messages,
                "saved_at": datetime.now().isoformat(),
                "messages": serializable_messages
            }
            
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved {len(self.messages)} messages to {self.storage_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving conversation history: {e}")
            return False
    
    def load_from_disk(self) -> bool:
        """
        Loads and deserializes conversation history from a JSON file.

        This method replaces the in-memory history with the content of the
        `storage_file`.

        Returns:
            bool: True if the load operation was successful, False otherwise.
        """
        try:
            if not os.path.exists(self.storage_file):
                logger.info(f"No conversation history file found at {self.storage_file}")
                return False
            
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Clear current messages
            self.messages.clear()
            
            # Restore messages
            for msg_dict in data.get("messages", []):
                message = ChatMessage(
                    role=msg_dict["role"],
                    content=msg_dict["content"],
                    timestamp=datetime.fromisoformat(msg_dict["timestamp"]),
                    agent_type=msg_dict.get("agent_type"),
                    metadata=msg_dict.get("metadata")
                )
                self.messages.append(message)
            
            # Update max_messages if it changed
            if "max_messages" in data:
                self.max_messages = data["max_messages"]
            
            logger.info(f"Loaded {len(self.messages)} messages from {self.storage_file}")
            logger.info(f"Last saved at: {data.get('saved_at', 'unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading conversation history: {e}")
            return False
    
    def delete_saved_history(self) -> bool:
        """
        Deletes the persisted conversation history file from the disk.

        Returns:
            bool: True if the file was deleted or did not exist, False if an
                  error occurred during deletion.
        """
        try:
            if os.path.exists(self.storage_file):
                os.remove(self.storage_file)
                logger.info(f"Deleted conversation history file: {self.storage_file}")
                return True
            else:
                logger.info(f"No conversation history file to delete at {self.storage_file}")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting conversation history file: {e}")
            return False
    
    def save_to_custom_file(self, filename: str) -> bool:
        """
        Saves the conversation history to a custom-named file in the 'saved/'
        directory.

        This is useful for creating snapshots or named exports of conversations.

        Args:
            filename (str): The name for the output file. A '.json' extension
                            will be added if not present.

        Returns:
            bool: True if the save operation was successful, False otherwise.
        """
        try:
            # Ensure saved directory exists at project root
            saved_dir = "saved"
            os.makedirs(saved_dir, exist_ok=True)
            
            # Add .json extension if not present
            if not filename.endswith('.json'):
                filename = f"{filename}.json"
            
            # Construct full path
            custom_file = os.path.join(saved_dir, filename)
            
            # CRITICAL: Enforce rolling window BEFORE saving to prevent file bloat
            if len(self.messages) > self.max_messages:
                original_count = len(self.messages)
                self.messages = self.messages[-self.max_messages:]
                logger.warning(f"Trimmed conversation history before custom save: {original_count} → {len(self.messages)} messages")
            
            # Convert messages to serializable format
            serializable_messages = []
            for message in self.messages:
                msg_dict = {
                    "role": message.role,
                    "content": message.content,
                    "timestamp": message.timestamp.isoformat(),
                    "agent_type": message.agent_type,
                    "metadata": message.metadata
                }
                serializable_messages.append(msg_dict)
            
            # Save to file
            data = {
                "max_messages": self.max_messages,
                "saved_at": datetime.now().isoformat(),
                "messages": serializable_messages
            }
            
            with open(custom_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved {len(self.messages)} messages to {custom_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving conversation history to custom file: {e}")
            return False
    
    def save(self) -> bool:
        """
        Alias for save_to_disk() for backward compatibility.
        
        Returns:
            bool: True if the save operation was successful, False otherwise.
        """
        return self.save_to_disk()
    
    def clear(self) -> None:
        """
        Alias for clear_history() for backward compatibility.
        """
        self.clear_history()
