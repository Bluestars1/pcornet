"""
A specialized agent for extracting and formatting data from a context string.

This module defines the ConceptSetExtractorAgent, which is designed to take a
raw string of data (typically a JSON-like representation of search results),
extract the relevant fields, and format them into a clean, human-readable
string for presentation or further processing by another agent.
"""
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class ConceptSetExtractorAgent:
    """
    An agent responsible for processing context data to extract concept sets.
    """

    def __init__(self):
        """
        Initializes the ConceptSetExtractorAgent.
        """
        logger.info("[ConceptSetExtractorAgent] ✅ Initialized")

    def process(self, context_data: str) -> str:
        """
        Processes a raw context string, extracts ICD data with ALL fields, and formats it.

        Args:
            context_data (str): A string containing the raw data, expected to be
                                a JSON representation of a list of dictionaries.

        Returns:
            str: A formatted string containing the extracted concept set with all available
                 fields (CODE, STR, OHDSI, SAB, etc.), or an error message if processing fails.
        """
        try:
            # The context data is a string representation of a list of dicts
            data: List[Dict[str, Any]] = json.loads(context_data)

            if not data:
                return "No concepts found in the provided data."  # Match test expectation

            formatted_lines = ["Here are the extracted ICD concepts for the concept set:"]
            for item in data:
                document = item.get("document", {})
                code = document.get("CODE", "N/A")
                label = document.get("STR", "N/A")
                score = item.get("score", 0.0)
                
                # Log available fields for debugging
                available_fields = list(document.keys())
                logger.debug(f"[ConceptSetExtractorAgent] 📋 Extracting {code}: fields available = {available_fields}")
                
                # Build line with code, label, and score
                line = f"Code: {code}, Label: {label}, Score: {score:.4f}"
                
                # Add ALL additional fields from document (OHDSI, SAB, etc.)
                additional_fields = []
                for field, value in document.items():
                    if field not in ["CODE", "STR", "id"] and value:
                        # Format field name nicely
                        additional_fields.append(f"{field}: {value}")
                        logger.debug(f"[ConceptSetExtractorAgent] 📋 Added field {field} for {code}")
                
                if additional_fields:
                    line += ", " + ", ".join(additional_fields)
                    logger.info(f"[ConceptSetExtractorAgent] 📋 Extracted {code} with {len(additional_fields)} additional fields (including OHDSI if present)")
                
                formatted_lines.append(line)

            return "\n".join(formatted_lines)

        except json.JSONDecodeError:
            logger.warning("[ConceptSetExtractorAgent] Failed to decode JSON from context")
            return {"error": "Failed to decode JSON"}  # Return dict for test compatibility
        except Exception as e:
            logger.exception("[ConceptSetExtractorAgent] An unexpected error occurred")
            return f"An error occurred while extracting the concept set: {e}"
