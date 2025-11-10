"""
Test Concept Set Follow-Up Functionality

Tests the ability to modify concept sets with follow-up queries.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from modules.master_agent import MasterAgent

print("Testing Concept Set Follow-Up Functionality")
print("=" * 80)

agent = MasterAgent()
session_id = "test_session_001"

# Test Case 1: Create concept set and modify it
print("\n" + "=" * 80)
print("TEST CASE 1: Single Concept Set - Remove Codes")
print("=" * 80)

print("\n[Query 1] Creating diabetes concept set...")
response1 = agent.chat(
    query="Create diabetes concept set with ICD and SNOMED codes",
    session_id=session_id
)
print(f"\n✅ Response received ({len(response1)} chars)")
print(f"Preview: {response1[:200]}...")

# Check cache
cache_size = len(agent.concept_set_cache.get(session_id, []))
print(f"\n📊 Cache status: {cache_size} concept set(s) stored")

print("\n[Query 2] Removing type 1 diabetes codes...")
response2 = agent.chat(
    query="Remove type 1 diabetes codes from that table",
    session_id=session_id
)
print(f"\n✅ Response received ({len(response2)} chars)")
print(f"Preview: {response2[:200]}...")

# Check if type 1 codes removed
if "type 1" in response2.lower() or "e10" in response2.lower():
    print("\n⚠️  Warning: Type 1 codes may still be present")
else:
    print("\n✅ Type 1 codes appear to be removed")

# Test Case 2: Multiple concept sets with clarification
print("\n" + "=" * 80)
print("TEST CASE 2: Multiple Concept Sets - Clarification")
print("=" * 80)

print("\n[Query 3] Creating hypertension concept set...")
response3 = agent.chat(
    query="Create hypertension concept set",
    session_id=session_id
)
print(f"\n✅ Response received ({len(response3)} chars)")
print(f"Preview: {response3[:200]}...")

# Check cache
cache_size = len(agent.concept_set_cache.get(session_id, []))
print(f"\n📊 Cache status: {cache_size} concept set(s) stored")

print("\n[Query 4] Ambiguous removal (should ask for clarification)...")
response4 = agent.chat(
    query="Remove code I10",
    session_id=session_id
)
print(f"\n✅ Response received ({len(response4)} chars)")
print(f"Response:\n{response4}")

# Check if clarification was requested
if "found" in response4.lower() and "specify" in response4.lower():
    print("\n✅ Clarification correctly requested")
else:
    print("\n⚠️  Expected clarification request")

# Test Case 3: Specify target concept set
print("\n" + "=" * 80)
print("TEST CASE 3: Specify Target Concept Set")
print("=" * 80)

print("\n[Query 5] Remove from hypertension concept set...")
response5 = agent.chat(
    query="Remove code I10 from the hypertension concept set",
    session_id=session_id
)
print(f"\n✅ Response received ({len(response5)} chars)")
print(f"Preview: {response5[:200]}...")

# Check if I10 removed
if "i10" in response5.lower():
    print("\n⚠️  Warning: Code I10 may still be present")
else:
    print("\n✅ Code I10 appears to be removed")

# Test Case 4: Most recent
print("\n" + "=" * 80)
print("TEST CASE 4: Use Most Recent Concept Set")
print("=" * 80)

print("\n[Query 6] Modify most recent concept set...")
response6 = agent.chat(
    query="Show only essential hypertension codes from the most recent one",
    session_id=session_id
)
print(f"\n✅ Response received ({len(response6)} chars)")
print(f"Preview: {response6[:200]}...")

# Test Case 5: Add column
print("\n" + "=" * 80)
print("TEST CASE 5: Add Column to Table")
print("=" * 80)

print("\n[Query 7] Add SAB column to diabetes table...")
response7 = agent.chat(
    query="Add a SAB column to the diabetes concept set",
    session_id=session_id
)
print(f"\n✅ Response received ({len(response7)} chars)")
print(f"Preview: {response7[:200]}...")

# Check if SAB column added
if "sab" in response7.lower():
    print("\n✅ SAB column appears to be added")
else:
    print("\n⚠️  Warning: SAB column may not be present")

# Summary
print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)

final_cache_size = len(agent.concept_set_cache.get(session_id, []))
print(f"\n✅ Final cache: {final_cache_size} concept set(s)")

concept_sets = agent._get_concept_sets(session_id)
if concept_sets:
    print(f"\n📋 Stored concept sets:")
    for i, cs in enumerate(concept_sets, 1):
        print(f"   {i}. {cs['name']} (query: {cs['query'][:50]}...)")

print("\n" + "=" * 80)
print("✅ All tests completed")
print("=" * 80)

print("\n💡 Next steps:")
print("   1. Review the responses above to verify modifications worked")
print("   2. Test in the Streamlit app for full UI experience")
print("   3. Check app.log for detailed logging")
