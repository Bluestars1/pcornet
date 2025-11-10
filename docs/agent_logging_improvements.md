# Agent Logging Improvements

## Changes Made

Added agent name prefixes to all INFO-level logs across the concept set workflow for better traceability.

## Before vs After

### Before (Unclear Agent)
```
INFO - Workflow Step 1: Calling IcdAgent
INFO - 📋 State updated: context set (1283599 chars) with ICD data from search
INFO - Workflow Step 3: Calling ConceptSetExtractorAgent
INFO - ✅ Initialized
INFO - 📋 Extracted E11 with 3 additional fields (including OHDSI if present)
INFO - Workflow Step 4: Calling ChatAgent for final formatting
```

### After (Clear Agent Attribution)
```
INFO - [MasterAgent] Workflow Step 1: Calling IcdAgent
INFO - [MasterAgent] 📋 State updated: context set (1283599 chars) with ICD data from search
INFO - [MasterAgent] Workflow Step 3: Calling ConceptSetExtractorAgent
INFO - [ConceptSetExtractorAgent] ✅ Initialized
INFO - [ConceptSetExtractorAgent] 📋 Extracted E11 with 3 additional fields (including OHDSI if present)
INFO - [MasterAgent] Workflow Step 4: Calling ChatAgent for final formatting
```

## Complete Concept Set Workflow Logs

### Full Example Log Output

```
INFO - [MasterAgent] 📋 Agent classification: 'Create diabetes concept set...' → agent_type='snomed'
INFO - [MasterAgent] 📋 State initialized: agent_type='snomed', user_input='Create for me a diabetes concept set...'
INFO - [MasterAgent] Concept set query detected. Starting concept set workflow
INFO - [MasterAgent] 📋 Extracted condition 'diabetes' from query 'Create for me a diabetes concept set showing both icd and sn...'
INFO - [MasterAgent] 🔍 Searching for medical condition: 'diabetes'
INFO - [MasterAgent] Workflow Step 1: Calling IcdAgent
INFO - [IcdAgent] ✅ Initialized (RelationshipSearch will be used per query)
INFO - [IcdAgent] ✅ Initialized with LLM
INFO - [MasterAgent] 📋 State updated: context set (1283599 chars) with ICD data from search
INFO - [MasterAgent] Workflow Step 3: Calling ConceptSetExtractorAgent
INFO - [ConceptSetExtractorAgent] ✅ Initialized
INFO - [ConceptSetExtractorAgent] 📋 Extracted E11 with 3 additional fields (including OHDSI if present)
INFO - [ConceptSetExtractorAgent] 📋 Extracted E10 with 3 additional fields (including OHDSI if present)
INFO - [ConceptSetExtractorAgent] 📋 Extracted E13 with 3 additional fields (including OHDSI if present)
INFO - [MasterAgent] Workflow Step 4: Calling ChatAgent for final formatting
```

## Agent-Specific Log Prefixes

| Agent | Prefix | Purpose |
|-------|--------|---------|
| MasterAgent | `[MasterAgent]` | Workflow orchestration, routing, classification |
| IcdAgent | `[IcdAgent]` | ICD code search and retrieval |
| SnomedAgent | `[SnomedAgent]` | SNOMED CT search and retrieval |
| ChatAgent | `[ChatAgent]` | Conversational responses and formatting |
| ConceptSetExtractorAgent | `[ConceptSetExtractorAgent]` | JSON parsing and field extraction |

## Benefits

### 1. **Troubleshooting**
Easy to filter logs by agent:
```bash
# See only MasterAgent workflow logs
grep "\[MasterAgent\]" app.log

# See only data extraction logs
grep "\[ConceptSetExtractorAgent\]" app.log

# See ICD search activity
grep "\[IcdAgent\]" app.log
```

### 2. **Performance Analysis**
Identify which agent is slow:
```bash
# Add timestamps to see duration
grep "\[MasterAgent\] Workflow Step" app.log
2025-11-07 11:04:49 - [MasterAgent] Workflow Step 1: Calling IcdAgent
2025-11-07 11:04:50 - [MasterAgent] Workflow Step 3: Calling ConceptSetExtractorAgent  # 1 second
2025-11-07 11:04:50 - [MasterAgent] Workflow Step 4: Calling ChatAgent for final formatting  # <1 second
```

### 3. **Error Tracing**
Quickly identify which agent failed:
```bash
grep "ERROR" app.log
ERROR - [IcdAgent] Error finding SNOMED for E11: Connection timeout
ERROR - [ChatAgent] Error formatting concept set: Rate limit exceeded
```

### 4. **Session Filtering**
Track semantic filtering decisions:
```bash
grep "Semantic filtering" app.log
INFO - [MasterAgent] 🔍 Semantic filtering: 10 total → 5 relevant (threshold: 0.3)
INFO - [MasterAgent] 📋 Retrieved 5/10 relevant codes for query 'diabetes'
```

## Log Level Recommendations

### Production (.env)
```bash
LOG_LEVEL=INFO
```
Shows agent workflow steps and important events only.

### Development
```bash
LOG_LEVEL=DEBUG
```
Shows detailed field extraction, available fields, and parsing details:
```
DEBUG - [ConceptSetExtractorAgent] 📋 Extracting E11: fields available = ['CODE', 'STR', 'OHDSI', 'SAB', 'id']
DEBUG - [ConceptSetExtractorAgent] 📋 Added field OHDSI for E11
DEBUG - [ConceptSetExtractorAgent] 📋 Added field SAB for E11
```

### Troubleshooting Specific Agent
```bash
# See all MasterAgent logs including DEBUG
grep "\[MasterAgent\]" app.log | grep -E "INFO|DEBUG|WARNING|ERROR"
```

## Files Modified

1. **`modules/master_agent.py`**
   - All `logger.info()` calls now include `[MasterAgent]` prefix
   - Affects: classification, workflow orchestration, filtering logs

2. **`modules/agents/concept_set_extractor_agent.py`**
   - All log calls now include `[ConceptSetExtractorAgent]` prefix
   - Affects: initialization, extraction, error handling

3. **`modules/agents/chat_agent.py`**
   - Error logs now include `[ChatAgent]` prefix
   - Affects: concept set formatting errors

4. **`modules/agents/icd_agent.py`**
   - Key logs now include `[IcdAgent]` prefix
   - Affects: initialization, search, SNOMED retrieval, session storage

## Example Use Cases

### Use Case 1: Debug Empty Results

**Problem:** User gets "No concepts found"

**Solution:**
```bash
grep "\[MasterAgent\]" app.log | tail -20
```

Look for:
```
[MasterAgent] 📋 Extracted condition 'xyz' from query '...'
[MasterAgent] 📋 State updated: context set (2 chars) with ICD data from search  ← Problem!
```

If context is only 2 chars (`[]`), the ICD search returned nothing. Check extracted condition.

### Use Case 2: Track Semantic Filtering

**Problem:** User asks "Why isn't code X showing?"

**Solution:**
```bash
grep "Semantic filtering\|similarity=" app.log
```

Output:
```
[MasterAgent] 🔍 Semantic filtering: 10 total → 3 relevant (threshold: 0.3)
✓ E11: similarity=0.820 (relevant)
✗ Z51.A: similarity=0.154 (filtered out)  ← Found it!
```

### Use Case 3: Monitor Performance

**Problem:** Queries feel slow

**Solution:**
```bash
grep "\[MasterAgent\] Workflow Step" app.log | tail -20
```

Check timestamps between steps to identify bottlenecks.

## Testing

To see the new logs in action:

```bash
# Start app
./run_streamlit.sh

# In another terminal, tail logs
tail -f app.log | grep "\[.*Agent\]"

# Submit query in UI:
"Create diabetes concept set with ICD and SNOMED codes"

# Watch the logs flow by with agent names!
```

## Summary

✅ **All workflow logs now show agent names**  
✅ **Easy filtering by agent**  
✅ **Better troubleshooting**  
✅ **Performance tracking enabled**  
✅ **Error tracing simplified**  

The logging improvements make it much easier to understand what's happening during concept set creation and quickly identify issues.
