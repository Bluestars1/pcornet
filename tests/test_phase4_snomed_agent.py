"""
Test suite for Phase 4: SnomedAgent Creation
Verifies that SnomedAgent works with the SNOMED index registry.
"""

import os
import warnings

# Suppress warnings for cleaner output
os.environ['PYTHONWARNINGS'] = 'ignore'
warnings.filterwarnings('ignore')

from modules.agents.snomed_agent import SnomedAgent
from modules.agents.icd_agent import IcdAgent
from modules.config import get_config


def test_snomed_agent_initialization():
    """Test that SnomedAgent initializes correctly."""
    # Create SnomedAgent with default (should use "snomed" registry key)
    agent = SnomedAgent()
    
    # Verify it's using the registry key
    assert agent.index_name == "snomed"


def test_snomed_agent_config_integration():
    """Test that SnomedAgent gets correct config from registry."""
    agent = SnomedAgent()
    config = get_config()
    
    # Get SNOMED config from registry
    snomed_config = config.get_index_config("snomed")
    
    # Verify config is correct
    assert snomed_config.name is not None
    assert snomed_config.vector_field == "content_vector"
    assert "STR" in snomed_config.search_fields
    assert "CODE" in snomed_config.search_fields
    assert "SAB" in snomed_config.search_fields


def test_both_agents_coexist():
    """Test that IcdAgent and SnomedAgent can coexist."""
    # Create both agents
    icd_agent = IcdAgent()
    snomed_agent = SnomedAgent()
    
    config = get_config()
    icd_config = config.get_index_config("icd")
    snomed_config = config.get_index_config("snomed")
    
    # Verify they use different indices
    assert icd_agent.index_name != snomed_agent.index_name
    assert icd_config.name != snomed_config.name


def test_snomed_agent_methods():
    """Test that SnomedAgent has expected methods."""
    agent = SnomedAgent()
    
    # Check for expected methods
    assert hasattr(agent, 'process')
    assert hasattr(agent, 'process_interactive')
    assert hasattr(agent, 'get_concept_details')
    assert hasattr(agent, '_generate_llm_response')
    assert hasattr(agent, '_normalize_citations')


def test_schema_differences():
    """Test that ICD and SNOMED indices have correct schema configurations."""
    config = get_config()
    icd_config = config.get_index_config("icd")
    snomed_config = config.get_index_config("snomed")
    
    # Verify both use content_vector
    assert icd_config.vector_field == "content_vector"
    assert snomed_config.vector_field == "content_vector"
    
    # SNOMED has SAB field
    assert "SAB" in snomed_config.search_fields
    
    # Both have STR and CODE
    assert "STR" in icd_config.search_fields
    assert "CODE" in icd_config.search_fields
    assert "STR" in snomed_config.search_fields
    assert "CODE" in snomed_config.search_fields
