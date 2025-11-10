"""
Complete Integration Test - Multi-Index Architecture
Tests all phases working together with both ICD and SNOMED indices.
"""

import os
import warnings

# Suppress warnings for cleaner output
os.environ['PYTHONWARNINGS'] = 'ignore'
warnings.filterwarnings('ignore')

from modules.config import get_config
from modules.search_tool import Search
from modules.agents.icd_agent import IcdAgent
from modules.agents.snomed_agent import SnomedAgent


def test_configuration():
    """Test that configuration is loaded correctly."""
    config = get_config()
    
    assert len(config.indices) == 2
    assert "icd" in config.indices
    assert "snomed" in config.indices


def test_search_tool_icd():
    """Test Search tool with ICD index."""
    icd_search = Search(
        index="icd",  # Registry key
        query="test query",
        top=5
    )
    
    assert icd_search.index is not None
    assert icd_search.vector_field == "content_vector"


def test_search_tool_snomed():
    """Test Search tool with SNOMED index."""
    snomed_search = Search(
        index="snomed",  # Registry key
        query="test query",
        top=5
    )
    
    assert snomed_search.index is not None
    assert snomed_search.vector_field == "content_vector"


def test_agents():
    """Test both agents initialize correctly."""
    # Test ICD Agent
    icd_agent = IcdAgent()
    assert icd_agent.index_name == "icd"
    assert icd_agent.llm is not None
    
    # Test SNOMED Agent
    snomed_agent = SnomedAgent()
    assert snomed_agent.index_name == "snomed"
    assert snomed_agent.llm is not None


def test_schema_awareness():
    """Test that different schemas are handled correctly."""
    config = get_config()
    
    # Get both configs
    icd_cfg = config.get_index_config("icd")
    snomed_cfg = config.get_index_config("snomed")
    
    # Verify they use content_vector
    assert icd_cfg.vector_field == "content_vector"
    assert snomed_cfg.vector_field == "content_vector"
    assert "SAB" in snomed_cfg.search_fields


def test_backward_compatibility():
    """Test backward compatibility with direct index names."""
    # Old way - direct index name
    search_old = Search(
        index="pcornet-icd-index",  # Direct name
        query="test",
        use_index_config=True  # Will try registry but fall back
    )
    assert search_old.index == "pcornet-icd-index"
    
    # New way - registry key
    search_new = Search(
        index="icd",  # Registry key
        query="test"
    )
    assert search_new.index is not None


def test_extensibility():
    """Test that system is ready for more indices."""
    config = get_config()
    
    # Verify indices are registered
    assert len(config.indices) >= 2
    assert "icd" in config.indices
    assert "snomed" in config.indices
