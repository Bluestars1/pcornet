"""
Diagnostic tests to verify vector field configuration.
"""

import os
import pytest

os.environ['PYTHONWARNINGS'] = 'ignore'

from modules.config import get_config
from modules.search_tool import Search
from modules.agents.icd_agent import IcdAgent


def test_icd_index_vector_field():
    """Check ICD index vector field configuration."""
    config = get_config()
    icd_config = config.get_index_config("icd")
    
    assert icd_config.vector_field == "content_vector"
    assert icd_config.name is not None
    assert len(icd_config.search_fields) > 0


def test_snomed_index_vector_field():
    """Check SNOMED index vector field configuration."""
    config = get_config()
    snomed_config = config.get_index_config("snomed")
    
    assert snomed_config.vector_field == "content_vector"
    assert snomed_config.name is not None
    assert len(snomed_config.search_fields) > 0


def test_search_tool_uses_config_vector_field():
    """Test Search tool uses configured vector field from registry."""
    search = Search(index="icd", query="test", top=5)
    
    assert search.vector_field == "content_vector"
    assert search.index is not None
    assert search.search_fields is not None


def test_icd_agent_search_uses_correct_vector_field():
    """Test IcdAgent creates searches with correct vector field."""
    icd_agent = IcdAgent()
    
    # Simulate IcdAgent search creation
    test_search = Search(
        index=icd_agent.index_name,
        query="test",
        top=10
    )
    
    assert test_search.vector_field == "content_vector"
    assert test_search.index is not None


def test_all_vector_fields_consistent():
    """Verify all vector fields are consistently set to content_vector."""
    config = get_config()
    icd_config = config.get_index_config("icd")
    
    search = Search(index="icd", query="test", top=5)
    
    icd_agent = IcdAgent()
    test_search = Search(index=icd_agent.index_name, query="test", top=10)
    
    assert icd_config.vector_field == "content_vector"
    assert search.vector_field == "content_vector"
    assert test_search.vector_field == "content_vector"
