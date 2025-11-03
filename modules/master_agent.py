"""
The MasterAgent orchestrates interactions between different specialized agents.

This module defines the MasterAgent class, which acts as a router to delegate
user queries to the appropriate agent, such as the ChatAgent for general
conversation or the IcdAgent for specific ICD code lookups. It initializes
all available agents and provides a unified entry point for processing chat
requests.
"""

import os
import logging
import json
import warnings
from typing import TypedDict

# Suppress torch warnings before importing memory modules
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', message='.*torch.classes.*')
warnings.filterwarnings('ignore', message='.*Tried to instantiate class.*')

from modules.agents.chat_agent import ChatAgent
from modules.agents.icd_agent import IcdAgent
from modules.agents.snomed_agent import SnomedAgent
from modules.agents.concept_set_extractor_agent import ConceptSetExtractorAgent
from modules.interactive_session import interactive_session
from modules.config import CONCEPT_SET_CLASSIFICATION_PROMPT, create_openai_client
from modules.memory.memory_manager import memory_manager

logger = logging.getLogger(__name__)


class MasterAgentState(TypedDict):
    """State definition for the master agent."""
    user_input: str
    agent_type: str
    context: str
    response: str
    error: str

class MasterAgent:
    """
    A central agent that routes user queries to specialized sub-agents.

    The MasterAgent initializes and manages a collection of agents (e.g.,
    ChatAgent, IcdAgent). It determines the appropriate agent to handle a
    given query based on the `agent_type` parameter and formats the response
    accordingly.
    """

    def __init__(self):
        """
        Initializes the MasterAgent and all its sub-agents.

        This constructor sets up the ChatAgent and IcdAgent, logging the
        successful initialization of each. It also performs a quick validation
        of the Azure OpenAI client configuration to ensure connectivity.

        Raises:
            Exception: If any of the agents fail to initialize.
        """
        try:
            # Initialize Agents
            self.chat_agent = ChatAgent()
            self.icd_agent = IcdAgent()
            self.snomed_agent = SnomedAgent()
            self.concept_set_extractor_agent = ConceptSetExtractorAgent()
            logger.info("✅ All agents initialized successfully")

        except Exception as e:
            logger.exception("Failed to initialize agents")
            raise e

        # Initialize conversation history
        try:
            from modules.conversation_history import ConversationHistory
            self.conversation_history = ConversationHistory()
            logger.info("✅ Conversation history initialized")
        except Exception as e:
            logger.exception("Failed to initialize conversation history")
            raise e

        # Quick validation of Azure OpenAI deployment
        try:
            self.client = create_openai_client()
            logger.info("✅ AzureOpenAI client initialized for MasterAgent")
        except Exception as e:
            logger.exception("Failed to initialize AzureOpenAI client")
            raise e

    def _is_concept_set_query(self, query: str) -> bool:
        """
        Uses an LLM to classify if the user's query is about a concept set.
        """
        try:
            prompt = CONCEPT_SET_CLASSIFICATION_PROMPT.format(query=query)
            response = self.client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=5,
                temperature=0.0,
            )
            is_concept_set = response.choices[0].message.content.strip().lower()
            logger.info(f"Concept set classification for '{query}': {is_concept_set}")
            return "true" in is_concept_set
        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return False

    def _classify_agent_type(self, query: str) -> str:
        """
        Classifies the query to determine the appropriate agent type.
        """
        query_lower = query.lower()
        
        # Check for SNOMED-related keywords (check first as it's more specific)
        snomed_keywords = [
            "snomed", "snomed ct", "snomedct", "sct", "snomed code",
            "clinical term", "clinical terminology", "snomed concept"
        ]
        
        if any(keyword in query_lower for keyword in snomed_keywords):
            logger.info(f"SNOMED query detected: '{query}' -> routing to 'snomed' agent")
            return "snomed"
        
        # Check for ICD-related keywords
        icd_keywords = [
            "icd", "icd-10", "icd10", "i10", "i11", "i20", "i21", "i50",
            "code i", "diagnosis code", "medical code", "billing code"
        ]
        
        # Check if query contains specific ICD patterns
        import re
        icd_pattern = r'\b[a-z]\d{2}(?:\.\d+)?\b'  # Matches ICD patterns like I10, E11.9, etc.
        
        if any(keyword in query_lower for keyword in icd_keywords) or re.search(icd_pattern, query_lower):
            logger.info(f"ICD query detected: '{query}' -> routing to 'icd' agent")
            return "icd"
        
        # Default to chat agent
        logger.info(f"General query detected: '{query}' -> routing to 'chat' agent")
        return "chat"

    def chat(self, query: str, agent_type: str = "auto", session_id: str = "default"):
        """
        Processes a chat query by routing it to the specified agent or workflow.
        Enhanced with memory system, interactive sessions, and conversation history tracking.
        """
        # Add user message to conversation history
        self.conversation_history.add_user_message(query)
        
        # Auto-detect agent type if not specified
        if agent_type == "auto":
            agent_type = self._classify_agent_type(query)
            logger.info(f"📋 Agent classification: '{query}' → agent_type='{agent_type}'")
        
        # Get relevant context from memory system
        working_memory = self.conversation_history.get_recent_context(num_messages=10)
        session_context = ""
        
        # Check if there's an active session with previous ICD data
        has_session_data = self._has_active_session(session_id)
        if has_session_data:
            session_context = self._get_session_context_string(session_id) or ""
        
        # Get comprehensive context from memory manager
        memory_context = memory_manager.get_relevant_context(
            current_query=query,
            working_memory=working_memory,
            session_context=session_context,
            max_tokens=2000,
            include_episodic=True,
            include_semantic=True
        )
        
        logger.info(f"📋 Session check: has_session_data={has_session_data}, memory_context={'available' if memory_context else 'none'}, session_id={session_id}")
        
        # For follow-up questions, use the chat agent with RAG context
        # This allows format changes like "show as table" to work with stored data
        if has_session_data and len(self.conversation_history.messages) > 0:
            # Check if query is explicitly requesting a NEW search
            is_explicit_new_search = (
                # Must have both search intent AND medical term
                any(keyword in query.lower() for keyword in [
                    "search for", "find", "look up", "get me", "retrieve"
                ]) and 
                any(keyword in query.lower() for keyword in [
                    "new", "different", "other", "more"
                ])
            ) or (
                # Or explicitly asking about a new condition
                any(phrase in query.lower() for phrase in [
                    "what is the code for", "find code for", "search for code"
                ])
            )
            
            # If it's not explicitly a new search, treat it as a follow-up
            is_concept_set = self._is_concept_set_query(query)
            logger.info(f"📋 Checking follow-up: is_explicit_new_search={is_explicit_new_search}, is_concept_set={is_concept_set}")
            
            if not is_explicit_new_search and not is_concept_set:
                logger.info(f"📋 ✅ Follow-up confirmed: Using chat agent with comprehensive memory context")
                
                # Use comprehensive memory context (includes session data, past conversations, facts)
                context_to_use = memory_context if memory_context else session_context
                
                if context_to_use:
                    logger.info(f"📋 State: Using memory context ({len(context_to_use)} chars)")
                    
                    # Use chat agent with comprehensive context
                    response = self.chat_agent.process(query, context=context_to_use)
                    logger.info(f"📋 State: Response generated ({len(response)} chars) using memory system")
                    self.conversation_history.add_assistant_message(response, agent_type="chat")
                    
                    # Store conversation turn in memory
                    memory_manager.process_conversation_turn(
                        session_id=session_id,
                        user_query=query,
                        assistant_response=response
                    )
                    
                    return response
                else:
                    logger.warning(f"📋 Follow-up detected but no context available")
                    # Continue to standard routing
        
        # Initialize state
        state = MasterAgentState(user_input=query, agent_type=agent_type, context="", response="", error="")
        logger.info(f"📋 State initialized: agent_type='{agent_type}', user_input='{query[:50]}...'")

        # Step 1: Classify user intent
        if self._is_concept_set_query(query):
            logger.info("Concept set query detected. Starting concept set workflow.")
            response = self._concept_set_workflow(state)
            self.conversation_history.add_assistant_message(response, agent_type="concept_set")
            return response

        # Enhanced routing with session support and memory
        logger.info(f"📋 Routing to '{agent_type}' agent (standard query path - NOT follow-up)")
        if agent_type == "chat":
            # Use comprehensive memory context (includes session data, episodic memory, facts)
            context_to_use = memory_context if memory_context else (session_context if has_session_data else None)
            
            if context_to_use:
                logger.info(f"📋 State: Using memory context ({len(context_to_use)} chars) for chat agent")
            else:
                logger.info(f"📋 State: ⚠️ No context available, using chat agent without memory")
            
            response = self.chat_agent.process(query, context=context_to_use)
            logger.info(f"📋 State: Chat response generated ({len(response)} chars) {'WITH' if context_to_use else 'WITHOUT'} context")
            self.conversation_history.add_assistant_message(response, agent_type="chat")
            
            # Store conversation turn in memory system
            memory_manager.process_conversation_turn(
                session_id=session_id,
                user_query=query,
                assistant_response=response,
                metadata={'agent_type': 'chat'}
            )
            
            return response
        elif agent_type == "icd":
            # Use interactive processing for ICD queries
            logger.info(f"📋 State: Routing to ICD agent with interactive session support")
            response = self._chat_icd_interactive(query, session_id)
            logger.info(f"📋 State: ICD response generated ({len(response)} chars), stored in session")
            self.conversation_history.add_assistant_message(response, agent_type="icd")
            
            # Store ICD conversation turn in memory system
            memory_manager.process_conversation_turn(
                session_id=session_id,
                user_query=query,
                assistant_response=response,
                metadata={'agent_type': 'icd', 'has_codes': True}
            )
            
            return response
        elif agent_type == "snomed":
            # Use interactive processing for SNOMED queries
            logger.info(f"📋 State: Routing to SNOMED agent with interactive session support")
            response = self._chat_snomed_interactive(query, session_id)
            logger.info(f"📋 State: SNOMED response generated ({len(response)} chars), stored in session")
            self.conversation_history.add_assistant_message(response, agent_type="snomed")
            
            # Store SNOMED conversation turn in memory system
            memory_manager.process_conversation_turn(
                session_id=session_id,
                user_query=query,
                assistant_response=response,
                metadata={'agent_type': 'snomed', 'has_concepts': True}
            )
            
            return response
        else:
            response = f"❌ Unknown agent type: {agent_type}"
            self.conversation_history.add_assistant_message(response, agent_type="master")
            return response
    
    def _has_active_session(self, session_id: str) -> bool:
        """Check if there's an active session with data."""
        # Check if session exists in contexts
        if session_id in interactive_session.contexts:
            context = interactive_session.contexts[session_id]
            return len(context.current_data) > 0
        return False
    
    def _get_session_context_string(self, session_id: str) -> str:
        """
        Retrieve RAG context from session as a formatted string with ALL available fields.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Formatted string with ICD codes, descriptions, and ALL available fields
            (including OHDSI, SAB, etc.), or None if no data
        """
        import re
        
        def clean_html_tags(text):
            """Remove HTML tags from text, replacing br with comma-space."""
            if not text or not isinstance(text, str):
                return text
            text = re.sub(r'<br\s*/?>', ', ', text, flags=re.IGNORECASE)
            text = re.sub(r'<[^>]+>', '', text)
            text = re.sub(r',\s*,', ',', text)
            return text.strip()
        
        session_context = interactive_session.get_context(session_id)
        if session_context and session_context.current_data:
            context_lines = []
            for item in session_context.current_data.values():
                # Start with basic code and description (already cleaned when stored)
                line = f"[{item.key}] {item.value}"
                
                # Add metadata fields if this is SNOMED data from agent
                if "source" in item.metadata:
                    line += f"\n  metadata: {item.metadata}"
                
                # Add ALL additional fields from the full document
                if "full_document" in item.metadata:
                    doc = item.metadata["full_document"]
                    
                    # Add OHDSI data if available (clean any br tags in JSON)
                    if "OHDSI" in doc and doc["OHDSI"]:
                        ohdsi_cleaned = clean_html_tags(doc['OHDSI'])
                        line += f"\n  OHDSI: {ohdsi_cleaned}"
                    
                    # Add SAB (source abbreviation) if available
                    if "SAB" in doc and doc["SAB"]:
                        line += f"\n  SAB: {doc['SAB']}"
                    
                    # Add any other fields that might be useful (clean br tags)
                    for field, value in doc.items():
                        if field not in ["CODE", "STR", "id", "OHDSI", "SAB"] and value:
                            cleaned_value = clean_html_tags(str(value))
                            line += f"\n  {field}: {cleaned_value}"
                
                context_lines.append(line)
            
            context_str = "\n\n".join(context_lines)
            logger.debug(f"📋 Retrieved {len(session_context.current_data)} codes with full document data from session {session_id}")
            return context_str
        logger.debug(f"📋 No context data found in session {session_id}")
        return None
    
    def _chat_icd_interactive(self, query: str, session_id: str):
        """
        Enhanced ICD query handling with interactive session support.
        """
        try:
            # Use interactive processing
            result = self.icd_agent.process_interactive(query, session_id)
            
            if "error" in result:
                return result["error"]

            # Return the processed response with session context
            processed_response = result.get("processed_response", "")
            if processed_response:
                return processed_response
            
            # Fallback to regular processing if no interactive response
            return self._chat_icd(query)
            
        except Exception as e:
            logger.exception("Interactive ICD chat failed")
            return f"An error occurred: {e}"

    def _chat_snomed_interactive(self, query: str, session_id: str):
        """
        Enhanced SNOMED query handling with interactive session support.
        """
        try:
            # Use interactive processing
            result = self.snomed_agent.process_interactive(query, session_id)
            
            if "error" in result:
                return result["error"]

            # Return the processed response with session context
            processed_response = result.get("processed_response", "")
            if processed_response:
                return processed_response
            
            # Fallback to regular processing if no interactive response
            return self._chat_snomed(query)
            
        except Exception as e:
            logger.exception("Interactive SNOMED chat failed")
            return f"An error occurred: {e}"

    def _chat_snomed(self, query: str):
        """
        Handles a simple, direct SNOMED query using the SnomedAgent.
        """
        try:
            data = self.snomed_agent.process(query)
            
            if "error" in data:
                return data["error"]
            
            # Return processed response if available
            if "processed_response" in data:
                return data["processed_response"]
            
            return "No SNOMED concepts found for your query."
            
        except Exception as e:
            logger.exception("SNOMED query failed")
            return f"An error occurred: {e}"

    def _concept_set_workflow(self, state: MasterAgentState) -> str:
        """
        Executes the multi-step workflow for creating a concept set.
        """
        # Step 1: Call IcdAgent to get data
        logger.info("Workflow Step 1: Calling IcdAgent")
        icd_result = self.icd_agent.process(state["user_input"])
        if "error" in icd_result:
            return f"Error during ICD search: {icd_result['error']}"
        
        # Step 2: Update context in state
        # ConceptSetExtractorAgent expects raw JSON data, not processed response
        state["context"] = icd_result.get("data", "")
        context_size = len(state["context"]) if state["context"] else 0
        logger.info(f"📋 State updated: context set ({context_size} chars) with ICD data from search")

        # Step 3: Call ConceptSetExtractorAgent to process the context
        logger.info("Workflow Step 3: Calling ConceptSetExtractorAgent")
        extracted_data = self.concept_set_extractor_agent.process(state["context"])
        if "error" in extracted_data:
             return f"Error during data extraction: {extracted_data['error']}"

        # Step 4: Call ChatAgent to format the final response
        logger.info("Workflow Step 4: Calling ChatAgent for final formatting.")
        final_response = self.chat_agent.format_concept_set(
            original_query=state["user_input"],
            context_data=extracted_data
        )
        
        return final_response

    def _chat_icd(self, query: str):
        """
        Handles a simple, direct ICD query using the IcdAgent.
        """
        try:
            data = self.icd_agent.process(query)
            if "error" in data:
                return data["error"]

            # For direct ICD queries, return the processed response with citations
            processed_response = data.get("processed_response", "")
            if processed_response:
                return processed_response
            
            # Fallback to formatted raw data if no processed response
            raw_results = json.loads(data.get("data", "[]"))
            
            output_lines = ["ICD Search Results:"]
            for r in raw_results:
                label = r.get("document", {}).get("STR", "N/A")
                code = r.get("document", {}).get("CODE", "N/A")
                score = r.get("score", 0.0)
                output_lines.append(f"Code: {code}, Label: {label}, Score: {score:.4f}")

            return "\n".join(output_lines)
        except Exception as e:
            logger.exception("Direct ICD chat failed")
            return f"An error occurred: {e}"
    
    def get_info(self):
        """
        Get system information about the master agent.
        
        Returns:
            dict: System info with endpoint, deployment, API version, and available agents.
        """
        return {
            "endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", "Not configured"),
            "deployment": os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "Not configured"),
            "api_version": os.getenv("AZURE_OPENAI_API_VERSION", "Not configured"),
            "specialized_agents": ["chat", "icd", "concept_set_extractor"]
        }
    
    def get_agent_status(self):
        """
        Get status of all agents.
        
        Returns:
            dict: Status information for all agents.
        """
        return {
            "master_agent": "active",
            "specialized_agents": {
                "chat": "active",
                "icd": "active", 
                "concept_set_extractor": "active"
            }
        }
    
    def get_conversation_history(self):
        """
        Get conversation history and statistics.
        
        Returns:
            dict: History info with messages and statistics.
        """
        if not hasattr(self, 'conversation_history'):
            from modules.conversation_history import ConversationHistory
            self.conversation_history = ConversationHistory()
        
        messages = self.conversation_history.messages
        user_msgs = sum(1 for m in messages if m.role == "user")
        assistant_msgs = sum(1 for m in messages if m.role == "assistant")
        
        agent_usage = {}
        for m in messages:
            if m.role == "assistant" and m.agent_type:
                agent_usage[m.agent_type] = agent_usage.get(m.agent_type, 0) + 1
        
        return {
            "messages": messages,
            "stats": {
                "total_messages": len(messages),
                "user_messages": user_msgs,
                "assistant_messages": assistant_msgs,
                "agent_usage": agent_usage
            }
        }
    
    def get_memory_stats(self):
        """
        Get statistics about the memory system.
        
        Returns:
            dict: Memory system statistics including episodic and semantic memory.
        """
        try:
            return memory_manager.get_memory_stats()
        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {
                'error': str(e),
                'episodic_memory': {'total_episodes': 0},
                'semantic_memory': {'total_facts': 0}
            }
    
    def save_conversation_history(self):
        """
        Save conversation history to file.
        
        Returns:
            bool: True if successful, False otherwise.
        """
        if not hasattr(self, 'conversation_history'):
            from modules.conversation_history import ConversationHistory
            self.conversation_history = ConversationHistory()
        
        return self.conversation_history.save()
    
    def clear_conversation_history(self):
        """Clear the conversation history."""
        if not hasattr(self, 'conversation_history'):
            from modules.conversation_history import ConversationHistory
            self.conversation_history = ConversationHistory()
        
        self.conversation_history.clear()
        logger.info("Conversation history cleared")
    
    def shutdown(self):
        """Gracefully shutdown the agent system."""
        logger.info("Shutting down MasterAgent...")
        self.save_conversation_history()
        logger.info("MasterAgent shutdown complete")
