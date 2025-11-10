# Retry Logic Fix - Complete Coverage

## Problem

After adding rate limit retry logic, the app **still failed** with rate limit errors:

```
Error formatting the concept set: Error code: 429 - {'error': {'code': 'RateLimitReached'...
```

## Root Cause

The retry logic was **only applied to concept set follow-up modifications**, not to the **initial concept set creation workflow**.

### Where Retry Logic Was Missing

1. ❌ **Concept set classification** (`_is_concept_set_query`)
2. ❌ **Query expansion** (`_extract_and_expand_medical_query`)
3. ❌ **Concept set formatting** (`chat_agent.format_concept_set`) ← **Primary cause of error**
4. ❌ **Fallback extraction** (error recovery)
5. ✅ **Follow-up modifications** (already had retry) ← Only this had it

## The Fix

Added `invoke_llm_with_retry()` wrapper to **all LLM calls** in the concept set workflow.

### Files Modified

#### 1. `modules/agents/chat_agent.py` (Lines 202-219)
**What:** Concept set formatting (main error source)

**Before:**
```python
response = self.llm.invoke(messages)  # No retry - fails immediately on 429
return response.content
```

**After:**
```python
from ..config import invoke_llm_with_retry

response = invoke_llm_with_retry(
    lambda: self.llm.invoke(messages),
    max_retries=3,
    initial_delay=10
)
return response.content
```

**Impact:** Retries on rate limit with 10s, 20s, 40s delays

---

#### 2. `modules/master_agent.py` - Classification (Lines 121-133)
**What:** Checking if query is about concept sets

**Before:**
```python
response = self.client.chat.completions.create(...)  # No retry
```

**After:**
```python
from modules.config import invoke_llm_with_retry

response = invoke_llm_with_retry(
    lambda: self.client.chat.completions.create(...),
    max_retries=3,
    initial_delay=10
)
```

**Impact:** Classification step now retries on rate limit

---

#### 3. `modules/master_agent.py` - Query Expansion (Lines 836-848)
**What:** Expanding medical terms (e.g., "diabetes" → "diabetes OR diabetic OR DM")

**Before:**
```python
response = self.client.chat.completions.create(...)  # No retry
```

**After:**
```python
from modules.config import invoke_llm_with_retry

response = invoke_llm_with_retry(
    lambda: self.client.chat.completions.create(...),
    max_retries=3,
    initial_delay=10
)
```

**Impact:** Query expansion now retries on rate limit

---

#### 4. `modules/master_agent.py` - Fallback Extraction (Lines 873-884)
**What:** Simple extraction if expansion fails

**Before:**
```python
response = self.client.chat.completions.create(...)  # No retry
```

**After:**
```python
from modules.config import invoke_llm_with_retry

response = invoke_llm_with_retry(
    lambda: self.client.chat.completions.create(...),
    max_retries=2,  # Fewer retries for fallback
    initial_delay=10
)
```

**Impact:** Even fallback paths now retry

---

## Complete Concept Set Workflow (After Fix)

```
User: "Create diabetes concept set"
    ↓
1. Classification (✅ with retry)
   - Determines if query is about concept sets
   - LLM call: 5 tokens
   - Retries: 3 attempts, 10s/20s/40s delays
    ↓
2. Query Expansion (✅ with retry)
   - "diabetes" → "diabetes OR diabetic OR DM OR type 2 diabetes..."
   - LLM call: ~150 tokens
   - Retries: 3 attempts, 10s/20s/40s delays
    ↓
3. ICD Search
   - Azure AI Search (not LLM, no retry needed)
    ↓
4. Extraction
   - Parses search results (no LLM call)
    ↓
5. Formatting (✅ with retry) ← **This was causing the error**
   - Creates final table
   - LLM call: up to CONCEPT_SET_MAX_TOKENS (default 8000)
   - Retries: 3 attempts, 10s/20s/40s delays
    ↓
✅ Final Response
```

## Retry Behavior

### On First Rate Limit Hit
```
Attempt 1: ❌ Rate limit (429 error)
Wait: 10 seconds
Attempt 2: Try again
  - If success: ✅ Return result
  - If 429: Wait 20 seconds
Attempt 3: Try again
  - If success: ✅ Return result
  - If 429: Wait 40 seconds
Attempt 4: Final try
  - If success: ✅ Return result
  - If 429: ❌ Show error to user

Total wait time: Up to 70 seconds (10 + 20 + 40)
```

### What User Sees

**Before (No Retry):**
```
User: "Create diabetes concept set"
System: ❌ Error formatting the concept set: Error code: 429...
         [Immediate failure]
```

**After (With Retry):**
```
User: "Create diabetes concept set"
System: [Processing...]
        ⚠️ Rate limit hit, retrying in 10s (attempt 1/3)
        [10 seconds pass]
        ⚠️ Rate limit hit, retrying in 20s (attempt 2/3)
        [20 seconds pass]
        ✅ [Returns complete concept set table]
```

**Or if still rate limited:**
```
User: "Create diabetes concept set"
System: [Processing...]
        ⚠️ Rate limit hit, retrying in 10s (attempt 1/3)
        ⚠️ Rate limit hit, retrying in 20s (attempt 2/3)
        ⚠️ Rate limit hit, retrying in 40s (attempt 3/3)
        ❌ Rate limit exceeded after 3 attempts
        
        Error: Your requests have exceeded the token rate limit...
        Please try again in a moment.
```

## Why It's Better Now

### Before
- **Single point of failure:** Any rate limit = immediate error
- **No recovery:** User had to manually retry
- **Bad UX:** Cryptic error messages
- **Wasted work:** Partial workflow results discarded

### After
- **Resilient:** Automatic retry on transient errors
- **Self-healing:** Often succeeds on retry
- **Better UX:** User sees retry progress
- **Preserves work:** Retries same request, not full workflow

## Retry Delay Strategy

### Why 10s, 20s, 40s?

S0 tier error says: **"Please retry after 60 seconds"**

Our retry pattern:
- Attempt 1 → 2: Wait 10s (cumulative: 10s)
- Attempt 2 → 3: Wait 20s (cumulative: 30s)
- Attempt 3 → 4: Wait 40s (cumulative: 70s)

**Total: 70 seconds across all retries** ≥ 60 second requirement ✅

This gives the rate limit time to reset while still being responsive.

### Alternative for Very Low Quotas

If you have **extremely** low quotas, increase delays:

```python
# In modules/config.py, line 415:
def invoke_llm_with_retry(llm_callable, max_retries=3, initial_delay=15):
    # 15s, 30s, 60s = 105s total
```

Or reduce retries:
```python
def invoke_llm_with_retry(llm_callable, max_retries=2, initial_delay=30):
    # 30s, 60s = 90s total
```

## Still Getting Rate Limits?

If you're still hitting rate limits after retries, you need to **reduce token usage**:

### Option 1: Lower Token Limits (Fastest)

Edit `.env`:
```bash
AGENT_MAX_TOKENS=1000              # Down from 2000
CONCEPT_SET_MAX_TOKENS=2000        # Down from 8000
```

### Option 2: Disable Query Expansion

This removes one LLM call from the workflow:

Edit `modules/master_agent.py`:
```python
def _concept_set_workflow(self, state: MasterAgentState) -> str:
    # Step 0: Skip expansion for S0 tier
    # expanded_query = self._extract_and_expand_medical_query(state["user_input"])
    expanded_query = state["user_input"]  # Use query as-is
```

### Option 3: Upgrade to S1 Tier

**Recommended for production:**
- 10x higher rate limits
- ~$10-50/month
- Much better experience
- Visit: https://aka.ms/oai/quotaincrease

## Testing

### Test 1: Simple Concept Set
```
Query: "Create diabetes concept set"
Expected:
- May see 1-2 retry warnings
- Should eventually succeed (within 70 seconds)
- Returns complete table
```

### Test 2: Multiple Queries
```
Query 1: "Create diabetes concept set"
Wait for completion
Query 2: "Create hypertension concept set"

Expected:
- Each may retry independently
- Both eventually succeed
- Total time may be longer due to accumulated rate limits
```

### Test 3: Follow-up Modification
```
Query 1: "Create diabetes concept set"
Query 2: "Remove E11.65"

Expected:
- Initial query may retry
- Follow-up uses cached data (no new LLM calls except formatting)
- Follow-up should be faster
```

## Logging

Watch for these in your logs:

```bash
# Success path
[INFO] Concept set classification for '...': true
[INFO] 🔍 Expanded to 5 related terms: diabetes, diabetic, DM, ...
[INFO] ✅ Generated modified table (2350 chars)

# Retry path
[WARNING] ⚠️ Rate limit hit, retrying in 10s (attempt 1/3)
[WARNING] ⚠️ Rate limit hit, retrying in 20s (attempt 2/3)
[INFO] ✅ Generated modified table (2350 chars)

# Failure path
[WARNING] ⚠️ Rate limit hit, retrying in 10s (attempt 1/3)
[WARNING] ⚠️ Rate limit hit, retrying in 20s (attempt 2/3)
[WARNING] ⚠️ Rate limit hit, retrying in 40s (attempt 3/3)
[ERROR] ❌ Rate limit exceeded after 3 attempts
```

## Summary

### What Was Fixed
✅ **chat_agent.format_concept_set** - Main error source  
✅ **master_agent._is_concept_set_query** - Classification  
✅ **master_agent._extract_and_expand_medical_query** - Expansion  
✅ **master_agent fallback extraction** - Error recovery  

### Result
- **All LLM calls** in concept set workflow now have retry logic
- **Automatic recovery** from transient rate limits
- **Better user experience** with retry progress messages
- **Higher success rate** on S0 tier

### Deployment
1. Pull latest code on your server
2. Restart the app
3. Test with concept set query
4. Monitor logs for retry behavior

The app should now **automatically retry** on rate limits instead of immediately failing! 🎉
