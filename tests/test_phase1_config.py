"""
Test suite for Phase 1: Multi-Index Configuration
Verifies that IndexConfig and the index registry are working correctly.
"""

import os
import warnings

# Suppress warnings for cleaner output
os.environ['PYTHONWARNINGS'] = 'ignore'
warnings.filterwarnings('ignore')

from modules.config import get_config, IndexConfig


def test_index_config_class():
    """Test that IndexConfig class works as expected."""
    test_config = IndexConfig(
        name="test-index",
        vector_field="test_vector",
        search_fields=["field1", "field2"],
        semantic_config="testConfig",
        description="Test index description"
    )
    
    assert test_config.name == "test-index"
    assert test_config.vector_field == "test_vector"
    assert test_config.search_fields == ["field1", "field2"]
    assert test_config.semantic_config == "testConfig"


def test_app_config_indices():
    """Test that AppConfig loads and registers indices correctly."""
    config = get_config()
    
    # Check that indices registry exists
    assert hasattr(config, 'indices'), "AppConfig should have 'indices' attribute"
    assert len(config.indices) >= 2, "Should have at least 2 registered indices"
    
    # Check ICD index
    icd_config = config.indices.get("icd")
    assert icd_config is not None, "ICD index should be registered"
    assert icd_config.vector_field == "content_vector"
    assert "STR" in icd_config.search_fields
    assert "CODE" in icd_config.search_fields
    
    # Check SNOMED index
    snomed_config = config.indices.get("snomed")
    assert snomed_config is not None, "SNOMED index should be registered"
    assert snomed_config.vector_field == "content_vector"
    assert "STR" in snomed_config.search_fields
    assert "CODE" in snomed_config.search_fields
    assert "SAB" in snomed_config.search_fields


def test_get_index_config():
    """Test the get_index_config method."""
    config = get_config()
    
    # Test valid retrieval
    icd_config = config.get_index_config("icd")
    assert icd_config.name is not None
    
    snomed_config = config.get_index_config("snomed")
    assert snomed_config.name is not None
    
    # Test invalid key raises ValueError
    try:
        config.get_index_config("invalid_key")
        assert False, "Should have raised ValueError for invalid key"
    except ValueError:
        pass  # Expected


def test_backward_compatibility():
    """Test that backward compatibility is maintained."""
    config = get_config()
    
    # Check that old attribute still exists
    assert hasattr(config, 'pcornet_icd_index')
    
    # Check that it matches the new registry
    assert config.pcornet_icd_index == config.indices["icd"].name
