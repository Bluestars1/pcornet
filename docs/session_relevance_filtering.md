# Session Relevance Filtering (Azure AI Search Style)

## Overview

The system now filters session data by **semantic relevance** to the current query, similar to how Azure AI Search works. This prevents unrelated codes from appearing in responses.

## Problem Solved

**Before:**
- User searches for "sepsis" → Z51.A stored in session
- User searches for "diabetes" → gets E10, E11, **Z51.A** (unrelated!)
- Session accumulated ALL codes from all searches

**After:**
- User searches for "sepsis" → Z51.A stored in session
- User searches for "diabetes" → gets E10, E11 only
- System filters out Z51.A (similarity: 0.15 < threshold: 0.3)

## How It Works

### 1. Semantic Similarity Calculation

When you ask a question like "create concept set for diabetes":

```python
# System generates embeddings
query_embedding = embed("create concept set for diabetes")
z51a_embedding = embed("Z51.A Encounter for sepsis aftercare")
e11_embedding = embed("E11 Type 2 diabetes mellitus")

# Calculates cosine similarity (0-1 scale)
similarity(query, Z51.A) = 0.15  # ← Filtered out
similarity(query, E11) = 0.82    # ← Included
```

### 2. Threshold-Based Filtering

Only codes with similarity ≥ threshold are included:

```
SESSION_RELEVANCE_THRESHOLD=0.3 (default)

Query: "diabetes concept set"
├─ E10 (Type 1 diabetes): 0.85 ✓ Included
├─ E11 (Type 2 diabetes): 0.82 ✓ Included
├─ E13 (Other diabetes): 0.78 ✓ Included
├─ I10 (Hypertension): 0.22 ✗ Filtered out
└─ Z51.A (Sepsis care): 0.15 ✗ Filtered out
```

### 3. Sorted by Relevance

Results are sorted highest to lowest similarity (most relevant first).

## Configuration

### Environment Variable

Edit `.env` file:

```bash
# Session Memory Settings
SESSION_RELEVANCE_THRESHOLD=0.3
```

### Threshold Guidelines

| Value | Behavior | Use Case |
|-------|----------|----------|
| `0.2` | Very permissive | Include loosely related codes |
| `0.3` | **Default** | Good balance (recommended) |
| `0.4` | Moderate | Stricter filtering |
| `0.5` | Strict | Only highly relevant codes |
| `0.6+` | Very strict | Near-exact matches only |

## Examples

### Example 1: Diabetes Query

**Session contains:**
- E10, E11, E13 (diabetes codes)
- I10, I15 (hypertension codes)
- Z51.A (sepsis aftercare)

**Query:** "Show diabetes codes in table"

**Result (threshold=0.3):**
```
🔍 Semantic filtering: 6 total → 3 relevant (threshold: 0.3)
📋 Retrieved 3/6 relevant codes for query 'Show diabetes codes...'

| Code | Description | Similarity |
|------|-------------|------------|
| E11 | Type 2 diabetes mellitus | 0.82 |
| E10 | Type 1 diabetes mellitus | 0.79 |
| E13 | Other specified diabetes mellitus | 0.76 |
```

### Example 2: Adding Related Codes

**Session contains:**
- E11 (Type 2 diabetes)

**Query:** "Add hypertension codes"

**Result:**
- Searches for hypertension → adds I10, I15
- Next query "show all" displays both diabetes AND hypertension
- Filtering is based on current query context

## Logging

System logs show filtering decisions:

```
🔍 Semantic filtering: 10 total → 5 relevant (threshold: 0.3)
✓ E11: similarity=0.82 (relevant)
✓ E10: similarity=0.79 (relevant)
✗ Z51.A: similarity=0.15 (filtered out)
📋 Retrieved 5/10 relevant codes for query 'diabetes'
```

## Technical Details

### Embedding Model

Uses `all-MiniLM-L6-v2` from sentence-transformers:
- **Dimensions:** 384
- **Speed:** Fast (lazy-loaded on first use)
- **Quality:** Good semantic understanding

### Similarity Metric

Cosine similarity between vectors:
```python
similarity = dot(query_vec, item_vec) / (norm(query_vec) * norm(item_vec))
# Returns: 0.0 (unrelated) to 1.0 (identical)
```

### Searchable Fields

Each item is embedded as:
```python
item_text = f"{code} {description} {additional_fields}"
# Example: "E11 Type 2 diabetes mellitus"
```

## Benefits

✅ **Prevents unrelated codes** from appearing in results  
✅ **Mimics Azure AI Search** semantic behavior  
✅ **Configurable threshold** for different use cases  
✅ **Sorted by relevance** (most relevant first)  
✅ **Graceful fallback** if embedding fails  
✅ **Transparent logging** shows what's filtered  

## Disabling Filtering

To disable filtering (show all session codes):

### Option 1: Set very low threshold
```bash
SESSION_RELEVANCE_THRESHOLD=0.0
```

### Option 2: Clear session before new searches
```
User: "New chat" → Clears all session data
```

### Option 3: Use explicit clear command
```
User: "Clear session and search for diabetes"
```

## Migration Notes

**Backward Compatibility:** ✅ Fully backward compatible
- If query is not provided → returns all items (original behavior)
- If embedding fails → returns all items (safe fallback)
- Existing sessions continue to work without changes

## Performance

- **First query:** 2-3 second delay (loading embedding model)
- **Subsequent queries:** <100ms per 10 items
- **Embedding cached:** Model stays in memory after first load
- **Batch processing:** Multiple items embedded efficiently

## Future Enhancements

Potential improvements:
1. **User-level threshold:** Let users adjust in UI
2. **Query-specific thresholds:** Different thresholds for different query types
3. **Hybrid filtering:** Combine semantic + keyword matching
4. **Caching:** Cache embeddings for frequently used codes
