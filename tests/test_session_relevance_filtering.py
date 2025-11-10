"""
Test Session Relevance Filtering

Verifies that session data is filtered by semantic relevance to current query.
"""
import pytest
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.interactive_session import interactive_session, DataItem
from modules.master_agent import MasterAgent
from datetime import datetime


def test_session_relevance_filtering():
    """Test that unrelated codes are filtered out based on query relevance."""
    
    # Create test session
    session_id = "test_relevance_filter"
    interactive_session.start_session(session_id)
    
    # Add diabetes codes
    diabetes_codes = [
        DataItem(
            item_type="icd_code",
            key="E10",
            value="Type 1 diabetes mellitus",
            metadata={"full_document": {"CODE": "E10", "STR": "Type 1 diabetes mellitus"}},
            source_query="diabetes search"
        ),
        DataItem(
            item_type="icd_code",
            key="E11",
            value="Type 2 diabetes mellitus",
            metadata={"full_document": {"CODE": "E11", "STR": "Type 2 diabetes mellitus"}},
            source_query="diabetes search"
        ),
    ]
    
    # Add unrelated codes (sepsis, hypertension)
    unrelated_codes = [
        DataItem(
            item_type="icd_code",
            key="Z51.A",
            value="Encounter for sepsis aftercare",
            metadata={"full_document": {"CODE": "Z51.A", "STR": "Encounter for sepsis aftercare"}},
            source_query="sepsis search"
        ),
        DataItem(
            item_type="icd_code",
            key="I10",
            value="Essential hypertension",
            metadata={"full_document": {"CODE": "I10", "STR": "Essential hypertension"}},
            source_query="hypertension search"
        ),
    ]
    
    # Add all codes to session
    for code in diabetes_codes + unrelated_codes:
        interactive_session.add_data_item(session_id, code)
    
    # Initialize MasterAgent
    agent = MasterAgent()
    
    # Test 1: Query for diabetes - should filter out unrelated codes
    diabetes_context = agent._get_session_context_string(
        session_id=session_id,
        current_query="show me diabetes codes",
        relevance_threshold=0.3
    )
    
    print("\n=== Test 1: Diabetes Query ===")
    print(f"Context returned:\n{diabetes_context}")
    
    # Verify diabetes codes are included
    assert "E10" in diabetes_context, "E10 should be included for diabetes query"
    assert "E11" in diabetes_context, "E11 should be included for diabetes query"
    
    # Verify unrelated codes are filtered out
    assert "Z51.A" not in diabetes_context or diabetes_context.count("Z51.A") == 0, \
        "Z51.A (sepsis) should be filtered out for diabetes query"
    
    print("✓ Diabetes codes included, sepsis codes filtered out")
    
    # Test 2: Query for hypertension - should include I10, filter out others
    hypertension_context = agent._get_session_context_string(
        session_id=session_id,
        current_query="show hypertension codes",
        relevance_threshold=0.3
    )
    
    print("\n=== Test 2: Hypertension Query ===")
    print(f"Context returned:\n{hypertension_context}")
    
    # Verify hypertension is included
    assert "I10" in hypertension_context, "I10 should be included for hypertension query"
    
    print("✓ Hypertension codes included")
    
    # Test 3: No query filter - should return all codes
    all_context = agent._get_session_context_string(
        session_id=session_id,
        current_query=None  # No filtering
    )
    
    print("\n=== Test 3: No Filter (All Codes) ===")
    print(f"Context returned:\n{all_context}")
    
    assert "E10" in all_context, "E10 should be in unfiltered context"
    assert "E11" in all_context, "E11 should be in unfiltered context"
    assert "Z51.A" in all_context, "Z51.A should be in unfiltered context"
    assert "I10" in all_context, "I10 should be in unfiltered context"
    
    print("✓ All codes included when no filter applied")
    
    # Cleanup
    interactive_session.clear_session(session_id, delete_file=True)
    
    print("\n=== All Tests Passed ✓ ===")


def test_relevance_threshold_levels():
    """Test different threshold levels (strict vs permissive)."""
    
    session_id = "test_threshold_levels"
    interactive_session.start_session(session_id)
    
    # Add codes with varying relevance to "diabetes"
    codes = [
        DataItem(
            item_type="icd_code",
            key="E11",
            value="Type 2 diabetes mellitus",
            metadata={"full_document": {"CODE": "E11", "STR": "Type 2 diabetes mellitus"}},
            source_query="test"
        ),
        DataItem(
            item_type="icd_code",
            key="E08",
            value="Diabetes mellitus due to underlying condition",
            metadata={"full_document": {"CODE": "E08", "STR": "Diabetes mellitus due to underlying condition"}},
            source_query="test"
        ),
    ]
    
    for code in codes:
        interactive_session.add_data_item(session_id, code)
    
    agent = MasterAgent()
    
    # Test strict threshold (0.5) - only very similar items
    strict_context = agent._get_session_context_string(
        session_id=session_id,
        current_query="Type 2 diabetes",
        relevance_threshold=0.5  # Strict
    )
    
    print("\n=== Strict Threshold (0.5) ===")
    print(f"Results: {strict_context}")
    
    # Test permissive threshold (0.2) - more items included
    permissive_context = agent._get_session_context_string(
        session_id=session_id,
        current_query="Type 2 diabetes",
        relevance_threshold=0.2  # Permissive
    )
    
    print("\n=== Permissive Threshold (0.2) ===")
    print(f"Results: {permissive_context}")
    
    # Permissive should have same or more items than strict
    strict_count = strict_context.count("E") if strict_context else 0
    permissive_count = permissive_context.count("E") if permissive_context else 0
    
    assert permissive_count >= strict_count, \
        "Permissive threshold should include same or more codes than strict"
    
    print(f"✓ Permissive ({permissive_count} codes) >= Strict ({strict_count} codes)")
    
    # Cleanup
    interactive_session.clear_session(session_id, delete_file=True)
    
    print("\n=== Threshold Test Passed ✓ ===")


if __name__ == "__main__":
    print("Testing Session Relevance Filtering\n")
    print("=" * 60)
    
    try:
        test_session_relevance_filtering()
        test_relevance_threshold_levels()
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
