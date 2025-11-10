# Concept Set Follow-Up Queries

## Overview

After creating a concept set, you can now modify it with natural language follow-up queries. The system stores concept set data in memory and allows you to:

- **Remove/exclude** specific codes or conditions
- **Add columns** or show additional fields
- **Filter** by specific criteria
- **Modify** the table without re-running searches

## How It Works

### 1. Create Concept Set (Initial Query)

```
User: "Create chronic pain concept set with ICD and SNOMED codes"

System:
1. Expands query to related conditions
2. Searches Azure AI Search
3. Extracts and formats data
4. Displays table
5. ✅ Stores raw data in memory for follow-ups
```

### 2. Follow-Up Query (Modification)

```
User: "Remove fibromyalgia codes from that table"

System:
1. Detects follow-up pattern ("remove", "from that table")
2. Retrieves stored raw data
3. Routes to chat agent with modification instruction
4. Returns modified table
```

## Supported Follow-Up Patterns

### Remove/Exclude Codes

```
"Remove fibromyalgia codes"
"Exclude code E11.9"
"Hide gestational diabetes codes"
"Show without type 1 diabetes"
"Filter out Z codes"
```

### Add/Show Columns

```
"Add a column for OHDSI mappings"
"Show the SAB field"
"Include code descriptions"
"Add a score column"
```

### Filter by Criteria

```
"Only show type 2 diabetes codes"
"Just show E11 codes"
"Show only codes with SNOMED mappings"
```

### Format Changes

```
"Change to JSON format"
"Show as a list instead"
"Modify to include metadata"
```

## Multiple Concept Sets

### Scenario: One Concept Set

```
Session: [chronic pain]

User: "Remove fibromyalgia"
System: ✅ Automatically uses chronic pain concept set
```

### Scenario: Multiple Concept Sets

```
Session: [diabetes, hypertension]

User: "Remove code E11.9"
System: ⚠️ Clarification needed

Response:
"I found 2 concept sets in this session:
1. diabetes
2. hypertension

Please specify which one you'd like to modify by mentioning 
the condition name, or say 'the most recent one'."
```

### Clarification Options

**Option 1: Mention condition name**
```
User: "Remove E11.9 from the diabetes concept set"
System: ✅ Applies to diabetes concept set
```

**Option 2: Say "most recent"**
```
User: "Remove code E11.9 from the most recent one"
System: ✅ Applies to most recent concept set (hypertension)
```

**Option 3: Say "latest"**
```
User: "Remove code E11.9 from the latest"
System: ✅ Applies to most recent concept set
```

## Detection Logic

### Follow-Up Patterns Detected

The system detects these keywords/phrases:

```python
followup_patterns = [
    'remove', 'exclude', 'filter out', 'hide', 'delete',
    'add column', 'show column', 'include column', 'add field',
    'only show', 'just show', 'only include', 'show only',
    'without', 'except', 'excluding',
    'modify', 'change', 'update', 'edit',
    'from that table', 'from the table', 'from table',
    'from that', 'from the concept set', 'from concept set'
]
```

### Identification Logic

1. **One concept set:** Auto-selects it
2. **Multiple concept sets:**
   - Checks for "most recent", "latest", "last one"
   - Checks if query mentions condition name (e.g., "diabetes")
   - If ambiguous, asks for clarification

## Storage

### In-Memory Cache Structure

```python
concept_set_cache = {
    'session_id_123': [
        {
            'name': 'chronic pain',
            'raw_data': 'Code: M79.3, Label: Fibromyalgia...',
            'formatted': '| ICD Code | Description | SNOMED |...',
            'query': 'Create chronic pain concept set...',
            'timestamp': 1699382400.0
        },
        {
            'name': 'diabetes',
            'raw_data': 'Code: E11, Label: Type 2 diabetes...',
            'formatted': '| ICD Code | Description |...',
            'query': 'Create diabetes concept set...',
            'timestamp': 1699382500.0
        }
    ]
}
```

### Data Stored Per Concept Set

- **name**: Primary condition (e.g., "chronic pain")
- **raw_data**: Extracted data from ConceptSetExtractorAgent (all fields)
- **formatted**: Final formatted table shown to user
- **query**: Original user query
- **timestamp**: When created (for sorting)

### Storage Duration

- **Lifetime:** Duration of application session
- **Scope:** Per chat session (isolated)
- **Cleanup:** Lost on app restart (in-memory only)

## Example Session Flow

### Complete Example

```
User: "Create chronic pain concept set with ICD and SNOMED"

System: [Returns table with 20 codes including fibromyalgia, arthritis, etc.]

Log:
[MasterAgent] 💾 Stored concept set 'chronic pain' in cache (total: 1)

---

User: "Remove fibromyalgia codes from that table"

System: 
[MasterAgent] Concept set follow-up detected
[MasterAgent] 📋 Using only available concept set: 'chronic pain'
[MasterAgent] 🔧 Processing follow-up for concept set 'chronic pain'

Returns: [Modified table without fibromyalgia codes]

---

User: "Create diabetes concept set"

System: [Returns diabetes table]

Log:
[MasterAgent] 💾 Stored concept set 'diabetes' in cache (total: 2)

---

User: "Remove code E11.9"

System:
[MasterAgent] ⚠️ Ambiguous: 2 concept sets available, none explicitly mentioned

Returns:
"I found 2 concept sets in this session:
1. chronic pain
2. diabetes

Please specify which one you'd like to modify..."

---

User: "Remove E11.9 from the diabetes one"

System:
[MasterAgent] 📋 Identified target concept set: 'diabetes'
[MasterAgent] 🔧 Processing follow-up for concept set 'diabetes'

Returns: [Diabetes table without E11.9]
```

## Chat Agent Instruction

When a follow-up is detected, the chat agent receives:

```
The user previously created a concept set and now wants to modify it.

Original Query: Create chronic pain concept set with ICD and SNOMED

Current Concept Set Data:
Code: M79.3, Label: Fibromyalgia, Score: 0.0320, OHDSI: {...}, SAB: ICD10CM
Code: M79.1, Label: Myalgia, Score: 0.0315, OHDSI: {...}, SAB: ICD10CM
...

User's Modification Request: Remove fibromyalgia codes

INSTRUCTIONS:
1. Parse the raw data to understand all available codes
2. Apply the user's modification (remove codes, add columns, filter, etc.)
3. Rebuild the table with the modifications
4. Keep the same format (markdown table) unless user requests otherwise
5. If removing codes, filter them out completely
6. If adding columns, extract that data from the raw fields
7. Return ONLY the modified table, no extra explanation unless there's an issue

Generate the modified concept set table:
```

## Benefits

### 1. No Re-Searching
- Original search results are cached
- Modifications use cached data
- Faster response time (no Azure AI Search calls)

### 2. Iterative Refinement
```
Create → Remove codes → Add column → Filter → Perfect!
```

### 3. Natural Language
```
❌ Complex: "Filter data where CODE NOT LIKE 'E11%'"
✅ Simple: "Remove type 2 diabetes codes"
```

### 4. Session Awareness
- Multiple concept sets per session
- Clarification when ambiguous
- Sorted by recency

## Limitations

### 1. In-Memory Only
- Lost on app restart
- Not persisted to disk
- Future: Could add session storage

### 2. Session-Scoped
- Each chat has its own cache
- Can't access concept sets from other chats
- Feature: Isolation prevents confusion

### 3. Modification Constraints
- Can only modify existing data
- Can't add NEW codes (would need new search)
- Can rearrange, filter, format existing data

## Logging

### Storage
```
[MasterAgent] 💾 Stored concept set 'chronic pain' in cache (total: 1)
```

### Detection
```
[MasterAgent] Concept set follow-up detected
```

### Identification
```
[MasterAgent] 📋 Using only available concept set: 'chronic pain'
[MasterAgent] 📋 Identified target concept set: 'diabetes'
[MasterAgent] ⚠️ Ambiguous: 2 concept sets available, none explicitly mentioned
```

### Processing
```
[MasterAgent] 🔧 Processing follow-up for concept set 'diabetes'
```

## Testing

### Test Script

```bash
cd /Users/josephbalsamo/Development/Work/pcornet
source .venv/bin/activate
python test_concept_set_followup.py
```

### Manual Testing in App

```bash
./run_streamlit.sh
```

**Test Case 1: Single Concept Set**
1. "Create chronic pain concept set"
2. "Remove fibromyalgia codes from that table"
3. ✅ Should return modified table

**Test Case 2: Multiple Concept Sets**
1. "Create diabetes concept set"
2. "Create hypertension concept set"
3. "Remove code E11.9"
4. ✅ Should ask for clarification
5. "From the diabetes one"
6. ✅ Should return modified diabetes table

**Test Case 3: Most Recent**
1. "Create diabetes concept set"
2. "Create hypertension concept set"
3. "Remove code I10 from the most recent one"
4. ✅ Should modify hypertension (most recent)

## Summary

✅ **Follow-up queries work** - Modify concept sets without re-searching  
✅ **Natural language** - "Remove fibromyalgia" instead of complex filters  
✅ **Multiple concept sets** - Handles disambiguation  
✅ **Clarification logic** - Asks when ambiguous  
✅ **Fast** - No new searches, uses cached data  
✅ **Session-aware** - Each chat has isolated cache  

The feature enables iterative refinement of concept sets through conversational follow-ups, making the workflow much more efficient!
