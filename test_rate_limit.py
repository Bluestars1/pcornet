#!/usr/bin/env python3
"""
Test script to trigger a concept set query and monitor for rate limit errors.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from modules.master_agent import MasterAgent
import logging

# Configure logging to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def test_concept_set():
    print("\n" + "="*80)
    print("TESTING CONCEPT SET - MONITORING FOR RATE LIMITS")
    print("="*80 + "\n")
    
    # Create test session
    session_id = "test_rate_limit_session"
    
    # Initialize agent
    print("Initializing MasterAgent...")
    agent = MasterAgent()
    print("✅ Agent initialized\n")
    
    # Test query
    query = "Create a concept set for diabetes"
    print(f"Query: {query}")
    print("\n" + "-"*80)
    print("EXECUTING QUERY - WATCH FOR RATE LIMIT ERRORS")
    print("-"*80 + "\n")
    
    try:
        response = agent.chat(query, session_id=session_id)
        print("\n" + "="*80)
        print("RESPONSE RECEIVED:")
        print("="*80)
        print(response[:500] + "..." if len(response) > 500 else response)
        print("\n✅ Test completed successfully")
        
    except Exception as e:
        print("\n" + "="*80)
        print("❌ ERROR OCCURRED:")
        print("="*80)
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        
        if "429" in str(e) or "RateLimitReached" in str(e):
            print("\n⚠️  RATE LIMIT ERROR DETECTED")
        
        raise

if __name__ == "__main__":
    test_concept_set()
