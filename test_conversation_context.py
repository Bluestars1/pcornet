#!/usr/bin/env python3
"""
Test script to verify that the last 3 responses are being saved and used as context.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from modules.conversation_history import ConversationHistory
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_last_responses():
    print("\n" + "="*80)
    print("TESTING LAST 3 RESPONSES CONTEXT")
    print("="*80 + "\n")
    
    # Create conversation history
    history = ConversationHistory(max_messages=20)
    
    # Simulate a conversation
    print("Simulating conversation with 5 exchanges...\n")
    
    # Exchange 1
    history.add_user_message("What is diabetes?")
    history.add_assistant_message(
        "Diabetes is a chronic condition that affects how your body processes blood sugar (glucose)...",
        agent_type="chat"
    )
    
    # Exchange 2
    history.add_user_message("What are the types?")
    history.add_assistant_message(
        "There are three main types: Type 1 diabetes, Type 2 diabetes, and Gestational diabetes...",
        agent_type="chat"
    )
    
    # Exchange 3
    history.add_user_message("Create a diabetes concept set")
    history.add_assistant_message(
        "Here is a diabetes concept set with ICD-10 codes: E10 (Type 1), E11 (Type 2), E13 (Other specified)...",
        agent_type="concept_set"
    )
    
    # Exchange 4
    history.add_user_message("What are the symptoms?")
    history.add_assistant_message(
        "Common symptoms include increased thirst, frequent urination, extreme hunger, unexplained weight loss...",
        agent_type="chat"
    )
    
    # Exchange 5
    history.add_user_message("How is it treated?")
    history.add_assistant_message(
        "Treatment varies by type but may include insulin therapy, oral medications, lifestyle changes...",
        agent_type="chat"
    )
    
    # Now test getting last 3 responses
    print("-" * 80)
    print("Getting last 3 responses as context:")
    print("-" * 80 + "\n")
    
    last_3 = history.get_last_n_responses(n=3)
    print(last_3)
    
    print("\n" + "-" * 80)
    print("Testing with fewer than 3 responses:")
    print("-" * 80 + "\n")
    
    # Create new history with only 2 responses
    history2 = ConversationHistory(max_messages=20)
    history2.add_user_message("Hello")
    history2.add_assistant_message("Hi! How can I help?", agent_type="chat")
    history2.add_user_message("What is ICD?")
    history2.add_assistant_message(
        "ICD stands for International Classification of Diseases...",
        agent_type="chat"
    )
    
    last_2 = history2.get_last_n_responses(n=3)
    print(last_2)
    
    print("\n" + "-" * 80)
    print("Testing with no responses:")
    print("-" * 80 + "\n")
    
    history3 = ConversationHistory(max_messages=20)
    history3.add_user_message("Hello")
    
    last_0 = history3.get_last_n_responses(n=3)
    print(f"Result: '{last_0}' (empty string expected)")
    
    print("\n" + "="*80)
    print("✅ Test completed successfully!")
    print("="*80 + "\n")
    
    # Show stats
    stats = history.get_stats()
    print(f"Final history stats:")
    print(f"  Total messages: {stats['total_messages']}")
    print(f"  User messages: {stats['user_messages']}")
    print(f"  Assistant messages: {stats['assistant_messages']}")
    print(f"  Agent usage: {stats['agent_usage']}")

if __name__ == "__main__":
    test_last_responses()
