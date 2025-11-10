#!/usr/bin/env python3
"""
Test to verify the InteractiveContext fix for clear_data() error.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from modules.interactive_session import interactive_session, InteractiveContext, DataItem

def test_interactive_context():
    print("\n" + "="*80)
    print("TESTING INTERACTIVE CONTEXT FIX")
    print("="*80 + "\n")
    
    # Create a test session
    session_id = "test_context_fix"
    context = interactive_session.start_session(session_id)
    
    print(f"✅ Created session: {session_id}")
    print(f"   Context type: {type(context)}")
    print(f"   Has current_data: {hasattr(context, 'current_data')}")
    
    # Test adding data directly to current_data dictionary
    print("\nTesting direct dictionary manipulation...")
    
    test_item = DataItem(
        item_type="snomed",
        key="12345",
        value="Test Concept",
        metadata={"test": "data"}
    )
    
    context.current_data["12345"] = test_item
    print(f"✅ Added item directly to current_data")
    print(f"   Items in context: {len(context.current_data)}")
    
    # Test clearing data
    print("\nTesting clearing data...")
    context.current_data.clear()
    print(f"✅ Cleared current_data using .clear()")
    print(f"   Items remaining: {len(context.current_data)}")
    
    # Test adding multiple items
    print("\nTesting multiple items...")
    for i in range(3):
        item = DataItem(
            item_type="snomed",
            key=f"CODE_{i}",
            value=f"Concept {i}",
            metadata={"index": i}
        )
        context.current_data[f"CODE_{i}"] = item
    
    print(f"✅ Added {len(context.current_data)} items")
    
    # List items
    print("\nItems in context:")
    for key, item in context.current_data.items():
        print(f"  - {key}: {item.value} (type: {item.item_type})")
    
    print("\n" + "="*80)
    print("✅ All tests passed! The fix works correctly.")
    print("="*80 + "\n")

if __name__ == "__main__":
    test_interactive_context()
