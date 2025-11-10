"""
Test suite to verify SEARCH_TOP_K configuration is used everywhere.
"""

import os
import pytest

os.environ['PYTHONWARNINGS'] = 'ignore'

from modules.config import get_config, AppConfig
from modules.agents.icd_agent import IcdAgent
from modules.agents.snomed_agent import SnomedAgent
from modules.relationship_search import RelationshipSearch
from modules.search_tool import Search


def test_config_loads_search_top_k():
    """Verify config loads SEARCH_TOP_K value."""
    os.environ['SEARCH_TOP_K'] = '15'
    config = get_config()
    assert config.search_top_k == 15


def test_config_default_value():
    """Verify default value works when SEARCH_TOP_K is not set."""
    # Temporarily remove env var
    original_value = os.environ.pop('SEARCH_TOP_K', None)
    try:
        config_default = AppConfig()
        assert config_default.search_top_k == 10
    finally:
        # Restore if it existed
        if original_value:
            os.environ['SEARCH_TOP_K'] = original_value


def test_agents_can_initialize():
    """Verify agents can access config."""
    os.environ['SEARCH_TOP_K'] = '15'
    
    icd_agent = IcdAgent()
    assert icd_agent is not None
    
    snomed_agent = SnomedAgent()
    assert snomed_agent is not None


def test_search_tool_respects_top_parameter():
    """Check that Search tool respects top parameter."""
    os.environ['SEARCH_TOP_K'] = '15'
    config = get_config()
    
    search = Search(index="icd", query="test", top=config.search_top_k)
    assert search.top == 15


def test_relationship_search_inherits_correctly():
    """Verify RelationshipSearch inherits correctly."""
    os.environ['SEARCH_TOP_K'] = '15'
    config = get_config()
    
    rel_search = RelationshipSearch(index="icd", query="test", top=config.search_top_k)
    assert rel_search.top == 15
