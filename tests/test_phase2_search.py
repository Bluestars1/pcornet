"""
Test suite for Phase 2: Enhanced Search Tool
Verifies that Search class can use index config registry while maintaining backward compatibility.
"""

import os
import warnings

# Suppress warnings for cleaner output
os.environ['PYTHONWARNINGS'] = 'ignore'
warnings.filterwarnings('ignore')

from modules.search_tool import Search
from modules.config import get_config


def test_search_icd_with_registry_key():
    """Test that Search can use ICD index registry key."""
    search_icd = Search(
        index="icd",  # Use registry key
        query="diabetes",
        top=5,
        use_index_config=True
    )
    
    # Check it resolved to the correct index name
    assert search_icd.index is not None
    assert search_icd.vector_field == "content_vector"
    assert "STR" in search_icd.search_fields
    assert "CODE" in search_icd.search_fields


def test_search_snomed_with_registry_key():
    """Test that Search can use SNOMED index registry key."""
    search_snomed = Search(
        index="snomed",  # Use registry key
        query="hypertension",
        top=5,
        use_index_config=True
    )
    
    # Verify index resolution
    assert search_snomed.index is not None
    assert search_snomed.vector_field == "content_vector"
    assert "STR" in search_snomed.search_fields
    assert "SAB" in search_snomed.search_fields


def test_search_direct_index_name():
    """Test that Search still works with direct index names."""
    # Test with direct index name (old approach)
    search_direct = Search(
        index="pcornet-icd-index",  # Direct index name
        query="diabetes",
        top=5,
        use_index_config=True  # Will try registry but fall back
    )
    
    assert search_direct.index == "pcornet-icd-index"


def test_search_bypass_registry():
    """Test that use_index_config=False bypasses registry."""
    # Test with use_index_config=False (completely bypass registry)
    search_bypass = Search(
        index="some-other-index",
        query="test",
        top=5,
        use_index_config=False  # Explicitly bypass registry
    )
    
    assert search_bypass.index == "some-other-index"


def test_search_override_params():
    """Test that explicit parameters override registry config."""
    search_override = Search(
        index="icd",
        query="test",
        top=5,
        vector_field="custom_vector",  # Override registry
        search_fields=["custom_field"],  # Override registry
        semantic_config="customConfig",  # Override registry
        use_index_config=True
    )
    
    # Index name should come from registry
    assert search_override.index is not None
    # But other fields should be overridden
    assert search_override.vector_field == "custom_vector"
    assert search_override.search_fields == ["custom_field"]
    assert search_override.semantic_config == "customConfig"


def test_schema_awareness():
    """Test that different indices get their correct schema configurations."""
    config = get_config()
    
    # Get both index configs
    icd_cfg = config.get_index_config("icd")
    snomed_cfg = config.get_index_config("snomed")
    
    # Create searches for both
    search_icd = Search(index="icd", query="test", use_index_config=True)
    search_snomed = Search(index="snomed", query="test", use_index_config=True)
    
    # Verify they use the configured vector fields
    assert search_icd.vector_field == "content_vector"
    assert search_snomed.vector_field == "content_vector"
