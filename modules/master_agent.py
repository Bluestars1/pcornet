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
from typing import TypedDict, Optional, List

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
# MEMORY SYSTEM with LAZY LOADING - model loads on first use only
from modules.memory.memory_manager import memory_manager
from modules.memory.embeddings import embedding_service

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
            logger.info("Initializing ChatAgent...")
            self.chat_agent = ChatAgent()
            logger.info("✅ ChatAgent initialized")
            
            logger.info("Initializing IcdAgent...")
            self.icd_agent = IcdAgent()
            logger.info("✅ IcdAgent initialized")
            
            logger.info("Initializing SnomedAgent...")
            self.snomed_agent = SnomedAgent()
            logger.info("✅ SnomedAgent initialized")
            
            logger.info("Initializing ConceptSetExtractorAgent...")
            self.concept_set_extractor_agent = ConceptSetExtractorAgent()
            logger.info("✅ ConceptSetExtractorAgent initialized")
            
            logger.info("✅ All agents initialized successfully")

        except Exception as e:
            logger.exception("Failed to initialize agents")
            raise e

        # Initialize conversation history
        try:
            logger.info("Initializing conversation history...")
            from modules.conversation_history import ConversationHistory
            self.conversation_history = ConversationHistory()
            logger.info("✅ Conversation history initialized")
        except Exception as e:
            logger.exception("Failed to initialize conversation history")
            raise e

        # Quick validation of Azure OpenAI deployment
        try:
            logger.info("Initializing Azure OpenAI client...")
            self.client = create_openai_client()
            logger.info("✅ AzureOpenAI client initialized for MasterAgent")
        except Exception as e:
            logger.exception("Failed to initialize AzureOpenAI client")
            raise e
        
        # Chat switching support
        self.current_chat_id: Optional[str] = None
        logger.info("✅ Chat switching support initialized")
        
        # In-memory cache for concept set data (per session)
        # Structure: {session_id: [{'name': str, 'raw_data': str, 'formatted': str, 'query': str, 'timestamp': float}]}
        self.concept_set_cache = {}
        logger.info("✅ Concept set cache initialized")

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
        # Chat switching detection - save before switching
        if self.current_chat_id != session_id:
            logger.info(f"🔄 Chat switch detected: {self.current_chat_id} → {session_id}")
            
            # Save current chat before switching
            if self.current_chat_id and interactive_session.has_session(self.current_chat_id):
                interactive_session.save_session(self.current_chat_id)
                logger.info(f"💾 Saved current chat data before switching")
            
            # Switch to new chat (auto-loads if exists)
            interactive_session.set_active_chat(session_id)
            self.current_chat_id = session_id
        
        # Add user message to conversation history
        self.conversation_history.add_user_message(query)
        
        # Auto-detect agent type if not specified
        if agent_type == "auto":
            agent_type = self._classify_agent_type(query)
            logger.info(f"[MasterAgent] 📋 Agent classification: '{query}' → agent_type='{agent_type}'")
        
        # Get comprehensive context from memory system (lazy-loaded)
        working_memory = self.conversation_history.get_recent_context(num_messages=10)
        session_context = ""
        
        # Check if there's an active session with previous ICD data
        has_session_data = self._has_active_session(session_id)
        if has_session_data:
            session_context = self._get_session_context_string(session_id, query) or ""
        
        # Get context from memory manager (model loads on first use only)
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
                logger.info(f"[MasterAgent] 📋 ✅ Follow-up confirmed: Using chat agent with comprehensive memory context")
                
                # Use comprehensive memory context (includes session data, past conversations, facts)
                context_to_use = memory_context if memory_context else session_context
                
                if context_to_use:
                    logger.info(f"📋 State: Using memory context ({len(context_to_use)} chars)")
                    
                    # Use chat agent with comprehensive context
                    response = self.chat_agent.process(query, context=context_to_use)
                    logger.info(f"📋 State: Response generated ({len(response)} chars) using memory context")
                    self.conversation_history.add_assistant_message(response, agent_type="chat")
                    
                    # Store conversation turn in memory (lazy-loaded)
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
        logger.info(f"[MasterAgent] 📋 State initialized: agent_type='{agent_type}', user_input='{query[:50]}...'")

        # Step 1: Classify user intent
        if self._is_concept_set_query(query):
            logger.info("[MasterAgent] Concept set query detected. Starting concept set workflow")
            response = self._concept_set_workflow(state)
            self.conversation_history.add_assistant_message(response, agent_type="concept_set")
            return response
        
        # Step 2: Check for concept set follow-up (modify existing concept set)
        # Only check if there are concept sets in cache to avoid false positives
        if self._get_concept_sets(session_id) and self._is_concept_set_followup(query):
            logger.info("[MasterAgent] Concept set follow-up detected")
            response = self._handle_concept_set_followup(query, session_id)
            self.conversation_history.add_assistant_message(response, agent_type="concept_set_followup")
            return response

        # Enhanced routing with session support and memory
        logger.info(f"[MasterAgent] 📋 Routing to '{agent_type}' agent (standard query path - NOT follow-up)")
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
            
            # Store conversation turn in memory (lazy-loaded)
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
            
            # Store ICD conversation turn in memory (lazy-loaded)
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
            
            # Store SNOMED conversation turn in memory (lazy-loaded)
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
    
    def _get_session_context_string(self, session_id: str, current_query: str = None, relevance_threshold: float = None) -> str:
        """
        Retrieve RAG context from session as a formatted string with ALL available fields.
        Optionally filters by semantic relevance to current query (Azure AI Search style).
        
        Args:
            session_id: Session identifier
            current_query: Optional query to filter by relevance (semantic similarity)
            relevance_threshold: Minimum similarity score (0-1) to include item (default: 0.3)
            
        Returns:
            Formatted string with ICD codes, descriptions, and ALL available fields
            (including OHDSI, SAB, etc.), filtered by relevance if query provided
        """
        import re
        
        # Read threshold from environment if not provided
        if relevance_threshold is None:
            relevance_threshold = float(os.getenv("SESSION_RELEVANCE_THRESHOLD", "0.3"))
        
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
            # Get all items
            all_items = list(session_context.current_data.values())
            
            # Filter by semantic relevance if query provided
            if current_query:
                relevant_items = self._filter_items_by_relevance(
                    all_items, 
                    current_query, 
                    relevance_threshold
                )
                logger.info(f"[MasterAgent] 🔍 Semantic filtering: {len(all_items)} total → {len(relevant_items)} relevant (threshold: {relevance_threshold})")
            else:
                relevant_items = all_items
                logger.debug(f"📋 No query filter - including all {len(all_items)} session items")
            
            # Format relevant items
            context_lines = []
            for item in relevant_items:
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
            if current_query:
                logger.info(f"[MasterAgent] 📋 Retrieved {len(relevant_items)}/{len(session_context.current_data)} relevant codes for query '{current_query[:50]}...'")
            else:
                logger.debug(f"📋 Retrieved {len(session_context.current_data)} codes with full document data from session {session_id}")
            return context_str
        logger.debug(f"📋 No context data found in session {session_id}")
        return None
    
    def _filter_items_by_relevance(self, items: List, query: str, threshold: float) -> List:
        """
        Filter session items by semantic relevance to query (Azure AI Search style).
        
        Args:
            items: List of DataItem objects to filter
            query: Current user query
            threshold: Minimum similarity score (0-1) to include
            
        Returns:
            List of relevant DataItem objects sorted by relevance score
        """
        try:
            if not items or not query:
                return items
            
            # Generate query embedding
            query_embedding = embedding_service.embed_text(query)
            if not query_embedding:
                logger.warning("Failed to generate query embedding - returning all items")
                return items
            
            # Calculate relevance scores for each item
            scored_items = []
            for item in items:
                # Create searchable text from item (code + description + metadata)
                item_text = f"{item.key} {item.value}"
                if item.metadata and 'full_document' in item.metadata:
                    doc = item.metadata['full_document']
                    if 'STR' in doc:
                        item_text += f" {doc['STR']}"
                
                # Generate item embedding
                item_embedding = embedding_service.embed_text(item_text)
                if not item_embedding:
                    continue
                
                # Compute similarity score
                similarity = embedding_service.compute_similarity(query_embedding, item_embedding)
                
                # Include if above threshold
                if similarity >= threshold:
                    scored_items.append((item, similarity))
                    logger.debug(f"✓ {item.key}: similarity={similarity:.3f} (relevant)")
                else:
                    logger.debug(f"✗ {item.key}: similarity={similarity:.3f} (filtered out)")
            
            # Sort by relevance score (highest first)
            scored_items.sort(key=lambda x: x[1], reverse=True)
            relevant_items = [item for item, score in scored_items]
            
            return relevant_items
            
        except Exception as e:
            logger.error(f"Error filtering items by relevance: {e}")
            return items  # Fallback to all items on error
    
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

    def _store_concept_set_data(self, session_id: str, raw_data: str, formatted_response: str, 
                                 original_query: str, primary_condition: str):
        """
        Store concept set data in memory for follow-up queries.
        
        Args:
            session_id: Session/chat ID
            raw_data: Raw extracted data from ConceptSetExtractorAgent
            formatted_response: Final formatted table
            original_query: User's original query
            primary_condition: Primary medical condition (used as name)
        """
        import time
        
        if session_id not in self.concept_set_cache:
            self.concept_set_cache[session_id] = []
        
        concept_set_entry = {
            'name': primary_condition,
            'raw_data': raw_data,
            'formatted': formatted_response,
            'query': original_query,
            'timestamp': time.time()
        }
        
        self.concept_set_cache[session_id].append(concept_set_entry)
        
        logger.info(f"[MasterAgent] 💾 Stored concept set '{primary_condition}' in cache (total: {len(self.concept_set_cache[session_id])})")
    
    def _get_concept_sets(self, session_id: str) -> List[dict]:
        """Get all concept sets for a session, most recent first."""
        if session_id not in self.concept_set_cache:
            return []
        
        # Return sorted by timestamp, most recent first
        return sorted(self.concept_set_cache[session_id], key=lambda x: x['timestamp'], reverse=True)
    
    def _is_concept_set_followup(self, query: str) -> bool:
        """
        Detect if query is about modifying an existing concept set.
        
        Patterns:
        - Remove/exclude codes
        - Add/show columns
        - Filter by condition
        - Format changes
        """
        query_lower = query.lower()
        
        followup_patterns = [
            'remove', 'exclude', 'filter out', 'hide', 'delete',
            'add column', 'show column', 'include column', 'add field',
            'only show', 'just show', 'only include', 'show only',
            'without', 'except', 'excluding',
            'modify', 'change', 'update', 'edit',
            'from that table', 'from the table', 'from table',
            'from that', 'from the concept set', 'from concept set'
        ]
        
        return any(pattern in query_lower for pattern in followup_patterns)
    
    def _identify_target_concept_set(self, query: str, session_id: str) -> Optional[dict]:
        """
        Identify which concept set the user is referring to.
        
        Returns:
            - Concept set dict if identified
            - None if needs clarification
        """
        concept_sets = self._get_concept_sets(session_id)
        
        if not concept_sets:
            return None
        
        # If only one concept set exists, use it
        if len(concept_sets) == 1:
            logger.info(f"[MasterAgent] 📋 Using only available concept set: '{concept_sets[0]['name']}'")
            return concept_sets[0]
        
        query_lower = query.lower()
        
        # Check for "most recent" or "latest"
        if any(phrase in query_lower for phrase in ['most recent', 'latest', 'last one', 'recent one']):
            logger.info(f"[MasterAgent] 📋 Using most recent concept set: '{concept_sets[0]['name']}'")
            return concept_sets[0]  # Already sorted by timestamp, most recent first
        
        # Check if query mentions a specific condition
        for cs in concept_sets:
            condition_name = cs['name'].lower()
            if condition_name in query_lower:
                logger.info(f"[MasterAgent] 📋 Identified target concept set: '{cs['name']}'")
                return cs
        
        # Ambiguous - return None to trigger clarification
        logger.info(f"[MasterAgent] ⚠️ Ambiguous: {len(concept_sets)} concept sets available, none explicitly mentioned")
        return None
    
    def _handle_concept_set_followup(self, query: str, session_id: str) -> str:
        """
        Handle follow-up modifications to concept set.
        
        Args:
            query: User's follow-up query (e.g., "Remove fibromyalgia codes")
            session_id: Current session ID
            
        Returns:
            Modified table or clarification request
        """
        concept_sets = self._get_concept_sets(session_id)
        
        if not concept_sets:
            return "No concept set found to modify. Please create a concept set first."
        
        # Identify target concept set
        target_cs = self._identify_target_concept_set(query, session_id)
        
        if target_cs is None:
            # Multiple concept sets, need clarification
            cs_list = "\n".join([f"{i+1}. {cs['name']}" for i, cs in enumerate(concept_sets)])
            return f"""I found {len(concept_sets)} concept sets in this session:

{cs_list}

Please specify which one you'd like to modify by mentioning the condition name, or say "the most recent one"."""
        
        # Route to chat agent with raw data as context
        logger.info(f"[MasterAgent] 🔧 Processing follow-up for concept set '{target_cs['name']}'")
        logger.info(f"[MasterAgent] 📊 Raw data size: {len(target_cs['raw_data'])} chars, {target_cs['raw_data'].count('Code:')} codes")
        
        # Build context with raw data and instructions
        context_with_instructions = f"""CONCEPT SET MODIFICATION TASK

Original Query: {target_cs['query']}

AVAILABLE CONCEPT SET DATA (ALL CODES):
{target_cs['raw_data']}

CRITICAL INSTRUCTIONS FOR MODIFICATION:
1. The data above contains ALL codes from the original concept set
2. Parse each line to extract: Code, Label, Score, OHDSI, SAB fields
3. Apply the user's modification request (remove, filter, add columns, etc.)
4. When REMOVING codes: Filter out ONLY the specified codes, KEEP ALL OTHERS
5. When ADDING columns: Extract data from the OHDSI or other fields
6. Rebuild the COMPLETE table with modifications applied
7. Use the same markdown table format as the original
8. Include ALL codes that were NOT removed
9. Do NOT truncate the table or only show examples
10. Return the FULL modified table

User's Modification Request: {query}

Now generate the COMPLETE modified concept set table with ALL remaining codes:"""
        
        # Use chat agent with higher token limit for large tables
        # Concept sets can be large (30+ codes with SNOMED mappings = 3000-5000 tokens)
        from langchain_openai import AzureChatOpenAI
        from langchain.schema import HumanMessage, SystemMessage
        from modules.config import get_config
        import os
        
        cfg = get_config()
        
        # Create LLM with higher token limit for concept set modifications
        llm_for_large_tables = AzureChatOpenAI(
            azure_endpoint=cfg.azure_openai_endpoint,
            api_key=cfg.azure_openai_api_key,
            api_version=cfg.azure_openai_api_version,
            deployment_name=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
            temperature=0.3,
            max_tokens=8000,  # Much higher limit for large tables
        )
        
        system_msg = SystemMessage(content=context_with_instructions)
        user_msg = HumanMessage(content=query)
        
        # Use retry wrapper for rate limit handling
        from modules.config import invoke_llm_with_retry
        
        try:
            response_obj = invoke_llm_with_retry(
                lambda: llm_for_large_tables.invoke([system_msg, user_msg]),
                max_retries=3,
                initial_delay=2
            )
            response = response_obj.content
            logger.info(f"[MasterAgent] ✅ Generated modified table ({len(response)} chars)")
            return response
            
        except Exception as e:
            logger.error(f"[MasterAgent] ❌ Error generating modified table: {e}")
            return f"⚠️ Unable to generate modified table. Please try again in a moment.\n\nError: {str(e)}"
    
    def _extract_and_expand_medical_query(self, query: str) -> str:
        """
        Extract the medical condition and expand to include related/causative conditions.
        
        Examples:
            "Create diabetes concept set" → "diabetes OR diabetic OR DM"
            "Chronic pain codes" → "chronic pain OR fibromyalgia OR arthritis OR neuropathy"
            "Heart failure" → "heart failure OR cardiac failure OR CHF OR congestive heart failure"
        
        Args:
            query: Full user query
            
        Returns:
            Expanded search query with primary and related conditions
        """
        try:
            # Step 1: Extract primary medical condition
            extraction_prompt = f"""Extract the PRIMARY medical condition from this query.
            
Query: "{query}"

RETURN ONLY THE MAIN MEDICAL CONDITION (2-4 words). Do not include:
- "concept set", "codes", "ICD", "SNOMED"
- Action words like "create", "show", "find"

Examples:
- "Create diabetes concept set" → diabetes
- "Show hypertension ICD codes" → hypertension  
- "Chronic pain with comorbidities" → chronic pain

Primary condition:"""
            
            response = self.client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
                messages=[{"role": "user", "content": extraction_prompt}],
                max_tokens=20,
                temperature=0.0,
            )
            primary_condition = response.choices[0].message.content.strip().lower()
            logger.info(f"[MasterAgent] 📋 Extracted primary condition: '{primary_condition}'")
            
            # Step 2: Expand to include related/causative conditions
            expansion_prompt = f"""You are a medical terminology expert. For the given medical condition, identify RELATED and CAUSATIVE conditions that should be included in a comprehensive search.

Primary Condition: "{primary_condition}"

Identify:
1. Common synonyms and abbreviations
2. Specific types/subtypes of this condition
3. Conditions that commonly CAUSE this condition
4. Related conditions that often co-occur

IMPORTANT RULES:
- Include 3-8 related terms (don't be excessive)
- Use standard medical terminology
- Focus on clinically relevant relationships
- Each term should be 1-4 words maximum

Examples:

Input: "diabetes"
Output: diabetes, diabetic, type 1 diabetes, type 2 diabetes, gestational diabetes, DM

Input: "chronic pain"
Output: chronic pain, fibromyalgia, arthritis, neuropathic pain, musculoskeletal pain, back pain

Input: "hypertension"
Output: hypertension, high blood pressure, essential hypertension, secondary hypertension, HTN

Input: "heart failure"
Output: heart failure, cardiac failure, CHF, congestive heart failure, systolic heart failure, diastolic heart failure

Input: "stroke"
Output: stroke, cerebrovascular accident, CVA, ischemic stroke, hemorrhagic stroke, cerebral infarction

Now provide ONLY the comma-separated list of related terms for: "{primary_condition}"

Output:"""
            
            response = self.client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
                messages=[{"role": "user", "content": expansion_prompt}],
                max_tokens=150,
                temperature=0.3,  # Slight creativity for medical relationships
            )
            expanded_terms = response.choices[0].message.content.strip()
            
            # Parse comma-separated terms and clean them
            terms = [term.strip().lower() for term in expanded_terms.split(',')]
            terms = [term for term in terms if term]  # Remove empty strings
            
            # Build search query with OR operators
            search_query = ' OR '.join(terms)
            
            logger.info(f"[MasterAgent] 🔍 Expanded to {len(terms)} related terms: {', '.join(terms[:5])}{'...' if len(terms) > 5 else ''}")
            logger.info(f"[MasterAgent] 📋 Search query: '{search_query[:100]}{'...' if len(search_query) > 100 else ''}'")
            
            return search_query
            
        except Exception as e:
            logger.error(f"[MasterAgent] Failed to expand medical query, using original query: {e}")
            # Fallback: try simple extraction
            try:
                response = self.client.chat.completions.create(
                    model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
                    messages=[{"role": "user", "content": f"Extract medical condition from: {query}"}],
                    max_tokens=20,
                    temperature=0.0,
                )
                return response.choices[0].message.content.strip().lower()
            except:
                return query
    
    def _concept_set_workflow(self, state: MasterAgentState) -> str:
        """
        Executes the multi-step workflow for creating a concept set.
        """
        # Step 0: Extract and expand medical query to include related conditions
        expanded_query = self._extract_and_expand_medical_query(state["user_input"])
        logger.info(f"[MasterAgent] 🔍 Searching with expanded query: '{expanded_query[:80]}{'...' if len(expanded_query) > 80 else ''}'")
        
        # Step 1: Call IcdAgent to get data
        logger.info("[MasterAgent] Workflow Step 1: Calling IcdAgent")
        icd_result = self.icd_agent.process(expanded_query)
        if "error" in icd_result:
            return f"Error during ICD search: {icd_result['error']}"
        
        # Step 2: Update context in state
        # ConceptSetExtractorAgent expects raw JSON data, not processed response
        state["context"] = icd_result.get("data", "")
        context_size = len(state["context"]) if state["context"] else 0
        logger.info(f"[MasterAgent] 📋 State updated: context set ({context_size} chars) with ICD data from search")

        # Step 3: Call ConceptSetExtractorAgent to process the context
        logger.info("[MasterAgent] Workflow Step 3: Calling ConceptSetExtractorAgent")
        extracted_data = self.concept_set_extractor_agent.process(state["context"])
        if "error" in extracted_data:
             return f"Error during data extraction: {extracted_data['error']}"

        # Step 4: Call ChatAgent to format the final response
        logger.info("[MasterAgent] Workflow Step 4: Calling ChatAgent for final formatting")
        final_response = self.chat_agent.format_concept_set(
            original_query=state["user_input"],
            context_data=extracted_data
        )
        
        # Step 5: Store concept set data for follow-up queries
        self._store_concept_set_data(
            session_id=self.current_chat_id,
            raw_data=extracted_data,
            formatted_response=final_response,
            original_query=state["user_input"],
            primary_condition=expanded_query.split(' OR ')[0]  # First term as name
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
