"""
A specialized agent for querying the PCORnet ICD index in Azure AI Search.

This module defines the IcdAgent, which is responsible for searching an Azure
AI Search index containing International Classification of Diseases (ICD) codes.
It uses an LLM to process search results and generate responses with proper
citations referencing the document IDs where information was found.
"""

# modules/agents/icd_agent.py
import os
import json
import logging
import re
from typing import Dict, List, Any
import modules.search_tool
import modules.relationship_search
from modules.interactive_session import interactive_session, DataItem
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

class IcdAgent:
    """
    An agent that queries an Azure AI Search index for ICD code information.

    This agent uses the `Search` helper to connect to a specified Azure AI
    Search endpoint and index to perform searches for ICD codes. It processes
    the results using an LLM and generates responses with proper citations
    referencing the document IDs where information was found.
    """

    def __init__(self, index="icd"):
        """
        Initializes the IcdAgent.
        
        Args:
            index (str): The index registry key or direct index name to query.
                Default is "icd" which uses the index registry.
        """
        self.index_name = index
        self.last_retrieved_documents = []
        
        # RelationshipSearch is instantiated per query (not initialized here)
        # It will be created dynamically when searching for SNOMED mappings
        logger.info("✅ IcdAgent initialized (RelationshipSearch will be used per query)")
        
        # Initialize LLM client
        try:
            self.llm = self._create_llm()
            logger.info("✅ IcdAgent initialized with LLM")
        except Exception as e:
            logger.error(f"Failed to initialize IcdAgent LLM: {e}")
            raise e

    def _create_llm(self):
        """Creates and returns an LLM client for processing search results."""
        from modules.config import create_chat_llm
        
        return create_chat_llm()  # Uses configured AGENT_MAX_TOKENS

    def process(self, query: str) -> dict:
        """
        Performs a hybrid search in the ICD index and processes results with LLM.

        This method searches for ICD codes, processes the results with an LLM to
        generate a comprehensive response, and includes proper citations referencing
        the document IDs where information was found. Also handles REL segment 
        relationship queries.

        Args:
            query (str): The search query from the user.

        Returns:
            dict: A dictionary with 'data' key containing JSON string of raw results
                  and 'processed_response' key containing the LLM response with citations,
                  or 'error' key if search fails.
        """
        # Check for predefined concept sets first
        if "heart disease concept set" in query.lower():
            concept_set_docs = [
                {"document": {"id": "I20", "title": "Angina pectoris", "STR": "Angina pectoris", "CODE": "I20"}},
                {"document": {"id": "I21", "title": "Acute myocardial infarction", "STR": "Acute myocardial infarction", "CODE": "I21"}},
                {"document": {"id": "I50", "title": "Heart failure", "STR": "Heart failure", "CODE": "I50"}},
            ]
            response = self._get_heart_disease_concept_set()
            return {"data": json.dumps(concept_set_docs), "processed_response": response}
        
        # Check if this is a relationship query
        if self._is_relationship_query(query):
            return self._process_relationship_query(query)
            
        try:
            from modules.config import get_config
            config = get_config()
            
            search = modules.search_tool.Search(
                index=self.index_name,
                query=query,
                top=config.search_top_k
            )
            results = search.run()
            self.last_retrieved_documents = results

            if not results:
                return {"data": "[]", "processed_response": "No ICD codes found for your query."}

            # Generate LLM response with search context
            response = self._generate_llm_response(query, results)
            
            # Post-process to normalize citations
            response = self._normalize_citations(response, results)
            
            # Return both raw results for backward compatibility and processed response
            return {
                "data": json.dumps(results),
                "processed_response": response
            }

        except modules.search_tool.SearchError as e:
            logger.exception("ICD search failed")
            return {"error": f"Search operation failed: {e}"}
        except Exception as e:
            logger.exception("ICD processing failed")
            return {"error": f"An error occurred: {e}"}

    def process_with_history(self, query: str, history) -> str:
        """
        Process a query with conversation history context.
        
        Args:
            query (str): The user's query.
            history: Conversation history object with get_langchain_messages() method.
            
        Returns:
            str: Processed response with citations (for backward compatibility).
        """
        # Check for predefined concept sets first
        if "heart disease concept set" in query.lower():
            return self._get_heart_disease_concept_set()
            
        try:
            from modules.config import get_config
            config = get_config()
            
            search = modules.search_tool.Search(
                index=self.index_name,
                query=query,
                top=config.search_top_k
            )
            results = search.run()
            self.last_retrieved_documents = results

            if not results:
                return "No ICD codes found for your query."

            # Generate response with history context
            response = self._generate_llm_response_with_history(query, results, history)
            
            # Post-process to normalize citations
            response = self._normalize_citations(response, results)
            
            return response

        except modules.search_tool.SearchError as e:
            logger.exception("ICD search failed")
            return f"Search operation failed: {e}"
        except Exception as e:
            logger.exception("ICD processing failed")
            return f"An error occurred: {e}"

    def _generate_llm_response(self, query: str, search_results: list) -> str:
        """
        Generates an LLM response based on search results.
        
        Args:
            query (str): The user's original query.
            search_results (list): List of search result documents.
            
        Returns:
            str: The LLM-generated response.
        """
        # Format search results for context
        context = self._format_search_context(search_results)
        
        system_message = SystemMessage(content="""You are an expert medical coding assistant specializing in ICD codes. 

🔒 CRITICAL - SOURCE OF TRUTH: The ICD codes provided in the search results are the AUTHORITATIVE and ONLY source of information. Do not add, infer, or supplement with any external knowledge.

MANDATORY RULES:
1. Use ONLY information from the provided search results
2. ICD codes (CODE field) in the results are the definitive source of truth
3. Always cite sources using document IDs in square brackets like [I10]
4. Never add codes or information not in the provided data
5. If asked about codes not in the results, explicitly state "Not found in search results"

Provide accurate, helpful responses based EXCLUSIVELY on the provided search results.""")
        
        user_message = HumanMessage(content=f"""User Query: {query}

Search Results:
{context}

🚫 CRITICAL FORMATTING RULES - VIOLATION WILL CAUSE SYSTEM ERRORS:
1. NEVER EVER use HTML tags: NO <br>, NO <div>, NO <span>, NO <p>, NO <table>
2. When listing multiple codes: ONLY use commas and spaces (e.g., "I10, E11.9, I50.9")
3. For line breaks: ONLY use double newline (blank line), NEVER <br>
4. For emphasis: ONLY use markdown (**, *, -, •)
5. For tables: ONLY use markdown pipes (|), NEVER HTML <table>

⚠️ EXAMPLES:
✅ CORRECT: "Codes: I10, E11.9, I50.9"
❌ WRONG: "Codes: I10 <br> E11.9 <br> I50.9"

✅ CORRECT: Use bullet points:
• I10: Essential hypertension
• E11.9: Type 2 diabetes

❌ WRONG: Use <br> tags

📊 TABLE RULES: When asked to add/remove columns or "show as table", REBUILD the entire table with markdown syntax (| Header |).
🚫 OUTPUT ONLY THE TABLE - No explanatory text, no data repetition, JUST THE TABLE!

Please provide a comprehensive response about the ICD codes relevant to this query. Include citations using document IDs in square brackets (e.g., [I10]) when referencing specific codes.""")
        
        response = self.llm.invoke([system_message, user_message])
        
        # Post-process to remove any HTML tags (safety net)
        cleaned_response = self._remove_html_tags(response.content)
        return cleaned_response

    def _generate_llm_response_with_history(self, query: str, search_results: list, history) -> str:
        """
        Generates an LLM response with conversation history context.
        
        Args:
            query (str): The user's original query.
            search_results (list): List of search result documents.
            history: Conversation history object.
            
        Returns:
            str: The LLM-generated response.
        """
        # Get conversation history
        history_messages = history.get_langchain_messages() if history else []
        
        # Format search results for context
        context = self._format_search_context(search_results)
        
        system_message = SystemMessage(content="""You are an expert medical coding assistant specializing in ICD codes. 

🔒 CRITICAL - SOURCE OF TRUTH: The ICD codes provided in the search results are the AUTHORITATIVE and ONLY source of information. Do not add, infer, or supplement with any external knowledge.

MANDATORY RULES:
1. Use ONLY information from the provided search results and conversation history
2. ICD codes (CODE field) in the results are the definitive source of truth
3. Always cite sources using document IDs in square brackets like [I10]
4. Never add codes or information not in the provided data
5. If asked about codes not in the results, explicitly state "Not found in search results"

Provide accurate, helpful responses based EXCLUSIVELY on the provided search results and conversation context.""")
        
        # Combine history with current query and context
        messages = [system_message] + history_messages[-10:]  # Last 10 messages for context
        
        current_message = HumanMessage(content=f"""User Query: {query}

Search Results:
{context}

🚫 CRITICAL FORMATTING RULES - VIOLATION WILL CAUSE SYSTEM ERRORS:
1. NEVER EVER use HTML tags: NO <br>, NO <div>, NO <span>, NO <p>, NO <table>
2. When listing multiple codes: ONLY use commas and spaces (e.g., "I10, E11.9, I50.9")
3. For line breaks: ONLY use double newline (blank line), NEVER <br>
4. For emphasis: ONLY use markdown (**, *, -, •)
5. For tables: ONLY use markdown pipes (|), NEVER HTML <table>

⚠️ EXAMPLES:
✅ CORRECT: "Codes: I10, E11.9, I50.9"
❌ WRONG: "Codes: I10 <br> E11.9 <br> I50.9"

✅ CORRECT: Use bullet points:
• I10: Essential hypertension
• E11.9: Type 2 diabetes

❌ WRONG: Use <br> tags

📊 TABLE RULES: When asked to add/remove columns or "show as table", REBUILD the entire table with markdown syntax (| Header |).
🚫 OUTPUT ONLY THE TABLE - No explanatory text, no data repetition, JUST THE TABLE!

Please provide a comprehensive response about the ICD codes relevant to this query. Include citations using document IDs in square brackets (e.g., [I10]) when referencing specific codes.""")
        
        messages.append(current_message)
        
        response = self.llm.invoke(messages)
        
        # Post-process to remove any HTML tags (safety net)
        cleaned_response = self._remove_html_tags(response.content)
        return cleaned_response
    
    def _remove_html_tags(self, text: str) -> str:
        """
        Remove HTML tags from text as a safety measure.
        Replaces br tags with commas, removes other HTML tags.
        Preserves newlines for proper markdown table formatting.
        """
        import re
        
        # Replace br tags with comma-space
        text = re.sub(r'<br\s*/?>', ', ', text, flags=re.IGNORECASE)
        
        # Remove any other HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Clean up multiple commas
        text = re.sub(r',\s*,', ',', text)
        
        # Clean up spaces but PRESERVE newlines
        # Replace multiple spaces with single space, but keep newlines
        text = re.sub(r' +', ' ', text)  # Multiple spaces -> single space
        text = re.sub(r' *\n *', '\n', text)  # Clean spaces around newlines
        
        return text.strip()

    def _format_search_context(self, search_results: list) -> str:
        """
        Formats search results into a context string for the LLM.
        
        Args:
            search_results (list): List of search result documents.
            
        Returns:
            str: Formatted context string.
        """
        context_parts = []
        
        for result in search_results:
            doc = result.get("document", {})
            doc_id = doc.get("id", "Unknown")
            title = doc.get("title", doc.get("STR", ""))
            content = doc.get("content", "")
            score = result.get("score", 0.0)
            
            context_part = f"Document ID: {doc_id}\nTitle: {title}\nContent: {content}\nRelevance Score: {score:.3f}\n"
            context_parts.append(context_part)
        
        return "\n---\n".join(context_parts)

    def _normalize_citations(self, response: str, search_results: list) -> str:
        """
        Normalizes citations in the response to ensure proper formatting.
        
        This method ensures that:
        1. ICD codes are properly bracketed (e.g., I10 becomes [I10])
        2. Unsupported citations are marked as [UNSUPPORTED_CITATION]
        3. Only valid document IDs from search results are cited
        
        Args:
            response (str): The LLM-generated response.
            search_results (list): List of search result documents.
            
        Returns:
            str: Response with normalized citations.
        """
        # Get valid document IDs from search results
        valid_ids = set()
        for result in search_results:
            doc_id = result.get("document", {}).get("id")
            if doc_id:
                valid_ids.add(doc_id)
        
        logger.debug(f"Normalizing citations. Valid IDs: {valid_ids}, Response: {response[:100]}...")
        
        # Find and normalize ICD code patterns (e.g., I10, E11.9)
        icd_pattern = r'\b([A-Z]\d{2}(?:\.\d+)?)\b'
        
        def normalize_icd_citation(match):
            code = match.group(1)
            if code in valid_ids:
                return f'[{code}]'
            return code  # Leave as-is if not in search results
        
        response = re.sub(icd_pattern, normalize_icd_citation, response)
        
        # Replace unsupported citation patterns
        response = re.sub(r'\[EXTERNAL\]', '[UNSUPPORTED_CITATION]', response)
        
        return response

    def _is_relationship_query(self, query: str) -> bool:
        """
        Determines if a query is asking for relationship/hierarchy information.
        
        Args:
            query (str): The user's query.
            
        Returns:
            bool: True if this appears to be a relationship query.
        """
        relationship_keywords = [
            "parent", "child", "hierarchy", "relationship", "related to",
            "parent code", "child code", "parent of", "child of",
            "snomed mapping", "snomed code", "maps to", "mapped to",
            "is a", "part of", "belongs to", "under", "above",
            "subcategory", "category", "classification"
        ]
        
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in relationship_keywords)

    def _process_relationship_query(self, query: str) -> dict:
        """
        Process queries specifically about relationships and hierarchies.
        
        Args:
            query (str): The relationship query.
            
        Returns:
            dict: Response with relationship data and formatted response.
        """
        try:
            # Extract code if present
            code_match = re.search(r'\b([A-Z]\d{1,3}(?:\.\d+)?)\b', query.upper())
            target_code = code_match.group(1) if code_match else None
            
            # Determine the type of relationship query
            query_lower = query.lower()
            
            if target_code and any(word in query_lower for word in ["parent", "child", "hierarchy"]):
                return self._search_hierarchy(target_code, query)
            
            elif target_code and any(word in query_lower for word in ["snomed", "mapping", "maps to"]):
                return self._search_snomed_mapping(target_code, query)
            
            else:
                # General relationship search
                return self._search_general_relationships(query)
                
        except Exception as e:
            logger.exception("Relationship query processing failed")
            return {"error": f"Relationship search failed: {e}"}

    def _search_hierarchy(self, code: str, original_query: str) -> dict:
        """
        Search for parent-child hierarchy for a specific code.
        
        Args:
            code (str): The ICD code to find hierarchy for.
            original_query (str): The original user query.
            
        Returns:
            dict: Hierarchy data and formatted response.
        """
        try:
            from modules.config import get_config
            config = get_config()
            
            rel_search = modules.relationship_search.RelationshipSearch(
                index=self.index_name,
                query=code,
                top=config.search_top_k * 2  # Use 2x for hierarchy queries
            )
            
            hierarchy_data = rel_search.search_parent_child_hierarchy(code)
            
            if not hierarchy_data["parents"] and not hierarchy_data["children"]:
                return {
                    "data": json.dumps(hierarchy_data),
                    "processed_response": f"No parent-child relationships found for code {code}."
                }
            
            # Generate LLM response with hierarchy context
            response = self._generate_hierarchy_response(original_query, hierarchy_data)
            
            return {
                "data": json.dumps(hierarchy_data),
                "processed_response": response
            }
            
        except Exception as e:
            logger.exception("Hierarchy search failed")
            return {"error": f"Hierarchy search failed: {e}"}

    def _search_snomed_mapping(self, code: str, original_query: str) -> dict:
        """
        Search for SNOMED mappings for a specific ICD code.
        
        Args:
            code (str): The ICD code to find SNOMED mappings for.
            original_query (str): The original user query.
            
        Returns:
            dict: SNOMED mapping data and formatted response.
        """
        try:
            from modules.config import get_config
            config = get_config()
            
            rel_search = modules.relationship_search.RelationshipSearch(
                index=self.index_name,
                query=code,
                top=config.search_top_k
            )
            
            snomed_mappings = rel_search.search_snomed_mappings(code)
            
            if not snomed_mappings:
                return {
                    "data": json.dumps({"mappings": []}),
                    "processed_response": f"No SNOMED mappings found for ICD code {code}."
                }
            
            # Generate LLM response with mapping context
            response = self._generate_snomed_response(original_query, snomed_mappings)
            
            return {
                "data": json.dumps({"mappings": snomed_mappings}),
                "processed_response": response
            }
            
        except Exception as e:
            logger.exception("SNOMED mapping search failed")
            return {"error": f"SNOMED mapping search failed: {e}"}

    def _search_general_relationships(self, query: str) -> dict:
        """
        Search for general relationship information.
        
        Args:
            query (str): The relationship query.
            
        Returns:
            dict: Relationship data and formatted response.
        """
        try:
            from modules.config import get_config
            config = get_config()
            
            rel_search = modules.relationship_search.RelationshipSearch(
                index=self.index_name,
                query=query,
                top=int(config.search_top_k * 1.5)  # Use 1.5x for relationship queries
            )
            
            relationship_results = rel_search.search_relationships()
            
            if not relationship_results:
                return {
                    "data": json.dumps([]),
                    "processed_response": "No relationship data found for your query."
                }
            
            # Generate LLM response with relationship context
            response = self._generate_relationship_response(query, relationship_results)
            
            return {
                "data": json.dumps(relationship_results),
                "processed_response": response
            }
            
        except Exception as e:
            logger.exception("General relationship search failed")
            return {"error": f"General relationship search failed: {e}"}

    def _generate_hierarchy_response(self, query: str, hierarchy_data: Dict) -> str:
        """
        Generate LLM response for hierarchy queries.
        
        Args:
            query (str): Original user query.
            hierarchy_data (Dict): Hierarchy relationship data.
            
        Returns:
            str: Formatted LLM response.
        """
        context = f"Query Code: {hierarchy_data['query_code']}\n\n"
        
        if hierarchy_data["parents"]:
            context += "Parent Codes:\n"
            for parent in hierarchy_data["parents"]:
                context += f"- {parent['parent_code']}: {parent['parent_name']} [{parent['source']}]\n"
        
        if hierarchy_data["children"]:
            context += "\nChild Codes:\n"
            for child in hierarchy_data["children"]:
                context += f"- {child['child_code']}: {child['child_name']} [{child['source']}]\n"
        
        system_message = SystemMessage(content="""You are an expert medical coding assistant specializing in ICD code hierarchies and relationships. 
        Provide clear, accurate responses about code hierarchies based on the relationship data provided. 
        When referencing specific codes, use the document ID in square brackets like [I10] for citations.""")
        
        user_message = HumanMessage(content=f"""User Query: {query}

Hierarchy Data:
{context}

Please provide a comprehensive response about the code hierarchy and relationships. Include citations using document IDs in square brackets.""")
        
        response = self.llm.invoke([system_message, user_message])
        return response.content

    def _generate_snomed_response(self, query: str, snomed_mappings: List[Dict]) -> str:
        """
        Generate LLM response for SNOMED mapping queries.
        
        Args:
            query (str): Original user query.
            snomed_mappings (List[Dict]): SNOMED mapping data.
            
        Returns:
            str: Formatted LLM response.
        """
        context = "SNOMED Mappings:\n\n"
        
        for mapping in snomed_mappings:
            icd_code = mapping.get("icd_code", "")
            icd_name = mapping.get("icd_name", "")
            snomed_code = mapping.get("snomed_code", "")
            snomed_name = mapping.get("snomed_name", "")
            relationship = mapping.get("relationship_id", mapping.get("relationship_type", ""))
            
            context += f"ICD Code: {icd_code} - {icd_name}\n"
            context += f"SNOMED Code: {snomed_code} - {snomed_name}\n"
            context += f"Relationship: {relationship}\n\n"
        
        system_message = SystemMessage(content="""You are an expert medical coding assistant specializing in SNOMED and ICD code mappings. 
        Provide clear, accurate responses about code mappings and relationships based on the mapping data provided. 
        When referencing specific codes, use the document ID in square brackets like [I10] for citations.""")
        
        user_message = HumanMessage(content=f"""User Query: {query}

SNOMED Mapping Data:
{context}

Please provide a comprehensive response about the SNOMED mappings and relationships. Include citations using document IDs in square brackets.""")
        
        response = self.llm.invoke([system_message, user_message])
        return response.content

    def _generate_relationship_response(self, query: str, relationship_results: List[Dict]) -> str:
        """
        Generate LLM response for general relationship queries.
        
        Args:
            query (str): Original user query.
            relationship_results (List[Dict]): General relationship data.
            
        Returns:
            str: Formatted LLM response.
        """
        context = "Relationship Data:\n\n"
        
        for result in relationship_results:
            document = result.get("document", {})
            relationships = result.get("parsed_relationships", [])
            
            doc_code = document.get("CODE", "")
            doc_name = document.get("STR", "")
            
            context += f"Code: {doc_code} - {doc_name}\n"
            
            if relationships:
                context += "Relationships:\n"
                for rel in relationships:
                    rel_type = rel["REL"]
                    rel_code = rel["CODE"]
                    rel_name = rel["STR"]
                    rel_source = rel["SAB"]
                    
                    context += f"  {rel_type}: {rel_code} - {rel_name} [{rel_source}]\n"
            
            context += "\n"
        
        system_message = SystemMessage(content="""You are an expert medical coding assistant specializing in medical code relationships. 
        Provide clear, accurate responses about code relationships based on the relationship data provided. 
        When referencing specific codes, use the document ID in square brackets like [I10] for citations.""")
        
        user_message = HumanMessage(content=f"""User Query: {query}

Relationship Data:
{context}

Please provide a comprehensive response about the code relationships. Include citations using document IDs in square brackets.""")
        
        response = self.llm.invoke([system_message, user_message])
        return response.content

    def _get_heart_disease_concept_set(self) -> str:
        """
        Returns a predefined heart disease concept set.
        
        Returns:
            str: Heart disease concept set with citations.
        """
        # Simulate heart disease concept set documents
        concept_set_docs = [
            {"document": {"id": "I20", "title": "Angina pectoris", "content": "Chest pain due to reduced blood flow to the heart"}},
            {"document": {"id": "I21", "title": "Acute myocardial infarction", "content": "Heart attack"}},
            {"document": {"id": "I50", "title": "Heart failure", "content": "Inability of the heart to pump blood effectively"}},
        ]
        
        self.last_retrieved_documents = concept_set_docs
        
        response = """Heart Disease Concept Set:

[I20] - Angina pectoris: Chest pain due to reduced blood flow to the heart
[I21] - Acute myocardial infarction: Heart attack  
[I50] - Heart failure: Inability of the heart to pump blood effectively

This concept set covers the primary ICD-10 codes for heart disease conditions as defined in PCORnet Documentation."""
        
        return response
    
    def process_interactive(self, query: str, session_id: str) -> Dict[str, Any]:
        """
        Process queries with interactive session support for dynamic data manipulation.
        
        Args:
            query: User's query
            session_id: Interactive session identifier
            
        Returns:
            Dictionary with response and session context
        """
        # Check if this is a modification request
        if interactive_session.is_modification_request(query):
            return self._handle_modification_request(query, session_id)
        
        # Process as normal query but store results in session
        result = self.process(query)
        
        # Extract and store data items in session
        self._extract_and_store_data(result, query, session_id)
        
        # Add session summary to response
        if "processed_response" in result:
            session_summary = interactive_session.get_current_data_summary(session_id)
            if session_summary and "No data currently loaded" not in session_summary:
                result["processed_response"] += f"\n\n---\n{session_summary}"
                result["processed_response"] += "\n\n💡 *You can ask me to add, remove, or modify this information. Try 'add SNOMED codes' or 'show as table'.*"
        
        return result
    
    def _handle_modification_request(self, query: str, session_id: str) -> Dict[str, Any]:
        """
        Handle requests to modify the current session data.
        
        Args:
            query: Modification request
            session_id: Session identifier
            
        Returns:
            Dictionary with modified data and response
        """
        modification_type = interactive_session.detect_modification_type(query)
        data_types = interactive_session.extract_data_types(query)
        
        # Check if session exists by ID, not by current_session_id
        current_context = interactive_session.get_context(session_id)
        if not current_context:
            # Start new session if none exists
            interactive_session.start_session(session_id)
            current_context = interactive_session.get_context(session_id)
        
        response = ""
        
        if modification_type == "add":
            add_result = self._handle_add_request(query, session_id, data_types)
            
            # Check if this returned structured data (search results + response)
            if isinstance(add_result, dict) and 'search_results' in add_result:
                return {
                    "data": add_result['search_results'],
                    "processed_response": add_result['text_response'],
                    "session_context": interactive_session.get_session_stats(session_id)
                }
            else:
                # Regular string response
                return {
                    "data": "[]",
                    "processed_response": add_result,
                    "session_context": interactive_session.get_session_stats(session_id)
                }
        elif modification_type == "remove":
            response = self._handle_remove_request(query, session_id, data_types)
        elif modification_type == "format":
            response = self._handle_format_request(query, session_id)
        elif modification_type == "filter":
            response = self._handle_filter_request(query, session_id, data_types)
        else:
            response = self._handle_general_modification(query, session_id)
        
        return {
            "data": "[]",  # No new search data
            "processed_response": response,
            "session_context": interactive_session.get_session_stats(session_id)
        }
    
    def _search_and_add_snomed(self, condition: str, session_id: str, original_query: str):
        """Helper method to search for ICD codes and then add SNOMED mappings."""
        try:
            # First search for ICD codes for the condition
            search_result = self.process(condition)
            
            if not search_result or search_result.get('error'):
                return f"I couldn't find any ICD codes for '{condition}'. Could you try a different condition or be more specific?"
            
            # Parse the JSON data from search results
            raw_data = search_result.get('data', '[]')
            if raw_data == '[]':
                return f"No ICD codes found for '{condition}'. Could you try a different condition or be more specific?"
            
            try:
                results_list = json.loads(raw_data)
            except (json.JSONDecodeError, TypeError):
                return f"Error processing search results for '{condition}'."
            
            if not results_list:
                return f"No ICD codes found for '{condition}'. Could you try a different condition or be more specific?"
            
            # Add the search results to session with full document (includes OHDSI field)
            if session_id:
                # Check if session exists, if not start one
                if session_id not in interactive_session.contexts:
                    interactive_session.start_session(session_id)
                    
                current_session = interactive_session.contexts.get(session_id)
                if current_session:
                    for result in results_list:
                        doc = result.get('document', {})
                        
                        # Clean OHDSI field to remove br tags before storing
                        if 'OHDSI' in doc and doc['OHDSI']:
                            doc['OHDSI'] = self._clean_html_tags(doc['OHDSI'])
                        
                        # Store full document so OHDSI field is available
                        data_item = DataItem(
                            item_type='icd_code',
                            key=doc.get('CODE', ''),
                            value=doc.get('STR', ''),
                            metadata={'full_document': doc},  # Store complete document
                            source_query=condition
                        )
                        interactive_session.add_data_item(session_id, data_item)
            
            # SNOMED mappings are now in OHDSI field - no need for separate search
            # The chat agent can extract SNOMED codes from the stored OHDSI data
            logger.info(f"📋 Stored {len(results_list)} ICD codes with OHDSI data in session")
            
            # Return simple response - SNOMED data is in session for chat agent to use
            formatted_results = []
            formatted_results.append(f"**Found {len(results_list)} ICD codes for '{condition}':**\n")
            
            for result in results_list:
                doc = result.get('document', {})
                code = doc.get('CODE', '')
                desc = doc.get('STR', '')
                formatted_results.append(f"**{code}**: {desc}")
            
            formatted_results.append("\n💡 *The data includes OHDSI mappings (with SNOMED codes). Try asking me to 'show SNOMED codes' or 'format as table with SNOMED'.*")
            
            return "\n".join(formatted_results)
                
        except Exception as e:
            return f"I encountered an error while searching for '{condition}' and SNOMED mappings: {str(e)}"

    def _handle_add_request(self, query: str, session_id: str, data_types: List[str]) -> str:
        """Handle requests to add specific types of data."""
        
        # Check if user wants to add SNOMED codes to existing ICD codes
        if "snomed_code" in data_types:
            current_icds = interactive_session.get_data_by_type(session_id, "icd_code")
            if current_icds:
                response_lines = ["**Adding SNOMED data from SNOMED Agent (Source of Truth):**\n"]
                
                # Import SNOMED agent
                from modules.agents.snomed_agent import SnomedAgent
                snomed_agent = SnomedAgent()
                
                for icd_item in current_icds:
                    icd_code = icd_item.key
                    icd_desc = icd_item.value
                    
                    try:
                        # First get SNOMED codes from OHDSI mappings (for reference)
                        rel_search = modules.relationship_search.RelationshipSearch(
                            index=self.index_name,
                            query=icd_code
                        )
                        snomed_mappings = rel_search.search_snomed_mappings(icd_code)
                        
                        if snomed_mappings:
                            response_lines.append(f"**{icd_code} - {icd_desc}:**")
                            
                            # For each SNOMED code found in mapping, get authoritative data from SNOMED agent
                            for mapping in snomed_mappings[:3]:  # Limit to first 3
                                snomed_code = mapping.get("snomed_code", "")
                                
                                if snomed_code:
                                    # Call SNOMED agent to get SOURCE OF TRUTH data
                                    snomed_result = snomed_agent.get_concept_details(snomed_code)
                                    
                                    if "error" not in snomed_result:
                                        # Use SNOMED agent data as source of truth
                                        snomed_name = snomed_result.get("concept_name", mapping.get("snomed_name", ""))
                                        snomed_source = snomed_result.get("source", "SNOMED CT")
                                        
                                        # Clean HTML tags from SNOMED name
                                        snomed_name = self._clean_html_tags(snomed_name)
                                        
                                        # Store SNOMED agent data in session
                                        snomed_item = DataItem(
                                            item_type="snomed_code",
                                            key=snomed_code,
                                            value=snomed_name,
                                            metadata={
                                                "source": "SNOMED_AGENT",  # Mark as from SNOMED agent
                                                "linked_icd": icd_code,
                                                "ohdsi_relationship": mapping.get("relationship_id", ""),
                                                "snomed_source": snomed_source,
                                                "full_document": snomed_result.get("full_document", {})
                                            },
                                            source_query=query
                                        )
                                        interactive_session.add_data_item(session_id, snomed_item)
                                        
                                        response_lines.append(f"  ✓ SNOMED {snomed_code}: {snomed_name}")
                                        response_lines.append(f"    _Source: {snomed_source} (via SNOMED Agent)_")
                                    else:
                                        # Fallback to OHDSI mapping if SNOMED agent lookup fails
                                        snomed_name = mapping.get("snomed_name", "")
                                        # Clean HTML tags from SNOMED name
                                        snomed_name = self._clean_html_tags(snomed_name)
                                        
                                        snomed_item = DataItem(
                                            item_type="snomed_code",
                                            key=snomed_code,
                                            value=snomed_name,
                                            metadata={
                                                "source": "OHDSI_MAPPING",  # Mark as from mapping only
                                                "linked_icd": icd_code,
                                                "relationship": mapping.get("relationship_id", "")
                                            },
                                            source_query=query
                                        )
                                        interactive_session.add_data_item(session_id, snomed_item)
                                        response_lines.append(f"  • SNOMED {snomed_code}: {snomed_name}")
                                        response_lines.append(f"    _Note: From OHDSI mapping (SNOMED agent lookup unavailable)_")
                                    
                            response_lines.append("")  # Empty line between codes
                        else:
                            response_lines.append(f"**{icd_code}:** No SNOMED mappings found")
                            
                    except Exception as e:
                        logger.error(f"Error finding SNOMED for {icd_code}: {e}")
                        response_lines.append(f"**{icd_code}:** Error retrieving SNOMED data")
                
                response_lines.append("\n💡 _SNOMED data retrieved from SNOMED Agent (authoritative source)_")
                return "\n".join(response_lines)
            else:
                # No existing ICD codes - check if query contains medical condition
                query_lower = query.lower()
                
                # Look for medical conditions in the query
                medical_terms = []
                common_conditions = [
                    'diabetes', 'hypertension', 'heart failure', 'myocardial infarction',
                    'copd', 'asthma', 'cancer', 'stroke', 'pneumonia', 'sepsis',
                    'kidney disease', 'liver disease', 'depression', 'anxiety'
                ]
                
                for condition in common_conditions:
                    if condition in query_lower:
                        medical_terms.append(condition)
                
                if medical_terms:
                    # Found medical terms - search for ICD codes first, then add SNOMED
                    search_result = self._search_and_add_snomed(medical_terms[0], session_id, query)
                    # Return the structured data so it can be processed in _handle_modification_request
                    return search_result
                else:
                    # No medical terms found - provide helpful suggestions
                    return """I'd be happy to help you find SNOMED codes! Here are a few options:

**Option 1: Tell me the medical condition**
- "Add SNOMED codes for diabetes"
- "Find SNOMED mappings for heart failure"
- "Show SNOMED codes for hypertension"

**Option 2: Search for ICD codes first**
- "Find diabetes ICD codes" (then I can add SNOMED mappings)

**Option 3: Give me specific ICD codes**
- "Add SNOMED codes for I10 and E11"

What condition would you like SNOMED codes for?"""
        
        # Handle other add requests with better guidance
        if data_types:
            return f"""I can help you add {', '.join(data_types)} information. Here are some examples:

• **For specific conditions**: "Add SNOMED codes for diabetes"
• **For ICD codes**: "Add descriptions for I10 and I21"  
• **For relationships**: "Add parent codes for current results"

What specific information would you like me to add?"""
        else:
            return "I can help you add various types of medical coding information. Please let me know what you'd like to add (e.g., 'SNOMED codes for diabetes' or 'descriptions for I10')."
    
    def _handle_remove_request(self, query: str, session_id: str, data_types: List[str]) -> str:
        """Handle requests to remove specific data."""
        
        removed_count = 0
        removed_items = []
        
        current_context = interactive_session.get_current_context()
        if not current_context or not current_context.current_data:
            return "No data in current session to remove."
        
        # Extract specific codes to remove from query
        import re
        
        # Look for specific ICD codes (like I10, E11.9)
        icd_pattern = r'\b[A-Z]\d{1,3}(?:\.\d+)?\b'
        icd_codes = re.findall(icd_pattern, query.upper())
        
        # Look for SNOMED codes (numeric)
        snomed_pattern = r'\b\d{6,10}\b'
        snomed_codes = re.findall(snomed_pattern, query)
        
        # Remove specific codes if found
        for code in icd_codes + snomed_codes:
            if interactive_session.remove_data_item(session_id, code):
                removed_count += 1
                removed_items.append(code)
        
        # Remove by data type if specified
        if not removed_items and data_types:
            for item in list(current_context.current_data.values()):
                if item.item_type in data_types:
                    interactive_session.remove_data_item(session_id, item.key)
                    removed_count += 1
                    removed_items.append(f"{item.key} ({item.item_type})")
        
        if removed_count > 0:
            response = f"✅ Removed {removed_count} item(s): {', '.join(removed_items)}\n\n"
            response += interactive_session.get_current_data_summary(session_id)
            return response
        else:
            return "No items were removed. Please specify codes or data types to remove."
    
    def _handle_format_request(self, query: str, session_id: str) -> str:
        """Handle requests to format data differently."""
        
        query_lower = query.lower()
        
        if "json" in query_lower:
            return f"**Data as JSON:**\n```json\n{interactive_session.format_data_as_json(session_id)}\n```"
        elif "table" in query_lower:
            return f"**Data as Table:**\n\n{interactive_session.format_data_as_table(session_id)}"
        else:
            # Default to summary format
            return interactive_session.get_current_data_summary(session_id)
    
    def _clean_html_tags(self, text: str) -> str:
        """
        Remove HTML tags from text.
        Replaces br tags with commas, removes other HTML tags.
        """
        import re
        
        if not text:
            return text
        
        # Replace br tags with comma-space
        text = re.sub(r'<br\s*/?>', ', ', text, flags=re.IGNORECASE)
        
        # Remove any other HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Clean up multiple commas
        text = re.sub(r',\s*,', ',', text)
        
        # Clean up spaces
        text = re.sub(r' +', ' ', text)
        
        return text.strip()
    
    def _handle_filter_request(self, query: str, session_id: str, data_types: List[str]) -> str:
        """Handle requests to filter current data."""
        
        if not data_types:
            return "Please specify what type of data to filter (e.g., 'only show ICD codes' or 'just SNOMED codes')."
        
        filtered_response = ["**Filtered Data:**\n"]
        
        for data_type in data_types:
            items = interactive_session.get_data_by_type(session_id, data_type)
            if items:
                filtered_response.append(f"**{data_type.replace('_', ' ').title()}s:**")
                for item in items:
                    filtered_response.append(f"- {item.key}: {item.value}")
                filtered_response.append("")
            else:
                filtered_response.append(f"No {data_type.replace('_', ' ')}s found in session.")
        
        return "\n".join(filtered_response)
    
    def _handle_general_modification(self, query: str, session_id: str) -> str:
        """Handle general modification requests."""
        
        current_summary = interactive_session.get_current_data_summary(session_id)
        
        help_text = """
**Available Interactive Commands:**

📝 **Add Information:**
- "Add SNOMED codes" - Add SNOMED mappings for current ICD codes
- "Include descriptions" - Add detailed descriptions
- "Also show parent codes" - Add hierarchical relationships

🗑️ **Remove Information:**  
- "Remove I10" - Remove specific code
- "Remove SNOMED codes" - Remove all SNOMED data
- "Without descriptions" - Remove description fields

📊 **Format Data:**
- "Show as table" - Display as markdown table
- "Format as JSON" - Export as JSON
- "Show as list" - Simple list format

🔍 **Filter Data:**
- "Only show ICD codes" - Filter to ICD codes only
- "Just SNOMED codes" - Show SNOMED codes only

Try any of these commands to modify your current data!
"""
        
        return current_summary + "\n" + help_text
    
    def _extract_and_store_data(self, result: Dict[str, Any], query: str, session_id: str):
        """
        Extract data items from search results and store in interactive session.
        
        Args:
            result: Search result dictionary
            query: Original query
            session_id: Session identifier
        """
        if "data" not in result:
            return
        
        try:
            # Ensure session exists by checking with session_id
            if not interactive_session.get_context(session_id):
                interactive_session.start_session(session_id)
            
            raw_data = json.loads(result["data"])
            
            for item in raw_data:
                document = item.get("document", {})
                code = document.get("CODE", "")
                description = document.get("STR", "")
                
                if code and description:
                    # Clean OHDSI field to remove br tags before storing
                    if 'OHDSI' in document and document['OHDSI']:
                        document['OHDSI'] = self._clean_html_tags(document['OHDSI'])
                    
                    # Store ALL fields from the document in metadata
                    # This includes OHDSI, SAB, and any other available fields
                    metadata = {
                        "score": item.get("score", 0),
                        "document_id": document.get("id", code),
                        "full_document": document  # Store complete document for access to all fields
                    }
                    
                    # Log what fields are available
                    logger.debug(f"📋 Storing document with fields: {list(document.keys())}")
                    
                    # Add ICD code to session with full document
                    data_item = DataItem(
                        item_type="icd_code",
                        key=code,
                        value=description,
                        metadata=metadata,
                        source_query=query
                    )
                    interactive_session.add_data_item(session_id, data_item)
                    
        except Exception as e:
            logger.error(f"Error extracting data for session: {e}")