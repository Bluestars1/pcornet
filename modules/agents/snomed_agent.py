"""
A specialized agent for querying the PCORnet SNOMED CT index in Azure AI Search.

This module defines the SnomedAgent, which is responsible for searching an Azure
AI Search index containing SNOMED CT US Edition clinical terminology. It uses an
LLM to process search results and generate responses with proper citations.
"""

import os
import json
import logging
import re
from typing import Dict, List, Any
import modules.search_tool
from modules.interactive_session import interactive_session, DataItem
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


class SnomedAgent:
    """
    An agent that queries an Azure AI Search index for SNOMED CT terminology.

    This agent uses the `Search` helper to connect to the SNOMED CT US Edition
    index and performs semantic searches for clinical concepts. It processes
    the results using an LLM and generates responses with proper citations.
    """

    def __init__(self, index="snomed"):
        """
        Initializes the SnomedAgent.
        
        Args:
            index (str): The index registry key or direct index name to query.
                Default is "snomed" which uses the index registry.
        """
        self.index_name = index
        self.last_retrieved_documents = []
        
        logger.info("✅ SnomedAgent initialized")
        
        # Initialize LLM client
        try:
            self.llm = self._create_llm()
            logger.info("✅ SnomedAgent initialized with LLM")
        except Exception as e:
            logger.error(f"Failed to initialize SnomedAgent LLM: {e}")
            raise e

    def _create_llm(self):
        """Creates and returns an LLM client for processing search results."""
        from modules.config import create_chat_llm
        
        return create_chat_llm()  # Uses configured AGENT_MAX_TOKENS

    def process(self, query: str) -> dict:
        """
        Performs a hybrid search in the SNOMED index and processes results with LLM.

        This method searches for SNOMED concepts, processes the results with an LLM to
        generate a comprehensive response, and includes proper citations referencing
        the document IDs where information was found.

        Args:
            query (str): The search query from the user.

        Returns:
            dict: A dictionary with 'data' key containing JSON string of raw results
                  and 'processed_response' key containing the LLM response with citations,
                  or 'error' key if search fails.
        """
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
                return {"data": "[]", "processed_response": "No SNOMED concepts found for your query."}

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
            logger.exception("SNOMED search failed")
            return {"error": f"Search operation failed: {e}"}
        except Exception as e:
            logger.exception("SNOMED processing failed")
            return {"error": f"An error occurred: {e}"}

    def process_interactive(self, query: str, session_id: str) -> dict:
        """
        Process query and store results in interactive session.
        
        Args:
            query: Search query
            session_id: Session identifier for storing results
            
        Returns:
            dict: Processed response with session context
        """
        try:
            # Perform search
            result = self.process(query)
            
            if "error" in result:
                return result
            
            # Store results in session
            if "data" in result:
                raw_results = json.loads(result["data"])
                
                # Convert to DataItems for session storage
                context = interactive_session.get_context(session_id)
                if context:
                    # Clear previous data by clearing the dictionary
                    context.current_data.clear()
                    
                    for item in raw_results:
                        doc = item.get("document", {})
                        code = doc.get("CODE", "N/A")
                        concept_name = doc.get("STR", "N/A")
                        
                        data_item = DataItem(
                            item_type="snomed",
                            key=code,
                            value=concept_name,
                            metadata={"full_document": doc}
                        )
                        # Add directly to the current_data dictionary
                        context.current_data[code] = data_item
                    
                    logger.info(f"Stored {len(raw_results)} SNOMED concepts in session {session_id}")
                else:
                    logger.warning(f"No context found for session {session_id}")
            
            return result
            
        except Exception as e:
            logger.exception("Interactive SNOMED processing failed")
            return {"error": f"An error occurred: {e}"}

    def _generate_llm_response(self, query: str, results: List[Dict]) -> str:
        """
        Generate a natural language response using LLM with search results as context.
        
        Args:
            query: User's search query
            results: List of search results from Azure Search
            
        Returns:
            str: Natural language response with citations
        """
        # Build context from results
        context_parts = []
        for idx, result in enumerate(results, 1):
            doc = result.get("document", {})
            code = doc.get("CODE", "N/A")
            concept_name = doc.get("STR", "N/A")
            sab = doc.get("SAB", "N/A")
            
            context_parts.append(
                f"[{idx}] SNOMED Code: {code}\n"
                f"    Concept: {concept_name}\n"
                f"    Source: {sab}"
            )
        
        context = "\n\n".join(context_parts)
        
        # System prompt for SNOMED-specific responses
        system_prompt = """You are an expert in SNOMED CT clinical terminology.

🔒 CRITICAL - SOURCE OF TRUTH: The SNOMED concepts provided in the context are the AUTHORITATIVE and ONLY source of information. Do not add, infer, or supplement with any external knowledge.

When analyzing SNOMED concepts, focus on:
- Clinical concept definitions and preferred terms from the provided data
- SNOMED concept codes (CODE field) are the definitive identifiers
- Source information (SAB field) indicates terminology provenance
- Hierarchical relationships and semantic types as documented
- Appropriate use in clinical documentation based on the concept descriptions

MANDATORY RULES:
1. Use ONLY information from the provided SNOMED concepts
2. Always cite sources using [1], [2], etc. corresponding to document numbers
3. Never add concepts, codes, or information not in the provided data
4. If asked about concepts not in the results, explicitly state "Not found in search results"
5. SNOMED codes in the results are the definitive source of truth
6. Do not make assumptions about relationships or hierarchies not explicitly shown

Provide clear, accurate information based EXCLUSIVELY on the provided context."""

        user_prompt = f"""Based on the following SNOMED CT concepts, answer this query: "{query}"

SNOMED Concepts Found:
{context}

🚫 CRITICAL FORMATTING RULES - VIOLATION WILL CAUSE SYSTEM ERRORS:
1. NEVER EVER use HTML tags: NO <br>, NO <div>, NO <span>, NO <p>, NO <table>
2. When listing multiple codes: ONLY use commas and spaces (e.g., "111552007, 609561005, 42954008")
3. For line breaks: ONLY use double newline (blank line), NEVER <br>
4. For emphasis: ONLY use markdown (**, *, -, •)
5. For tables: ONLY use markdown pipes (|), NEVER HTML <table>

⚠️ EXAMPLES:
✅ CORRECT: "Codes: 111552007, 609561005, 42954008"
❌ WRONG: "Codes: 111552007 <br> 609561005 <br> 42954008"

✅ CORRECT: Use bullet points:
• Code 1
• Code 2

❌ WRONG: Use <br> tags

📊 TABLE RULES: When asked to add/remove columns or "show as table", REBUILD the entire table with markdown syntax (| Header |).
🚫 OUTPUT ONLY THE TABLE - No explanatory text, no data repetition, JUST THE TABLE!

Provide a comprehensive answer with citations [1], [2], etc."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.llm.invoke(messages)
            
            # Post-process to remove any HTML tags (safety net)
            cleaned_response = self._remove_html_tags(response.content)
            return cleaned_response
            
        except Exception as e:
            logger.error(f"LLM response generation failed: {e}")
            return f"Error generating response: {e}"
    
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

    def _normalize_citations(self, response: str, results: List[Dict]) -> str:
        """
        Normalize citations in the response to use document CODEs instead of numbers.
        
        Args:
            response: LLM response with [1], [2] style citations
            results: Search results to map citations to
            
        Returns:
            str: Response with normalized citations
        """
        # Create mapping of citation numbers to document codes
        citation_map = {}
        for idx, result in enumerate(results, 1):
            doc = result.get("document", {})
            code = doc.get("CODE", f"doc{idx}")
            citation_map[str(idx)] = code
        
        # Replace [1], [2], etc. with [CODE]
        def replace_citation(match):
            num = match.group(1)
            return f"[{citation_map.get(num, num)}]"
        
        # Match [1], [2], etc. but not [CODE] style citations
        normalized = re.sub(r'\[(\d+)\]', replace_citation, response)
        
        return normalized


    def get_concept_details(self, concept_code: str) -> Dict:
        """
        Get detailed information about a specific SNOMED concept.
        
        Args:
            concept_code: SNOMED concept code
            
        Returns:
            dict: Concept details or error
        """
        try:
            from modules.config import get_config
            config = get_config()
            
            search = modules.search_tool.Search(
                index=self.index_name,
                query=concept_code,
                top=max(5, config.search_top_k // 2)  # At least 5, or half of configured top_k
            )
            results = search.run()
            
            if not results:
                return {"error": f"No details found for SNOMED concept {concept_code}"}
            
            # Find exact match
            for result in results:
                doc = result.get("document", {})
                if doc.get("CODE") == concept_code:
                    return {
                        "code": doc.get("CODE"),
                        "concept_name": doc.get("STR"),
                        "source": doc.get("SAB"),
                        "full_document": doc
                    }
            
            # If no exact match, return first result
            doc = results[0].get("document", {})
            return {
                "code": doc.get("CODE"),
                "concept_name": doc.get("STR"),
                "source": doc.get("SAB"),
                "full_document": doc,
                "note": "Closest match (not exact)"
            }
            
        except Exception as e:
            logger.exception(f"Failed to get concept details for {concept_code}")
            return {"error": f"Failed to get concept details: {e}"}
