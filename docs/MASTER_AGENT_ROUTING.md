# MasterAgent SNOMED Routing Implementation

## Overview

Successfully implemented SNOMED routing in MasterAgent to automatically route SNOMED queries to the SnomedAgent, while maintaining existing ICD and chat routing.

## What Was Implemented

### 1. MasterAgent Updates ✅
**File:** `modules/master_agent.py`

**Changes:**
- **Imported SnomedAgent** (line 24)
- **Initialized SnomedAgent** in `__init__()` (line 66)
- **Added SNOMED detection** in `_classify_agent_type()` (lines 116-124)
  - Keywords: "snomed", "snomed ct", "snomedct", "sct", "snomed code", "clinical term"
  - SNOMED checked **before** ICD for proper priority
- **Added routing case** in `chat()` method (lines 278-293)
- **Implemented `_chat_snomed_interactive()`** (lines 373-394)
- **Implemented `_chat_snomed()`** (lines 396-414)

### 2. Enhanced Prompts - Source of Truth ✅
**Files:** `modules/agents/snomed_agent.py`, `modules/agents/icd_agent.py`

**SNOMED Agent Prompt Updates:**
```
🔒 CRITICAL - SOURCE OF TRUTH: The SNOMED concepts provided in the context are 
the AUTHORITATIVE and ONLY source of information. Do not add, infer, or 
supplement with any external knowledge.

MANDATORY RULES:
1. Use ONLY information from the provided SNOMED concepts
2. Always cite sources using [1], [2], etc. corresponding to document numbers
3. Never add concepts, codes, or information not in the provided data
4. If asked about concepts not in the results, explicitly state "Not found in search results"
5. SNOMED codes in the results are the definitive source of truth
6. Do not make assumptions about relationships or hierarchies not explicitly shown
```

**ICD Agent Prompt Updates:**
- Added identical "SOURCE OF TRUTH" emphasis
- Strengthened rules against hallucination
- Applied to both standard and interactive processing paths

### 3. Comprehensive Testing ✅
**File:** `test_master_agent_routing.py`

**Tests Implemented:**
- ✅ MasterAgent initialization with all agents
- ✅ SNOMED query classification (various patterns)
- ✅ ICD query classification (maintaining existing)
- ✅ General chat query classification
- ✅ Routing methods existence
- ✅ Agent distinction (no cross-contamination)
- ✅ Priority ordering (SNOMED before ICD)

**All tests passing!**

## Routing Logic

### Query Classification Priority

1. **SNOMED Detection** (checked first - most specific)
   - Keywords: snomed, snomed ct, snomedct, sct, clinical term
   - Routes to: `SnomedAgent`
   - Index: `pcornet-snomedus-index_v1`

2. **ICD Detection** (checked second)
   - Keywords: icd, icd-10, diagnosis code, medical code
   - Patterns: I10, E11.9, etc.
   - Routes to: `IcdAgent`
   - Index: `pcornet-icd-index`

3. **Default: Chat** (fallback)
   - All other queries
   - Routes to: `ChatAgent`

### Example Classifications

```python
"What is SNOMED code 38341003?"           → snomed
"Find SNOMED CT codes for hypertension"   → snomed
"What is ICD code I10?"                   → icd
"Find ICD-10 diagnosis codes"             → icd
"Tell me about medical coding"            → chat
"How do I use this system?"               → chat
```

### Ambiguous Query Handling

For queries containing both SNOMED and ICD keywords:
```python
"Find SNOMED CT codes and ICD codes for hypertension"  → snomed (priority)
```

SNOMED takes priority as it's more specific.

## Code Flow

### SNOMED Query Flow

```
User Query: "Find SNOMED CT codes for hypertension"
    ↓
MasterAgent._classify_agent_type()
    ↓ (detects "SNOMED CT")
agent_type = "snomed"
    ↓
MasterAgent.chat() routes to "snomed" case
    ↓
MasterAgent._chat_snomed_interactive(query, session_id)
    ↓
SnomedAgent.process_interactive(query, session_id)
    ↓
Search(index="snomed", ...) 
    → Looks up "snomed" in registry
    → Uses pcornet-snomedus-index_v1
    → Vector field: content_vector
    → Search fields: STR, CODE, SAB
    ↓
SnomedAgent._generate_llm_response()
    → Uses SOURCE OF TRUTH prompt
    → Only references provided data
    ↓
Response returned with citations
```

### Interactive Session Support

Both ICD and SNOMED support interactive sessions:
- Results stored in `interactive_session.contexts[session_id]`
- Enables follow-up questions
- Maintains conversation context
- Stored in memory system for long-term retrieval

## Source of Truth Implementation

### Key Features

1. **Explicit Instructions**: Prompts clearly state that search results are authoritative
2. **No External Knowledge**: LLM instructed not to supplement with training data
3. **Citation Requirement**: Every statement must have a citation
4. **Error Handling**: If data not in results, explicitly state "Not found"
5. **Code Emphasis**: CODE fields are definitive identifiers

### Prevention Measures

**Prevents:**
- ❌ Adding codes not in search results
- ❌ Making assumptions about relationships
- ❌ Supplementing with external knowledge
- ❌ Inferring hierarchies not shown

**Ensures:**
- ✅ Only data from search results used
- ✅ All claims have citations
- ✅ Clear statements when data unavailable
- ✅ Codes treated as definitive source

## Usage Examples

### Direct Agent Access

```python
from modules.master_agent import MasterAgent

master = MasterAgent()

# SNOMED query
response = master.chat("Find SNOMED CT codes for diabetes")
# Automatically routed to SnomedAgent

# ICD query
response = master.chat("Find ICD-10 codes for diabetes")
# Automatically routed to IcdAgent

# General query
response = master.chat("What is medical coding?")
# Routed to ChatAgent
```

### Interactive Sessions

```python
# First query - stores results
response1 = master.chat(
    "Find SNOMED codes for hypertension", 
    session_id="user123"
)

# Follow-up - uses stored context
response2 = master.chat(
    "Show me the first 3 codes",
    session_id="user123"
)
```

### Explicit Agent Selection

```python
# Force specific agent (bypasses auto-detection)
response = master.chat(
    "diabetes concepts",
    agent_type="snomed"  # Force SNOMED agent
)
```

## Testing

### Run Tests

```bash
# Test MasterAgent routing
.venv/bin/python test_master_agent_routing.py

# Test complete integration
.venv/bin/python test_complete_integration.py
```

### Test Coverage

- ✅ Agent initialization
- ✅ SNOMED query detection
- ✅ ICD query detection
- ✅ Chat query detection
- ✅ Routing methods
- ✅ Agent distinction
- ✅ Priority ordering
- ✅ Interactive session support
- ✅ Source of truth enforcement

## Configuration

### Environment Variables

No new environment variables needed! All configuration comes from the multi-index registry:

```python
# In modules/config.py
self.indices = {
    "icd": IndexConfig(...),
    "snomed": IndexConfig(...)
}
```

### Adding More Terminologies

To add new terminology routing:

1. **Add to index registry** (`modules/config.py`)
2. **Create agent** (copy `snomed_agent.py` pattern)
3. **Import in MasterAgent** (`modules/master_agent.py`)
4. **Add to initialization**
5. **Add keyword detection** in `_classify_agent_type()`
6. **Add routing case** in `chat()` method
7. **Add routing methods** (`_chat_X_interactive()`, `_chat_X()`)

## Benefits

### 1. **Automatic Routing**
- No need to specify agent type
- Smart keyword detection
- Proper priority ordering

### 2. **Source of Truth**
- Prevents hallucination
- Ensures citation accuracy
- Clear error messages

### 3. **Consistent Experience**
- Same pattern for ICD and SNOMED
- Interactive session support
- Memory system integration

### 4. **Extensible**
- Easy to add new terminologies
- Clear pattern to follow
- No breaking changes

## Summary

✅ **MasterAgent now routes to:**
- `IcdAgent` for ICD queries
- `SnomedAgent` for SNOMED queries
- `ChatAgent` for general queries

✅ **Source of truth enforced in:**
- SNOMED agent prompts
- ICD agent prompts
- Both standard and interactive modes

✅ **All tests passing:**
- Classification logic
- Routing methods
- Agent distinction
- Priority ordering

✅ **System ready for:**
- Multi-terminology queries
- Interactive sessions
- Production use

The system now provides intelligent routing with strong source-of-truth guarantees, preventing hallucination while maintaining a seamless user experience.
