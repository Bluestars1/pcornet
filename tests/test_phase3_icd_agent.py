"""
Test suite for Phase 3: Updated IcdAgent with Index Registry
Verifies that IcdAgent uses the index registry correctly.
"""

import os
import warnings

# Suppress warnings for cleaner output
os.environ['PYTHONWARNINGS'] = 'ignore'
warnings.filterwarnings('ignore')

from modules.agents.icd_agent import IcdAgent
from modules.config import get_config


def test_icd_agent_initialization():
    """Test that IcdAgent initializes with registry key."""
    # Create IcdAgent with default (should use "icd" registry key)
    agent = IcdAgent()
    
    # Verify it's using the registry key
    assert agent.index_name == "icd"


def test_icd_agent_with_custom_index():
    """Test that IcdAgent can still use custom index names."""
    # Create IcdAgent with custom index name
    agent = IcdAgent(index="custom-index")
    
    assert agent.index_name == "custom-index"


def test_icd_agent_search_integration():
    """Test that IcdAgent properly passes index to Search tool."""
    # This test verifies the integration but doesn't actually run a search
    # (would require valid Azure credentials and network access)
    
    agent = IcdAgent()
    config = get_config()
    
    # Verify the registry has the ICD index configured
    icd_config = config.get_index_config("icd")
    
    assert icd_config.name is not None
    assert icd_config.vector_field == "content_vector"
    assert len(icd_config.search_fields) > 0
    
    # Verify agent is using the same key
    assert agent.index_name == "icd"


def test_backward_compatibility():
    """Test that existing code using direct index names still works."""
    # Old way: direct index name
    agent_old = IcdAgent(index="pcornet-icd-index")
    assert agent_old.index_name == "pcornet-icd-index"
    
    # New way: registry key
    agent_new = IcdAgent()  # Uses "icd" by default
    assert agent_new.index_name == "icd"
