# Max Tokens Configuration - Now Fully Configurable

## Summary

**Previously:** The `max_tokens=8000` for concept set tables was **hard-coded** in `master_agent.py`.

**Now:** It's **configurable** via `.env` as `CONCEPT_SET_MAX_TOKENS`.

## What Changed

### 1. Added Environment Variable
**File:** `.env` (line 20)
```bash
CONCEPT_SET_MAX_TOKENS=8000  # For large concept set tables
```

### 2. Updated Code to Use Variable
**File:** `modules/master_agent.py` (lines 724-734)
```python
# Before (hard-coded):
max_tokens=8000,  # Much higher limit for large tables

# After (configurable):
concept_set_max_tokens = int(os.getenv("CONCEPT_SET_MAX_TOKENS", "8000"))
max_tokens=concept_set_max_tokens,  # Configurable via .env
```

### 3. Updated Documentation
**File:** `docs/RATE_LIMIT_HANDLING.md`
- Added configuration examples for S0 vs S1+ tiers
- Explained trade-offs for different values

## Hard-Coded vs Configurable Values

### ✅ Now Configurable
| Use Case | Environment Variable | Default | File |
|----------|---------------------|---------|------|
| General chat | `AGENT_MAX_TOKENS` | 2000 | `.env` |
| **Concept set tables** | **`CONCEPT_SET_MAX_TOKENS`** | **8000** | **`.env`** |
| Temperature | `AGENT_TEMPERATURE` | 0.3 | `.env` |

### ⚠️ Still Hard-Coded (Small Values)
| Use Case | Value | Location | Reason |
|----------|-------|----------|--------|
| Concept set classification | 5 tokens | `master_agent.py:125` | Simple yes/no |
| Medical condition extraction | 20 tokens | `master_agent.py:789` | Single term |
| Query expansion | 150 tokens | `master_agent.py:836` | Short phrase list |
| Fact extraction | 500 tokens | `memory/semantic_memory.py:96` | Brief facts |

**Note:** These small values don't need configuration - they're intentionally brief for specific tasks.

## Recommended Settings by Tier

### S0 Tier (Free/Low)
**Problem:** Very limited rate limits, easily exceeded

**Solution:** Reduce token usage
```bash
# .env
AGENT_MAX_TOKENS=1500
CONCEPT_SET_MAX_TOKENS=3000  # Reduced from 8000
AGENT_TEMPERATURE=0.3
```

**Expected:** Smaller tables but fewer rate limit errors

### S1 Tier (Production)
**No changes needed** - Default settings work well
```bash
# .env
AGENT_MAX_TOKENS=2000
CONCEPT_SET_MAX_TOKENS=8000  # Full tables
AGENT_TEMPERATURE=0.3
```

### S2+ Tier (High-Volume)
**Can increase for better quality**
```bash
# .env
AGENT_MAX_TOKENS=3000
CONCEPT_SET_MAX_TOKENS=10000  # Even larger tables
AGENT_TEMPERATURE=0.3
```

## How to Adjust for Your Server

### Step 1: Identify Your Tier
Check Azure Portal → Your OpenAI Resource → Pricing Tier

### Step 2: Update `.env`
```bash
# For S0 tier (recommended to avoid rate limits)
CONCEPT_SET_MAX_TOKENS=3000

# For S1+ tier (keep full functionality)
CONCEPT_SET_MAX_TOKENS=8000
```

### Step 3: Restart Server
```bash
# Kill existing server
pkill -f streamlit

# Start with new config
./run_streamlit.sh
```

### Step 4: Test
Try creating a concept set:
```
Query: "Create diabetes concept set"
Expected: Full table without rate limit errors
```

## Token Usage Examples

### Example 1: Small Concept Set (10 codes)
```
CONCEPT_SET_MAX_TOKENS=3000 ✅ Plenty of room
Response: ~1,500 tokens (table + formatting)
```

### Example 2: Medium Concept Set (25 codes)
```
CONCEPT_SET_MAX_TOKENS=3000 ⚠️ May truncate
Response: ~3,200 tokens (exceeds limit)
Result: Table may be incomplete

CONCEPT_SET_MAX_TOKENS=5000 ✅ Better
Response: ~3,200 tokens (fits)
Result: Complete table
```

### Example 3: Large Concept Set (50 codes)
```
CONCEPT_SET_MAX_TOKENS=3000 ❌ Will truncate
Response: ~6,500 tokens (exceeds limit)

CONCEPT_SET_MAX_TOKENS=8000 ✅ Full table
Response: ~6,500 tokens (fits)
Result: Complete table
```

## Trade-offs

### Higher Values (6000-10000)
**Pros:**
- ✅ Complete tables even for large concept sets
- ✅ Better user experience (no truncation)
- ✅ More SNOMED codes included

**Cons:**
- ❌ Higher token usage per request
- ❌ More likely to hit rate limits on S0 tier
- ❌ Slower response times
- ❌ Higher API costs

### Lower Values (3000-4000)
**Pros:**
- ✅ Fewer rate limit errors
- ✅ Faster responses
- ✅ Lower API costs
- ✅ Works well on S0 tier

**Cons:**
- ❌ Large tables may be truncated
- ❌ May need multiple queries for big concept sets
- ❌ Some SNOMED codes may be omitted

## Monitoring Token Usage

### Add Logging
```python
# After LLM response
logger.info(f"Tokens used: {len(response)} chars, ~{len(response)//4} tokens")
```

### Check Logs
```bash
tail -f logs/app.log | grep "Tokens used"
```

### Watch for Truncation
Look for responses that end abruptly or have incomplete tables.

## Best Practices

1. **Start Conservative** - Use 3000-4000 on S0 tier
2. **Monitor Usage** - Watch logs for truncation
3. **Adjust Up** - Increase if tables are incomplete
4. **Upgrade Tier** - If constantly hitting limits, upgrade to S1
5. **Use Retry Logic** - Already implemented for rate limits

## Files Modified

1. **`.env`** (line 20)
   - Added `CONCEPT_SET_MAX_TOKENS=8000`

2. **`modules/master_agent.py`** (lines 724-734)
   - Reads `CONCEPT_SET_MAX_TOKENS` from environment
   - Falls back to 8000 if not set

3. **`docs/RATE_LIMIT_HANDLING.md`**
   - Updated recommendations for different tiers
   - Added configuration examples

## Next Steps

### For Your S0 Server (Immediate)
```bash
# Edit .env
nano .env

# Change this line:
CONCEPT_SET_MAX_TOKENS=3000  # Reduced from 8000

# Restart
./run_streamlit.sh
```

### Monitor Results
1. Try creating concept sets
2. Check if tables are complete
3. Watch for rate limit errors
4. Adjust up/down as needed

### Long-term (Recommended)
**Upgrade to S1 tier** for production use:
- Better rate limits
- Can use full 8000 tokens
- Better user experience
- ~$10-50/month

## Summary

✅ **Problem Solved:** `max_tokens` is no longer hard-coded for concept sets  
✅ **Configurable:** Use `CONCEPT_SET_MAX_TOKENS` in `.env`  
✅ **Flexible:** Adjust based on your Azure tier  
✅ **Backward Compatible:** Defaults to 8000 if not set  

You can now tune your token usage to match your Azure OpenAI tier! 🎉
