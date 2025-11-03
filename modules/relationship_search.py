"""
REL Segment Search Tool for SNOMED and ICD Relationships

This module provides specialized search functionality for the REL segment data,
which contains SNOMED code relationships including parent-child and "is a" 
relationships. It extends the base Search functionality to focus on 
relationship data extraction and formatting.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from .search_tool import Search, SearchError
from .config import get_config

logger = logging.getLogger(__name__)

class RelationshipSearch(Search):
    """
    Specialized search for REL segment data containing SNOMED relationships.
    
    This class extends the base Search functionality to focus on relationship
    data, providing methods to search for parent-child relationships, 
    SNOMED mappings, and hierarchical code structures.
    """

    def __init__(
        self,
        index: str,
        query: str,
        *,
        top: int = 20,
        embedding: Optional[List[float]] = None,
        semantic_config: Optional[str] = None,
        rel_types: Optional[List[str]] = None,
        search_fields: Optional[List[str]] = None,
        vector_field: Optional[str] = None,
    ) -> None:
        """
        Initializes the RelationshipSearch with REL-specific parameters.
        
        Args:
            index (str): The name of the target search index.
            query (str): The search query string.
            top (int): The maximum number of results to retrieve. Defaults to 20.
            embedding (List[float], optional): Pre-computed embedding vector.
            semantic_config (str, optional): Semantic configuration name.
            rel_types (List[str], optional): Filter by specific relationship types
                (PAR, CHD, RO, SY, etc.). If None, all types are included.
            search_fields (List[str], optional): Fields to search in.
            vector_field (str, optional): Vector field name.
        """
        super().__init__(
            index=index,
            query=query,
            top=top,
            embedding=embedding,
            semantic_config=semantic_config,
            search_fields=search_fields or ["STR", "CODE"],  # REL is retrievable but not searchable
            vector_field=vector_field
        )
        
        self.rel_types = rel_types or ["PAR", "CHD", "RO", "SY", "RQ"]

    def search_relationships(self, target_code: str = None) -> List[Dict[str, Any]]:
        """
        Search for relationship data, optionally filtered by target code.
        
        Args:
            target_code (str, optional): Filter results to relationships 
                involving this specific code.
                
        Returns:
            List[Dict[str, Any]]: List of documents with relationship data,
                enhanced with parsed REL information.
        """
        try:
            # Get base search results
            results = self.run()
            
            # Filter and enhance results with relationship data
            relationship_results = []
            
            for result in results:
                document = result.get("document", {})
                rel_data = document.get("REL", [])
                
                if not rel_data:
                    continue
                
                # Parse REL data
                parsed_relationships = self._parse_rel_data(rel_data, target_code)
                
                if parsed_relationships:
                    # Add parsed relationships to the document
                    enhanced_result = result.copy()
                    enhanced_result["parsed_relationships"] = parsed_relationships
                    relationship_results.append(enhanced_result)
            
            return relationship_results
            
        except Exception as e:
            logger.exception("Relationship search failed")
            raise SearchError(f"Relationship search failed: {e}") from e

    def search_parent_child_hierarchy(self, code: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search for parent and child relationships for a specific code.
        
        Args:
            code (str): The ICD or SNOMED code to find relationships for.
            
        Returns:
            Dict containing 'parents' and 'children' lists with relationship data.
        """
        try:
            # For precise matching, do a focused search with just the code
            config = get_config()
            
            specific_search = Search(
                index=self.index,
                query=code,
                top=config.search_top_k,
                search_fields=["CODE", "STR"]
            )
            
            results = specific_search.run()
            
            parents = []
            children = []
            
            for result in results:
                document = result.get("document", {})
                doc_code = document.get("CODE", "")
                
                # Only process exact matches or closely related codes
                if code.upper() not in doc_code.upper():
                    continue
                
                rel_data = document.get("REL", [])
                parsed_rels = self._parse_rel_data(rel_data)
                
                for rel in parsed_rels:
                    if rel["REL"] == "PAR":
                        parents.append({
                            "parent_code": rel["CODE"],
                            "parent_name": rel["STR"],
                            "source": rel["SAB"],
                            "current_code": doc_code,
                            "current_name": document.get("STR", "")
                        })
                    elif rel["REL"] == "CHD":
                        children.append({
                            "child_code": rel["CODE"],
                            "child_name": rel["STR"],
                            "source": rel["SAB"],
                            "current_code": doc_code,
                            "current_name": document.get("STR", "")
                        })
            
            return {
                "parents": parents,
                "children": children,
                "query_code": code
            }
            
        except Exception as e:
            logger.exception("Parent-child hierarchy search failed")
            raise SearchError(f"Hierarchy search failed: {e}") from e

    def search_snomed_mappings(self, icd_code: str) -> List[Dict[str, Any]]:
        """
        Search for SNOMED mappings for a given ICD code.
        
        Args:
            icd_code (str): The ICD code to find SNOMED mappings for.
            
        Returns:
            List of SNOMED mapping data.
        """
        try:
            # Search for the ICD code to get its REL data
            config = get_config()
            
            code_search = Search(
                index=self.index,
                query=icd_code,
                top=max(5, config.search_top_k // 2),  # At least 5, or half of configured top_k
                search_fields=["CODE"]
            )
            
            results = code_search.run()
            snomed_mappings = []
            
            for result in results:
                document = result.get("document", {})
                doc_code = document.get("CODE", "")
                
                # Check for exact or close match
                if icd_code.upper() not in doc_code.upper():
                    continue
                
                # Look for SNOMED data in OHDSI mappings
                ohdsi_data = document.get("OHDSI", "")
                if ohdsi_data:
                    try:
                        ohdsi_json = json.loads(ohdsi_data)
                        maps = ohdsi_json.get("maps", [])
                        
                        for mapping in maps:
                            if mapping.get("vocabulary_id") == "SNOMED":
                                # SNOMED code is always in concept_code field for SNOMED vocabulary
                                relationship_id = mapping.get("relationship_id", "")
                                snomed_code = mapping.get("concept_code", "")
                                
                                snomed_mappings.append({
                                    "icd_code": doc_code,
                                    "icd_name": document.get("STR", ""),
                                    "snomed_code": snomed_code,
                                    "snomed_name": mapping.get("concept_name", ""),
                                    "relationship_id": relationship_id,
                                    "domain_id": mapping.get("domain_id", ""),
                                    "concept_class": mapping.get("concept_class_id", ""),
                                    "omop_concept_id": mapping.get("concept_id", "")  # Keep OMOP ID for reference
                                })
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.debug(f"Could not parse OHDSI data for {doc_code}: {e}")
                
                # Also check REL data for SNOMED relationships
                rel_data = document.get("REL", [])
                parsed_rels = self._parse_rel_data(rel_data)
                
                for rel in parsed_rels:
                    if rel["SAB"] == "SNOMEDCT_US":
                        snomed_mappings.append({
                            "icd_code": doc_code,
                            "icd_name": document.get("STR", ""),
                            "snomed_code": rel["CODE"],
                            "snomed_name": rel["STR"],
                            "relationship_type": rel["REL"],
                            "relationship_attribute": rel.get("RELA", ""),
                            "source": "REL_segment"
                        })
            
            return snomed_mappings
            
        except Exception as e:
            logger.exception("SNOMED mapping search failed")
            raise SearchError(f"SNOMED mapping search failed: {e}") from e

    def _parse_rel_data(self, rel_data: List, target_code: str = None) -> List[Dict[str, Any]]:
        """
        Parse REL segment data from JSON strings into structured format.
        
        Args:
            rel_data (List[Union[str, dict]]): List of JSON strings or dicts containing relationship data.
            target_code (str, optional): Filter for specific target code.
            
        Returns:
            List of parsed relationship dictionaries.
        """
        parsed_relationships = []
        
        for rel_item in rel_data:
            try:
                # Handle both dict (new format) and JSON string (old format)
                if isinstance(rel_item, dict):
                    rel_obj = rel_item
                elif isinstance(rel_item, str):
                    rel_obj = json.loads(rel_item)
                else:
                    logger.debug(f"Unexpected REL data type: {type(rel_item)}")
                    continue
                
                # Filter by relationship type if specified
                if rel_obj.get("REL") not in self.rel_types:
                    continue
                
                # Filter by target code if specified
                if target_code and target_code.upper() not in rel_obj.get("CODE", "").upper():
                    continue
                
                parsed_relationships.append({
                    "REL": rel_obj.get("REL", ""),
                    "RELA": rel_obj.get("RELA", ""),
                    "SAB": rel_obj.get("SAB", ""),
                    "AUI": rel_obj.get("AUI", ""),
                    "TTY": rel_obj.get("TTY", ""),
                    "STR": rel_obj.get("STR", ""),
                    "CODE": rel_obj.get("CODE", "")
                })
                
            except (json.JSONDecodeError, KeyError) as e:
                logger.debug(f"Could not parse REL data: {str(rel_item)[:100]}... Error: {e}")
        
        return parsed_relationships

    def format_relationships_for_display(self, relationships: List[Dict[str, Any]]) -> str:
        """
        Format relationship data for human-readable display.
        
        Args:
            relationships (List[Dict[str, Any]]): Parsed relationship data.
            
        Returns:
            str: Formatted relationship information.
        """
        if not relationships:
            return "No relationships found."
        
        formatted_lines = []
        
        # Group by relationship type
        by_type = {}
        for rel in relationships:
            rel_type = rel["REL"]
            if rel_type not in by_type:
                by_type[rel_type] = []
            by_type[rel_type].append(rel)
        
        # Format each type
        type_names = {
            "PAR": "Parent Codes",
            "CHD": "Child Codes", 
            "SY": "Synonyms",
            "RO": "Related Codes",
            "RQ": "Required/Associated Codes"
        }
        
        for rel_type, rels in by_type.items():
            type_name = type_names.get(rel_type, f"{rel_type} Relationships")
            formatted_lines.append(f"\n**{type_name}:**")
            
            for rel in rels:
                code = rel["CODE"]
                name = rel["STR"]
                source = rel["SAB"]
                rela = rel.get("RELA", "")
                
                line = f"- {code}: {name}"
                if rela:
                    line += f" ({rela})"
                line += f" [{source}]"
                
                formatted_lines.append(line)
        
        return "\n".join(formatted_lines)


__all__ = ["RelationshipSearch", "SearchError"]