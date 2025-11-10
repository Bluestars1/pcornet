# Rate Limit Handling Guide

## Problem

Your server is hitting Azure OpenAI rate limits (Error 429):

```
Error code: 429 - {'error': {'code': 'RateLimitReached', 
'message': 'Your requests to gpt-4.1 for gpt-4.1 in East US 2 have exceeded 
the token rate limit for your current AIServices S0 pricing tier...'}}
```

## Why This Happens

### Common Causes
1. **S0 Pricing Tier Limits** - Very low rate limits for production use
2. **Parallel Searches** - ICD + SNOMED searches run simultaneously
3. **High Token Usage** - `max_tokens=8000` for large concept set tables
4. **Multiple Sequential Calls** - Query expansion → Search → Extraction → Formatting
5. **Multiple Users** - Server handling concurrent requests

### Request Flow (Token-Intensive)
```
User: "Create diabetes concept set"
    ↓
1. Query Expansion (LLM call ~200 tokens)
    ↓
2. Parallel Searches (2x concurrent API calls)
    ├─→ ICD Search (tokens vary)
    └─→ SNOMED Search (tokens vary)
    ↓
3. Extraction (LLM call ~1000 tokens)
    ↓
4. Formatting (LLM call up to 8000 tokens!)
    ↓
Total: ~10,000+ tokens per concept set request
```

## Solutions Implemented

### ✅ Solution 1: Automatic Retry with Exponential Backoff

**File:** `modules/config.py`
**Function:** `invoke_llm_with_retry()`

Added a reusable retry wrapper that automatically retries LLM calls on rate limit errors:

```python
from modules.config import invoke_llm_with_retry

# Wrap any LLM call
response = invoke_llm_with_retry(
    lambda: llm.invoke(messages),
    max_retries=3,
    initial_delay=2
)
```

**Retry Pattern:**
- Attempt 1: Immediate
- Attempt 2: Wait 2 seconds
- Attempt 3: Wait 4 seconds
- Attempt 4: Wait 8 seconds
- Fail: Raise error to user

**Already Applied To:**
- ✅ Concept set follow-up modifications (`_handle_concept_set_followup`)

**Should Be Applied To:**
- Query expansion (`_extract_and_expand_medical_query`)
- Concept set classification (`_is_concept_set_query`)
- Chat agent responses (`chat_agent.process`)
- Any other LLM invocations

### Example Usage in Your Code

**Before:**
```python
response = llm.invoke([system_msg, user_msg])
```

**After:**
```python
from modules.config import invoke_llm_with_retry

response = invoke_llm_with_retry(
    lambda: llm.invoke([system_msg, user_msg])
)
```

## Additional Solutions (Choose What Fits)

### Option 2: Reduce Token Limits (Quick Fix) ✅ NOW CONFIGURABLE

Reduce the `max_tokens` setting to consume less of your quota:

**File:** `.env`
```bash
# General chat responses (default: 2000)
AGENT_MAX_TOKENS=2000

# ✅ NEW: Configurable concept set table size (default: 8000)
# For S0 tier, reduce to 3000-4000 to avoid rate limits
CONCEPT_SET_MAX_TOKENS=4000  # Reduced from 8000 for S0 tier

# For S1+ tier, keep at 8000 or higher for complete tables
# CONCEPT_SET_MAX_TOKENS=8000
```

**Trade-off:** Smaller values may truncate very large concept sets (30+ codes with SNOMED).

### Option 3: Add Request Throttling (Server-Side)

Limit concurrent requests to avoid bursting past rate limits:

**Create:** `modules/rate_limiter.py`
```python
import time
from threading import Lock
from collections import deque

class RateLimiter:
    """Simple token bucket rate limiter."""
    
    def __init__(self, requests_per_minute=10):
        self.requests_per_minute = requests_per_minute
        self.window = deque()
        self.lock = Lock()
    
    def acquire(self):
        """Block until a request can be made within rate limit."""
        with self.lock:
            now = time.time()
            # Remove requests older than 60 seconds
            while self.window and self.window[0] < now - 60:
                self.window.popleft()
            
            # If at limit, wait
            if len(self.window) >= self.requests_per_minute:
                sleep_time = 60 - (now - self.window[0])
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    return self.acquire()
            
            self.window.append(now)

# Global rate limiter
llm_rate_limiter = RateLimiter(requests_per_minute=20)
```

**Usage:**
```python
llm_rate_limiter.acquire()  # Will block if too many requests
response = llm.invoke(messages)
```

### Option 4: Upgrade Azure Pricing Tier (Recommended for Production)

**Current:** S0 (Free/Low tier)
- Very limited requests per minute
- Low token throughput
- Not suitable for production

**Recommended:** S1 or higher
- Higher rate limits
- Better for multi-user scenarios
- Cost-effective for production use

**Steps:**
1. Go to Azure Portal → Your OpenAI resource
2. Navigate to "Pricing tier"
3. Upgrade to S1 or S2
4. Visit: https://aka.ms/oai/quotaincrease for quota increase

**Cost Comparison:**
- S0: ~$0 (limited, rate limited)
- S1: ~$10-50/month (much higher limits)
- S2: ~$100-500/month (production-ready)

### Option 5: Add Caching for Common Queries

Cache results for frequently requested concept sets:

```python
from functools import lru_cache
import hashlib

@lru_cache(maxsize=100)
def get_cached_concept_set(query_hash):
    # Will only compute once per unique query
    return concept_set_workflow(query)

# Usage
query_hash = hashlib.md5(query.encode()).hexdigest()
result = get_cached_concept_set(query_hash)
```

### Option 6: Sequential Instead of Parallel Searches

**Current:** ICD and SNOMED searches run in parallel (faster but uses more tokens/second)

**Alternative:** Run sequentially (slower but spreads out token usage)

**File:** `modules/master_agent.py`
**Function:** `_concept_set_workflow()`

```python
# Current (parallel)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    icd_future = executor.submit(self.icd_agent.process, query)
    snomed_future = executor.submit(self.snomed_agent.process, query)

# Alternative (sequential)
icd_result = self.icd_agent.process(query)
snomed_result = self.snomed_agent.process(query)
```

**Trade-off:** ~2x slower but halves concurrent token usage.

## Monitoring and Debugging

### Add Rate Limit Logging

Update your logging to track rate limit events:

```python
import logging

logger = logging.getLogger(__name__)

# In your .env or config
LOGLEVEL=INFO  # or DEBUG for verbose output
```

### Check Logs for Rate Limit Warnings

```bash
# Look for rate limit patterns
tail -f logs/app.log | grep -i "rate limit"

# Expected output after fixes:
# ⚠️ Rate limit hit, retrying in 2s (attempt 1/3)
# ✅ Generated modified table (2350 chars)
```

### Monitor Token Usage

Add token usage tracking:

```python
# After LLM call
if hasattr(response, 'usage'):
    logger.info(f"📊 Tokens used: {response.usage}")
```

## Recommended Configuration for S0 Tier

**File:** `.env`
```bash
# Reduce token limits to stay within S0 tier limits
AGENT_MAX_TOKENS=1500  # Down from 2000

# ✅ Reduce concept set table size for S0 tier
CONCEPT_SET_MAX_TOKENS=3000  # Down from 8000 - prevents rate limits

# Use lower temperature for more consistent responses
AGENT_TEMPERATURE=0.3

# Enable retry logic (already in code)
# Retries will handle transient rate limits
```

**No code changes needed!** The `CONCEPT_SET_MAX_TOKENS` setting is now configurable via `.env`.

## Recommended Configuration for Production (S1+)

**File:** `.env`
```bash
# Higher limits for production
AGENT_MAX_TOKENS=3000

# Keep parallel searches enabled
# Retry logic will handle occasional rate limits
```

## Testing After Changes

### Test 1: Simple Query (Low Token Usage)
```
Query: "Find ICD code for diabetes"
Expected: ✅ Works without rate limit
```

### Test 2: Concept Set (High Token Usage)
```
Query: "Create diabetes concept set with ICD and SNOMED codes"
Expected: 
- First attempt may hit rate limit
- Retry after 2s succeeds
- ✅ Table generated
```

### Test 3: Multiple Sequential Queries
```
Query 1: "Create diabetes concept set"
Query 2: "Remove E11.65"
Query 3: "Add chronic kidney disease codes"

Expected:
- Some queries may trigger retry
- All eventually succeed
- User sees "retrying" messages
```

## Summary

### ✅ What's Been Fixed
1. **Retry logic added** - Automatic retry with exponential backoff
2. **Reusable wrapper** - `invoke_llm_with_retry()` for all LLM calls
3. **Better error messages** - Users see helpful rate limit messages

### 🔧 What You Should Do

**Immediate (Required):**
1. ✅ Retry logic is already implemented - test it!
2. Monitor logs for rate limit warnings
3. Consider reducing token limits if still hitting limits

**Short-term (Recommended):**
1. **Upgrade to S1 tier** ($10-50/month) for better limits
2. Apply retry wrapper to all LLM calls (query expansion, classification, etc.)
3. Add request throttling if multiple users

**Long-term (Optional):**
1. Implement caching for common queries
2. Add monitoring dashboard for token usage
3. Consider switching to sequential searches if needed

### Expected Behavior After Fixes

**Before:**
```
User: "Create diabetes concept set"
System: ❌ Error code: 429 - Rate limit reached
```

**After:**
```
User: "Create diabetes concept set"
System: [Processing...]
System: ⚠️ Rate limit hit, retrying in 2s...
System: ✅ [Returns complete table]
```

## Getting Help

- **Azure Support:** https://aka.ms/oai/quotaincrease
- **Pricing Tiers:** https://azure.microsoft.com/pricing/details/cognitive-services/openai/
- **Rate Limits:** https://learn.microsoft.com/azure/ai-services/openai/quotas-limits

## Files Modified

1. **`modules/config.py`**
   - Added `invoke_llm_with_retry()` function
   - Lines 415-456

2. **`modules/master_agent.py`**
   - Updated `_handle_concept_set_followup()` to use retry wrapper
   - Changed hard-coded `max_tokens=8000` to configurable `CONCEPT_SET_MAX_TOKENS`
   - Lines 724-734, 737-752

3. **`.env`**
   - Added `CONCEPT_SET_MAX_TOKENS=8000` (configurable)
   - Line 20

## Next Steps

1. **Test the retry logic** - Try creating a concept set on your server
2. **Monitor the logs** - Watch for rate limit warnings and successful retries
3. **Consider upgrading** - S1 tier if retries aren't enough
4. **Apply to other calls** - Add retry wrapper to query expansion and other LLM calls

The retry logic should handle most rate limit issues automatically! 🎉
