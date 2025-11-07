"""
A specialized agent for handling general conversational chat.

This module defines the ChatAgent, which uses the AzureChatOpenAI model from
the LangChain library to engage in conversations. It is responsible for
processing user input and generating helpful, context-aware responses for
non-specialized queries.
"""

# modules/agents/chat_agent.py
import os
import logging
from langchain_core.messages import HumanMessage, SystemMessage
from ..config import get_config, create_chat_llm, CONCEPT_SET_FORMATTING_PROMPT

logger = logging.getLogger(__name__)

class ChatAgent:
    """
    A conversational agent powered by Azure OpenAI's GPT models.

    This agent is designed for general-purpose chat. It initializes a connection
    to an Azure OpenAI deployment and uses it to respond to user messages.
    """

    def __init__(self):
        """
        Initializes the ChatAgent and its underlying language model.

        This constructor configures and instantiates the AzureChatOpenAI model
        using centralized configuration. It sets a default temperature and 
        token limit for the responses.

        Raises:
            Exception: If the language model fails to initialize, often due to
                       missing or incorrect environment variables.
        """
        try:
            self.llm = create_chat_llm()  # Uses configured AGENT_MAX_TOKENS
            logger.info("✅ ChatAgent LLM initialized successfully")
        except Exception as e:
            logger.exception("Failed to initialize ChatAgent LLM")
            raise e

    def process(self, user_input: str, context: str = None) -> str:
        """
        Processes a user's chat message and returns the model's response.

        This method constructs a message list with a system prompt and the user's
        input, then invokes the language model to get a conversational response.

        Args:
            user_input (str): The message from the user.
            context (str): Optional RAG context from previous searches to include.

        Returns:
            str: The AI-generated response as a string. Returns an error message
                 if the model invocation fails.
        """
        try:
            # Build system message with RAG context if provided
            if context:
                # Count how many codes we have
                code_count = context.count('[') if context else 0
                system_content = f"""You are a helpful AI assistant specializing in medical coding and ICD-10 codes.

🔒 CRITICAL INSTRUCTION: You have access to {code_count} ICD-10 codes from a previous search below. This is your COMPLETE dataset. You MUST use ONLY this data. DO NOT ask the user for more information - you already have ALL the data you need.

⚠️ CRITICAL - SNOMED DATA SOURCE PRIORITY:
1. If data has "source": "SNOMED_AGENT" in metadata → USE THIS (Authoritative source of truth)
2. If data has "source": "OHDSI_MAPPING" → Only use as fallback
3. OHDSI field mappings are for CORRELATION ONLY, not source of truth

AVAILABLE ICD-10 CODES WITH ALL FIELDS ({code_count} codes):
{context}

UNDERSTANDING THE DATA:
- Each code entry includes [CODE] Description  
- Items with metadata "source": "SNOMED_AGENT" contain AUTHORITATIVE SNOMED data from the SNOMED Agent
- Items with metadata "source": "OHDSI_MAPPING" are secondary correlation data only
- OHDSI field contains mappings to other vocabularies (for correlation/mapping reference)
  - When OHDSI is present, it contains a "maps" array
  - Each map has: vocabulary_id, concept_code, concept_name, relationship_id, domain_id
  - These are MAPPINGS ONLY - not the source of truth for SNOMED data
- SAB field indicates the source abbreviation
- All other fields are additional metadata

MANDATORY RULES:
1. NEVER ask the user to provide data - you already have ALL the data above
2. For ANY SNOMED request: 
   a. FIRST check for items with "source": "SNOMED_AGENT" - these are the authoritative SNOMED concepts
   b. ONLY use OHDSI mappings if no SNOMED_AGENT data is available
3. When displaying SNOMED data in tables:
   - USE data from SNOMED_AGENT items (marked with source=SNOMED_AGENT)
   - Label clearly if using OHDSI mappings vs SNOMED Agent data
4. Format the data as requested (table, JSON, list, etc.)
5. Do not add any additional codes or information not in the list above
6. If asked about codes not in the list, state they are not in the current dataset
7. When asked to create a table, use the data above immediately - do not ask for clarification
8. SNOMED Agent data is the SOURCE OF TRUTH - always prioritize it over OHDSI mappings

📊 TABLE MODIFICATION RULES:
9. When user says "add X to table" or "include X in table":
   - REBUILD the ENTIRE table with the new column/data
   - Use markdown table syntax: | Header 1 | Header 2 | Header 3 |
   - Include proper header separator: |----------|----------|----------|
   - Add all rows with the new data extracted from OHDSI or other fields
   
10. When user says "remove X from table" or "without X":
    - REBUILD the ENTIRE table excluding that column
    - Keep all other columns intact
    
11. When user says "show as table" or "format as table":
    - CREATE a complete markdown table with ALL available data
    - Extract SNOMED codes from OHDSI field if present
    - Use clear column headers (ICD Code, Description, SNOMED Codes, etc.)

⚠️ TABLE EXAMPLE:
User: "Show ICD codes with SNOMED codes as a table"
YOU MUST CREATE:
| ICD Code | Description | SNOMED Codes |
|----------|-------------|--------------|
| I10 | Essential hypertension | 111552007, 609561005 |
| E11.9 | Type 2 diabetes | 73211009, 44054006 |

🚫 CRITICAL TABLE OUTPUT RULES:
- When creating/modifying a table: OUTPUT ONLY THE TABLE
- Do NOT add explanatory paragraphs after the table
- Do NOT repeat the data in text form
- Do NOT concatenate all data into one long paragraph
- JUST THE TABLE, nothing else!

🚫 CRITICAL FORMATTING RULES - VIOLATION WILL CAUSE SYSTEM ERRORS:
1. NEVER EVER use HTML tags: NO <br>, NO <div>, NO <span>, NO <p>, NO <table>
2. When listing multiple codes: ONLY use commas and spaces (e.g., "I10, E11.9, I50.9")
3. For line breaks: ONLY use double newline (blank line), NEVER <br>
4. For emphasis: ONLY use markdown (**, *, -, •)
5. For tables: ONLY use markdown pipes (|), NEVER HTML <table>

⚠️ EXAMPLES:
✅ CORRECT: "Codes: I10, E11.9, I50.9" or use bullet points
❌ WRONG: "Codes: I10 <br> E11.9 <br> I50.9"

✅ CORRECT when listing codes:
• I10: Essential hypertension
• E11.9: Type 2 diabetes
OR: "I10, E11.9, I50.9"

❌ WRONG: NEVER use <br> tags between codes"""
            else:
                system_content = "You are a helpful AI assistant."
            
            messages = [
                SystemMessage(content=system_content),
                HumanMessage(content=user_input)
            ]
            response = self.llm.invoke(messages)
            
            # Post-process to remove any HTML tags (safety net)
            cleaned_response = self._remove_html_tags(response.content)
            return cleaned_response
        except Exception as e:
            logger.error(f"Error in ChatAgent: {e}")
            return f"⚠️ Error: {e}"
    
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

    def format_concept_set(self, original_query: str, context_data: str) -> str:
        """
        Uses the LLM to format the extracted concept set data.

        Args:
            original_query (str): The user's original query.
            context_data (str): The extracted data from the ConceptSetExtractorAgent.

        Returns:
            str: A formatted, conversational response for the user.
        """
        try:
            prompt = CONCEPT_SET_FORMATTING_PROMPT.format(
                query=original_query,
                context_data=context_data
            )
            messages = [HumanMessage(content=prompt)]
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"[ChatAgent] Error formatting concept set: {e}")
            return f"⚠️ Error formatting the concept set: {e}"
