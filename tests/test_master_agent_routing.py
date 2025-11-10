"""
Test suite for MasterAgent SNOMED Routing
Verifies that MasterAgent correctly routes queries to ICD and SNOMED agents.
"""

import os
import warnings

os.environ['PYTHONWARNINGS'] = 'ignore'
warnings.filterwarnings('ignore')

from modules.master_agent import MasterAgent


def test_master_agent_initialization():
    """Test that MasterAgent initializes with all agents including SNOMED."""
    master = MasterAgent()
    
    # Check that all agents are present
    assert hasattr(master, 'chat_agent')
    assert hasattr(master, 'icd_agent')
    assert hasattr(master, 'snomed_agent')
    assert hasattr(master, 'concept_set_extractor_agent')


def test_snomed_query_classification():
    """Test that SNOMED queries are correctly classified."""
    master = MasterAgent()
    
    # Test various SNOMED query patterns
    snomed_queries = [
        "What is SNOMED code 38341003?",
        "Find SNOMED CT codes for hypertension",
        "Show me snomedct terms for diabetes",
        "Search for sct concepts related to fever",
        "What are snomed clinical terms for pneumonia?"
    ]
    
    for query in snomed_queries:
        agent_type = master._classify_agent_type(query)
        assert agent_type == "snomed", f"Expected 'snomed' but got '{agent_type}' for query: {query}"


def test_icd_query_classification():
    """Test that ICD queries are still correctly classified."""
    master = MasterAgent()
    
    # Test various ICD query patterns
    icd_queries = [
        "What is ICD code I10?",
        "Find ICD-10 codes for diabetes",
        "Show me diagnosis codes for hypertension",
        "What is code I50?",
        "Search for medical billing code E11"
    ]
    
    for query in icd_queries:
        agent_type = master._classify_agent_type(query)
        assert agent_type == "icd", f"Expected 'icd' but got '{agent_type}' for query: {query}"


def test_chat_query_classification():
    """Test that general queries are classified as chat."""
    master = MasterAgent()
    
    # Test general chat queries
    chat_queries = [
        "Hello, how are you?",
        "What can you help me with?",
        "Tell me about medical coding",
        "Explain the difference between ICD and SNOMED",
        "What is a concept set?"
    ]
    
    for query in chat_queries:
        agent_type = master._classify_agent_type(query)
        assert agent_type == "chat", f"Expected 'chat' but got '{agent_type}' for query: {query}"


def test_routing_methods_exist():
    """Test that routing methods exist on MasterAgent."""
    master = MasterAgent()
    
    # Check for routing method
    assert hasattr(master, '_classify_agent_type')
    assert callable(master._classify_agent_type)
    
    # Check for process methods
    assert hasattr(master, 'process')
    assert callable(master.process)


def test_agent_distinction():
    """Test that ICD and SNOMED agents are properly distinguished."""
    master = MasterAgent()
    
    # Specific ICD query
    icd_result = master._classify_agent_type("What is ICD-10 code E11.9?")
    assert icd_result == "icd"
    
    # Specific SNOMED query  
    snomed_result = master._classify_agent_type("What is SNOMED code 44054006?")
    assert snomed_result == "snomed"
    
    # Verify they're different
    assert icd_result != snomed_result


def test_priority_ordering():
    """Test that SNOMED and ICD keywords are properly prioritized."""
    master = MasterAgent()
    
    # SNOMED-specific query
    snomed_query = "Find SNOMED CT codes for diabetes with ICD mapping"
    result = master._classify_agent_type(snomed_query)
    assert result == "snomed", "SNOMED keywords should take precedence"
    
    # ICD-specific query
    icd_query = "Find ICD-10 diagnosis codes"
    result = master._classify_agent_type(icd_query)
    assert result == "icd"
