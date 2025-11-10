"""
Test Medical Query Expansion

Verifies that medical conditions are expanded to include related/causative conditions.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from modules.master_agent import MasterAgent

print("Testing Medical Query Expansion")
print("=" * 80)

agent = MasterAgent()

test_cases = [
    {
        "query": "Create concept set for chronic pain",
        "expected_terms": ["chronic pain", "fibromyalgia", "arthritis", "pain"]
    },
    {
        "query": "Show me diabetes codes",
        "expected_terms": ["diabetes", "diabetic", "type 1", "type 2"]
    },
    {
        "query": "Heart failure concept set",
        "expected_terms": ["heart failure", "cardiac failure", "CHF"]
    },
    {
        "query": "Find hypertension ICD codes",
        "expected_terms": ["hypertension", "high blood pressure", "HTN"]
    }
]

for i, test in enumerate(test_cases, 1):
    print(f"\n{'='*80}")
    print(f"Test Case {i}: {test['query']}")
    print("-" * 80)
    
    try:
        expanded_query = agent._extract_and_expand_medical_query(test['query'])
        
        print(f"\n✅ Expanded Query:")
        print(f"   {expanded_query}")
        
        # Parse the OR-separated terms
        terms = [term.strip() for term in expanded_query.split(' OR ')]
        
        print(f"\n📋 Extracted {len(terms)} terms:")
        for term in terms:
            print(f"   • {term}")
        
        # Check if expected terms are present
        query_lower = expanded_query.lower()
        found_expected = []
        missing_expected = []
        
        for expected in test['expected_terms']:
            if expected.lower() in query_lower:
                found_expected.append(expected)
            else:
                missing_expected.append(expected)
        
        print(f"\n🔍 Coverage Check:")
        print(f"   Found: {len(found_expected)}/{len(test['expected_terms'])} expected terms")
        for term in found_expected:
            print(f"   ✓ {term}")
        
        if missing_expected:
            print(f"\n   Missing (may be OK if clinically equivalent):")
            for term in missing_expected:
                print(f"   ⚠ {term}")
        
        if len(found_expected) >= len(test['expected_terms']) * 0.5:
            print(f"\n✅ PASS: Good coverage of related conditions")
        else:
            print(f"\n⚠️  PARTIAL: Some expected terms missing")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

print(f"\n{'='*80}")
print("Test Complete")
print("=" * 80)
